"""Ingest gRPC service: reads CSV, orchestrates transform, streams progress."""

from __future__ import annotations

import logging
import os
import queue
import time
from concurrent import futures
from pathlib import Path

import grpc

from generated.pipeline.v1 import pipeline_pb2, pipeline_pb2_grpc
from services.common.csv_batch import iter_csv_batches
from services.common.limits import grpc_message_options
from services.common.pipeline_utils import csv_row_to_proto
from services.common.progress_builder import (
    BatchMeta,
    BatchTransformResult,
    JobAccumulators,
    build_batch_progress,
    progress_payload_to_proto,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ingest] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

TRANSFORM_TARGET = os.getenv("TRANSFORM_TARGET", "transform-service:50052")
INGEST_PORT = int(os.getenv("INGEST_PORT", "50051"))


class IngestServicer(pipeline_pb2_grpc.IngestServiceServicer):
    def Ping(self, request, context):
        return pipeline_pb2.PingResponse(status="ok")

    def RunPipeline(self, request, context):
        job_id = request.job_id
        file_path = request.file_path or "/data/transactions.csv"
        chunk_size = request.chunk_size or 100
        sleep_ms = request.sleep_ms or 0

        if not Path(file_path).exists():
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"file not found: {file_path}",
            )

        channel = grpc.insecure_channel(
            TRANSFORM_TARGET,
            options=grpc_message_options(),
        )
        stub = pipeline_pb2_grpc.TransformServiceStub(channel)
        accumulators = JobAccumulators()
        pipeline_started_at = time.monotonic()
        batch_queue: queue.Queue[pipeline_pb2.RecordBatch] = queue.Queue()

        def batch_generator():
            for batch in iter_csv_batches(file_path, chunk_size):
                record_batch = pipeline_pb2.RecordBatch(
                    job_id=job_id,
                    chunk_index=batch.chunk_index,
                    chunk_total=batch.chunk_total,
                    chunk_size=batch.chunk_size,
                    records=[csv_row_to_proto(row) for row in batch.records],
                    bytes_read=batch.bytes_read,
                    total_rows_estimate=batch.total_rows_estimate,
                    total_file_bytes=batch.total_file_bytes,
                    line_number_end=batch.line_number_end,
                )
                batch_queue.put(record_batch)
                yield record_batch
                if sleep_ms > 0:
                    time.sleep(sleep_ms / 1000.0)

        try:
            responses = stub.TransformStream(batch_generator())
            for batch_result in responses:
                record_batch = batch_queue.get()
                wire_bytes_batch = record_batch.ByteSize()
                meta = BatchMeta(
                    job_id=job_id,
                    chunk_index=record_batch.chunk_index,
                    chunk_total=record_batch.chunk_total,
                    bytes_streamed=record_batch.bytes_read,
                    total_rows_estimate=record_batch.total_rows_estimate,
                    total_file_bytes=record_batch.total_file_bytes,
                    line_number_end=record_batch.line_number_end,
                )
                transform_result = BatchTransformResult(
                    rows_processed=batch_result.rows_processed,
                    rows_rejected=batch_result.rows_rejected,
                    total_usd_delta=batch_result.total_usd_delta,
                    record_preview=batch_result.record_preview,
                )
                job_complete = record_batch.chunk_index == record_batch.chunk_total
                payload = build_batch_progress(
                    meta=meta,
                    batch_result=transform_result,
                    accumulators=accumulators,
                    pipeline_started_at=pipeline_started_at,
                    wire_bytes_batch=wire_bytes_batch,
                    job_complete=job_complete,
                )
                yield progress_payload_to_proto(payload)

            logger.info(
                "Pipeline complete job_id=%s processed=%s rejected=%s total_usd=%.2f",
                job_id,
                accumulators.rows_processed,
                accumulators.rows_rejected,
                accumulators.total_usd,
            )
        except grpc.RpcError as exc:
            logger.error("Pipeline failed job_id=%s error=%s", job_id, exc)
            context.abort(exc.code(), exc.details() or str(exc))
        finally:
            channel.close()


def serve() -> None:
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=8),
        options=grpc_message_options(),
    )
    pipeline_pb2_grpc.add_IngestServiceServicer_to_server(
        IngestServicer(),
        server,
    )
    server.add_insecure_port(f"[::]:{INGEST_PORT}")
    server.start()
    logger.info("Ingest service listening on %s", INGEST_PORT)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
