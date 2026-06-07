"""Ingest gRPC service: reads CSV and streams raw records to transform."""

from __future__ import annotations

import csv
import json
import logging
import os
import threading
import time
from concurrent import futures
from pathlib import Path

import grpc

from generated.pipeline.v1 import pipeline_pb2, pipeline_pb2_grpc
from services.common.csv_batch import file_meta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ingest] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

TRANSFORM_TARGET = os.getenv("TRANSFORM_TARGET", "transform-service:50052")
INGEST_PORT = int(os.getenv("INGEST_PORT", "50051"))
PROGRESS_EVERY = int(os.getenv("PROGRESS_EVERY", "50"))


class IngestServicer(pipeline_pb2_grpc.IngestServiceServicer):
    def Ping(self, request, context):
        return pipeline_pb2.PingResponse(status="ok")

    def StartPipeline(self, request, context):
        job_id = request.job_id
        file_path = request.file_path or "/data/transactions.csv"
        chunk_size = request.chunk_size or 100
        sleep_ms = request.sleep_ms or 0

        if not Path(file_path).exists():
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"file not found: {file_path}")
            return pipeline_pb2.StartPipelineResponse()

        thread = threading.Thread(
            target=self._run_pipeline,
            args=(job_id, file_path, chunk_size, sleep_ms),
            daemon=True,
        )
        thread.start()
        logger.info("Started pipeline job_id=%s file=%s", job_id, file_path)
        return pipeline_pb2.StartPipelineResponse(job_id=job_id, status="started")

    def _run_pipeline(
        self,
        job_id: str,
        file_path: str,
        chunk_size: int,
        sleep_ms: int,
    ) -> None:
        channel = grpc.insecure_channel(TRANSFORM_TARGET)
        stub = pipeline_pb2_grpc.TransformServiceStub(channel)

        def record_generator():
            meta = file_meta(file_path)
            total_estimate = meta["total_rows"]
            total_file_bytes = meta["total_file_bytes"]
            bytes_read = 0
            chunk_count = 0
            emitted = 0

            with open(file_path, newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                for line_number, row in enumerate(reader, start=2):
                    payload = json.dumps(row, ensure_ascii=True)
                    bytes_read += len(payload.encode("utf-8"))
                    emitted += 1
                    chunk_count += 1

                    yield pipeline_pb2.RawRecord(
                        job_id=job_id,
                        line_number=line_number,
                        payload_json=payload,
                        bytes_read=bytes_read,
                        total_rows_estimate=total_estimate,
                        total_file_bytes=total_file_bytes,
                    )

                    if chunk_count >= chunk_size:
                        chunk_count = 0
                        if sleep_ms > 0:
                            time.sleep(sleep_ms / 1000.0)

            logger.info(
                "Finished streaming job_id=%s rows=%s bytes=%s",
                job_id,
                emitted,
                bytes_read,
            )

        try:
            summary = stub.TransformStream(record_generator())
            logger.info(
                "Transform complete job_id=%s processed=%s rejected=%s total_usd=%.2f",
                job_id,
                summary.rows_processed,
                summary.rows_rejected,
                summary.total_usd,
            )
        except grpc.RpcError as exc:
            logger.error("Pipeline failed job_id=%s error=%s", job_id, exc)
        finally:
            channel.close()


def serve() -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
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
