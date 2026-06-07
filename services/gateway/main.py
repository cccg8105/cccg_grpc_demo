"""Gateway: REST + SSE for frontend, gRPC ProgressService for transform."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import uuid
from concurrent import futures
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator

import grpc
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from generated.pipeline.v1 import pipeline_pb2, pipeline_pb2_grpc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [gateway] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

INGEST_TARGET = os.getenv("INGEST_TARGET", "ingest-service:50051")
HTTP_PORT = int(os.getenv("HTTP_PORT", "8080"))
GRPC_PORT = int(os.getenv("GRPC_PORT", "50053"))
DEFAULT_FILE = os.getenv("DEFAULT_FILE", "/data/transactions.csv")


@dataclass
class JobState:
    job_id: str
    status: str = "pending"
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    last_event: dict | None = None


class JobHub:
    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}
        self._lock = asyncio.Lock()

    async def create_job(self) -> JobState:
        job_id = str(uuid.uuid4())
        job = JobState(job_id=job_id, status="created")
        async with self._lock:
            self._jobs[job_id] = job
        return job

    async def get_job(self, job_id: str) -> JobState | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def subscribe(self, job_id: str) -> asyncio.Queue:
        job = await self.get_job(job_id)
        if job is None:
            raise KeyError(job_id)
        queue: asyncio.Queue = asyncio.Queue()
        job.subscribers.append(queue)
        if job.last_event is not None:
            await queue.put(job.last_event)
        return queue

    async def publish(self, event: pipeline_pb2.ProgressEvent) -> None:
        payload = _event_to_dict(event)
        job = await self.get_job(event.job_id)
        if job is None:
            logger.warning("Unknown job_id in progress event: %s", event.job_id)
            return

        job.last_event = payload
        if event.job_complete:
            job.status = "complete"
        else:
            job.status = "running"

        for queue in list(job.subscribers):
            await queue.put(payload)


def _event_to_dict(event: pipeline_pb2.ProgressEvent) -> dict:
    return {
        "job_id": event.job_id,
        "stage": event.stage,
        "timestamp_ms": event.timestamp_ms,
        "record_preview": event.record_preview,
        "rows_processed": event.rows_processed,
        "rows_rejected": event.rows_rejected,
        "total_usd": event.total_usd,
        "total_rows_estimate": event.total_rows_estimate,
        "throughput_rows_per_sec": event.throughput_rows_per_sec,
        "job_complete": event.job_complete,
        "message": event.message,
        "bytes_streamed": event.bytes_streamed,
        "total_file_bytes": event.total_file_bytes,
        "throughput_bytes_per_sec": event.throughput_bytes_per_sec,
    }


hub = JobHub()
loop_holder: dict[str, asyncio.AbstractEventLoop] = {}


class ProgressServicer(pipeline_pb2_grpc.ProgressServiceServicer):
    def Ping(self, request, context):
        return pipeline_pb2.PingResponse(status="ok")

    def PublishEvents(self, request_iterator, context):
        event_loop = loop_holder.get("loop")
        for event in request_iterator:
            if event_loop is not None:
                future = asyncio.run_coroutine_threadsafe(
                    hub.publish(event),
                    event_loop,
                )
                future.result(timeout=5)
            logger.info(
                "Progress job_id=%s stage=%s rows=%s",
                event.job_id,
                event.stage,
                event.rows_processed,
            )
        return pipeline_pb2.Ack(ok=True)


def start_grpc_server() -> grpc.Server:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    pipeline_pb2_grpc.add_ProgressServiceServicer_to_server(
        ProgressServicer(),
        server,
    )
    server.add_insecure_port(f"[::]:{GRPC_PORT}")
    server.start()
    logger.info("Gateway gRPC listening on %s", GRPC_PORT)
    return server


class CreateJobRequest(BaseModel):
    file_path: str = Field(default=DEFAULT_FILE)
    chunk_size: int = Field(default=100, ge=1, le=5000)
    sleep_ms: int = Field(default=0, ge=0, le=5000)


class CreateJobResponse(BaseModel):
    job_id: str
    status: str


def _start_pipeline(job_id: str, file_path: str, chunk_size: int, sleep_ms: int) -> None:
    channel = grpc.insecure_channel(INGEST_TARGET)
    stub = pipeline_pb2_grpc.IngestServiceStub(channel)
    try:
        response = stub.StartPipeline(
            pipeline_pb2.StartPipelineRequest(
                job_id=job_id,
                file_path=file_path,
                chunk_size=chunk_size,
                sleep_ms=sleep_ms,
            )
        )
        logger.info("Ingest acknowledged job_id=%s status=%s", response.job_id, response.status)
    except grpc.RpcError as exc:
        logger.error("Failed to start pipeline job_id=%s: %s", job_id, exc)
    finally:
        channel.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop_holder["loop"] = asyncio.get_running_loop()
    grpc_server = start_grpc_server()
    yield
    grpc_server.stop(grace=2)


app = FastAPI(title="gRPC Pipeline Gateway", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/jobs", response_model=CreateJobResponse)
async def create_job(body: CreateJobRequest):
    job = await hub.create_job()
    thread = threading.Thread(
        target=_start_pipeline,
        args=(job.job_id, body.file_path, body.chunk_size, body.sleep_ms),
        daemon=True,
    )
    thread.start()
    job.status = "starting"
    return CreateJobResponse(job_id=job.job_id, status=job.status)


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = await hub.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job_id": job.job_id, "status": job.status, "last_event": job.last_event}


@app.get("/jobs/{job_id}/events")
async def job_events(job_id: str):
    try:
        queue = await hub.subscribe(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job not found") from None

    async def event_stream() -> AsyncIterator[str]:
        yield f"data: {json.dumps({'type': 'connected', 'job_id': job_id})}\n\n"
        while True:
            payload = await queue.get()
            yield f"data: {json.dumps(payload)}\n\n"
            if payload.get("job_complete"):
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=HTTP_PORT, log_level="info")


if __name__ == "__main__":
    main()
