"""Transform gRPC service: enriches records and reports progress to gateway."""

from __future__ import annotations

import json
import logging
import os
import time
from concurrent import futures

import grpc

from generated.pipeline.v1 import pipeline_pb2, pipeline_pb2_grpc
from services.common.pipeline_utils import now_ms, preview_record, transform_record

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [transform] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

GATEWAY_TARGET = os.getenv("GATEWAY_TARGET", "gateway:50053")
TRANSFORM_PORT = int(os.getenv("TRANSFORM_PORT", "50052"))
PROGRESS_EVERY = int(os.getenv("PROGRESS_EVERY", "50"))


def _format_bytes(value: int) -> str:
    if value >= 1_048_576:
        return f"{value / 1_048_576:.1f} MB"
    if value >= 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value} B"


class TransformServicer(pipeline_pb2_grpc.TransformServiceServicer):
    def Ping(self, request, context):
        return pipeline_pb2.PingResponse(status="ok")

    def TransformStream(self, request_iterator, context):
        rows_processed = 0
        rows_rejected = 0
        total_usd = 0.0
        job_id = ""
        total_estimate = 0
        total_file_bytes = 0
        bytes_streamed = 0
        start_time = time.monotonic()
        last_preview = ""
        seen_first = False

        for raw in request_iterator:
            job_id = raw.job_id or job_id
            total_estimate = raw.total_rows_estimate or total_estimate
            total_file_bytes = raw.total_file_bytes or total_file_bytes
            bytes_streamed = raw.bytes_read
            payload = json.loads(raw.payload_json)
            transformed, error = transform_record(payload)
            elapsed = max(time.monotonic() - start_time, 0.001)
            bytes_throughput = bytes_streamed / elapsed

            if not seen_first:
                seen_first = True
                self._emit_progress(
                    self._build_progress_event(
                        job_id=job_id,
                        stage="ingest",
                        record_preview=raw.payload_json[:120],
                        rows_processed=0,
                        rows_rejected=0,
                        total_usd=0.0,
                        total_estimate=total_estimate,
                        throughput_rows=0.0,
                        bytes_streamed=bytes_streamed,
                        total_file_bytes=total_file_bytes,
                        bytes_throughput=bytes_throughput,
                        job_complete=False,
                        message=(
                            f"Ingest streaming from line {raw.line_number} "
                            f"({_format_bytes(bytes_streamed)} streamed)"
                        ),
                    )
                )

            if error:
                rows_rejected += 1
            else:
                rows_processed += 1
                total_usd += transformed["amount_usd"]
                last_preview = preview_record(transformed)

            total_handled = rows_processed + rows_rejected
            elapsed = max(time.monotonic() - start_time, 0.001)
            throughput = rows_processed / elapsed
            bytes_throughput = bytes_streamed / elapsed

            if total_handled % PROGRESS_EVERY == 0:
                self._emit_progress(
                    self._build_progress_event(
                        job_id=job_id,
                        stage="transform",
                        record_preview=last_preview,
                        rows_processed=rows_processed,
                        rows_rejected=rows_rejected,
                        total_usd=round(total_usd, 2),
                        total_estimate=total_estimate,
                        throughput_rows=round(throughput, 2),
                        bytes_streamed=bytes_streamed,
                        total_file_bytes=total_file_bytes,
                        bytes_throughput=bytes_throughput,
                        job_complete=False,
                        message=(
                            f"Processed line {raw.line_number} "
                            f"({_format_bytes(bytes_streamed)} streamed)"
                        ),
                    )
                )

        if job_id:
            elapsed = max(time.monotonic() - start_time, 0.001)
            self._emit_progress(
                self._build_progress_event(
                    job_id=job_id,
                    stage="complete",
                    record_preview=last_preview,
                    rows_processed=rows_processed,
                    rows_rejected=rows_rejected,
                    total_usd=round(total_usd, 2),
                    total_estimate=total_estimate,
                    throughput_rows=round(rows_processed / elapsed, 2),
                    bytes_streamed=bytes_streamed,
                    total_file_bytes=total_file_bytes,
                    bytes_throughput=bytes_streamed / elapsed,
                    job_complete=True,
                    message=(
                        f"Pipeline finished ({_format_bytes(bytes_streamed)} streamed)"
                    ),
                )
            )

        logger.info(
            "Stream done job_id=%s processed=%s rejected=%s total_usd=%.2f bytes=%s",
            job_id,
            rows_processed,
            rows_rejected,
            total_usd,
            bytes_streamed,
        )
        return pipeline_pb2.TransformSummary(
            rows_processed=rows_processed,
            rows_rejected=rows_rejected,
            total_usd=round(total_usd, 2),
        )

    @staticmethod
    def _build_progress_event(
        *,
        job_id: str,
        stage: str,
        record_preview: str,
        rows_processed: int,
        rows_rejected: int,
        total_usd: float,
        total_estimate: int,
        throughput_rows: float,
        bytes_streamed: int,
        total_file_bytes: int,
        bytes_throughput: float,
        job_complete: bool,
        message: str,
    ) -> pipeline_pb2.ProgressEvent:
        return pipeline_pb2.ProgressEvent(
            job_id=job_id,
            stage=stage,
            timestamp_ms=now_ms(),
            record_preview=record_preview,
            rows_processed=rows_processed,
            rows_rejected=rows_rejected,
            total_usd=total_usd,
            total_rows_estimate=total_estimate,
            throughput_rows_per_sec=throughput_rows,
            job_complete=job_complete,
            message=message,
            bytes_streamed=bytes_streamed,
            total_file_bytes=total_file_bytes,
            throughput_bytes_per_sec=round(bytes_throughput, 2),
        )

    def _emit_progress(self, event: pipeline_pb2.ProgressEvent) -> None:
        channel = grpc.insecure_channel(GATEWAY_TARGET)
        try:
            stub = pipeline_pb2_grpc.ProgressServiceStub(channel)
            stub.PublishEvents(iter([event]))
        except grpc.RpcError as exc:
            logger.error("Failed to publish progress: %s", exc)
        finally:
            channel.close()


def serve() -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    pipeline_pb2_grpc.add_TransformServiceServicer_to_server(
        TransformServicer(),
        server,
    )
    server.add_insecure_port(f"[::]:{TRANSFORM_PORT}")
    server.start()
    logger.info("Transform service listening on %s", TRANSFORM_PORT)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
