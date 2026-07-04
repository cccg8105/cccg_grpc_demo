"""REST ingest API: server-side pipeline and debug pagination endpoints."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from services.common.csv_batch import file_meta, iter_csv_batches, read_batch
from services.common.limits import MAX_CHUNK_SIZE, MIN_CHUNK_SIZE
from services.common.progress import ProgressPayload
from services.common.progress_builder import (
    BatchMeta,
    BatchTransformResult,
    JobAccumulators,
    build_batch_progress,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [rest-ingest] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

HTTP_PORT = int(os.getenv("HTTP_PORT", "8091"))
DEFAULT_FILE = os.getenv("DEFAULT_FILE", "/data/transactions.csv")
REST_TRANSFORM_URL = os.getenv("REST_TRANSFORM_URL", "http://rest-transform:8092")
REST_GATEWAY_URL = os.getenv("REST_GATEWAY_URL", "http://rest-gateway:8090")


class StartPipelineBody(BaseModel):
    job_id: str
    file_path: str
    chunk_size: int
    sleep_ms: int


app = FastAPI(title="REST Ingest API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _resolve_file(file_path: str | None) -> str:
    path = file_path or DEFAULT_FILE
    if not Path(path).exists():
        raise HTTPException(status_code=404, detail=f"file not found: {path}")
    return path


def _post_transform(records: list[dict]) -> tuple[dict, int]:
    body = json.dumps({"records": records}).encode("utf-8")
    wire_bytes_batch = len(body)
    request = urllib.request.Request(
        f"{REST_TRANSFORM_URL}/transform",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8")), wire_bytes_batch


def _post_progress(payload: ProgressPayload) -> None:
    body = json.dumps(payload.model_dump()).encode("utf-8")
    request = urllib.request.Request(
        f"{REST_GATEWAY_URL}/internal/progress",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10):
            pass
    except urllib.error.URLError as exc:
        logger.error(
            "Failed to publish REST progress job_id=%s: %s",
            payload.job_id,
            exc,
        )


def _run_pipeline(job_id: str, file_path: str, chunk_size: int, sleep_ms: int) -> None:
    accumulators = JobAccumulators()
    pipeline_started_at = time.monotonic()

    try:
        for batch in iter_csv_batches(file_path, chunk_size):
            result, wire_bytes_batch = _post_transform(batch.records)
            meta = BatchMeta(
                job_id=job_id,
                chunk_index=batch.chunk_index,
                chunk_total=batch.chunk_total,
                bytes_streamed=batch.bytes_read,
                total_rows_estimate=batch.total_rows_estimate,
                total_file_bytes=batch.total_file_bytes,
                line_number_end=batch.line_number_end,
            )
            transform_result = BatchTransformResult(
                rows_processed=result["rows_processed"],
                rows_rejected=result["rows_rejected"],
                total_usd_delta=result["total_usd_delta"],
                record_preview=result.get("record_preview", ""),
            )
            job_complete = batch.chunk_index == batch.chunk_total
            payload = build_batch_progress(
                meta=meta,
                batch_result=transform_result,
                accumulators=accumulators,
                pipeline_started_at=pipeline_started_at,
                wire_bytes_batch=wire_bytes_batch,
                job_complete=job_complete,
            )
            _post_progress(payload)

            if sleep_ms > 0:
                time.sleep(sleep_ms / 1000.0)

        logger.info(
            "REST pipeline complete job_id=%s processed=%s rejected=%s",
            job_id,
            accumulators.rows_processed,
            accumulators.rows_rejected,
        )
    except urllib.error.URLError as exc:
        logger.error("REST pipeline failed job_id=%s error=%s", job_id, exc)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/internal/start-pipeline")
async def start_pipeline(body: StartPipelineBody):
    path = _resolve_file(body.file_path)
    thread = threading.Thread(
        target=_run_pipeline,
        args=(body.job_id, path, body.chunk_size, body.sleep_ms),
        daemon=True,
    )
    thread.start()
    logger.info("Started REST pipeline job_id=%s file=%s", body.job_id, path)
    return {"job_id": body.job_id, "status": "started"}


@app.get("/meta")
async def get_meta(file_path: str | None = Query(default=None)):
    path = _resolve_file(file_path)
    meta = file_meta(path)
    payload = {"file_path": path, **meta}
    body = json.dumps(payload, ensure_ascii=True)
    return {**payload, "response_bytes": len(body.encode("utf-8"))}


@app.get("/records")
async def get_records(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=MIN_CHUNK_SIZE, le=MAX_CHUNK_SIZE),
    file_path: str | None = Query(default=None),
):
    path = _resolve_file(file_path)
    meta = file_meta(path)
    records = read_batch(path, offset, limit)
    has_more = offset + len(records) < meta["total_rows"]

    payload = {
        "offset": offset,
        "limit": limit,
        "total_rows": meta["total_rows"],
        "total_file_bytes": meta["total_file_bytes"],
        "records": records,
        "has_more": has_more,
    }
    body = json.dumps(payload, ensure_ascii=True)
    return {**payload, "response_bytes": len(body.encode("utf-8"))}


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=HTTP_PORT, log_level="info")


if __name__ == "__main__":
    main()
