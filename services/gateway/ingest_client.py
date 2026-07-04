"""gRPC client: consume ingest RunPipeline stream and publish to JobHub."""

from __future__ import annotations

import asyncio
import logging

import grpc

from generated.pipeline.v1 import pipeline_pb2, pipeline_pb2_grpc
from services.common.limits import grpc_message_options
from services.gateway.config import INGEST_TARGET
from services.gateway.hub import JobHub

logger = logging.getLogger(__name__)


def run_pipeline(
    hub: JobHub,
    loop: asyncio.AbstractEventLoop,
    job_id: str,
    file_path: str,
    chunk_size: int,
    sleep_ms: int,
) -> None:
    """Consume Ingest RunPipeline stream. Intended to run in a background thread."""
    channel = grpc.insecure_channel(INGEST_TARGET, options=grpc_message_options())
    stub = pipeline_pb2_grpc.IngestServiceStub(channel)
    try:
        events = stub.RunPipeline(
            pipeline_pb2.StartPipelineRequest(
                job_id=job_id,
                file_path=file_path,
                chunk_size=chunk_size,
                sleep_ms=sleep_ms,
            )
        )
        for event in events:
            future = asyncio.run_coroutine_threadsafe(
                hub.publish(event),
                loop,
            )
            future.result(timeout=5)
            logger.info(
                "Progress job_id=%s stage=%s rows=%s",
                event.job_id,
                event.stage,
                event.rows_processed,
            )
    except grpc.RpcError as exc:
        logger.error("Pipeline stream failed job_id=%s: %s", job_id, exc)
    finally:
        channel.close()
