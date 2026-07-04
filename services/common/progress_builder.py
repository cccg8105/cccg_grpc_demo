"""Build progress events after a pipeline batch completes (ingest + transform)."""

from __future__ import annotations

import time
from dataclasses import dataclass

from generated.pipeline.v1 import pipeline_pb2

from services.common.pipeline_utils import now_ms
from services.common.progress import ProgressPayload


def format_bytes(value: int) -> str:
    if value >= 1_048_576:
        return f"{value / 1_048_576:.1f} MB"
    if value >= 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value} B"


@dataclass(frozen=True)
class BatchMeta:
    job_id: str
    chunk_index: int
    chunk_total: int
    bytes_streamed: int
    total_rows_estimate: int
    total_file_bytes: int
    line_number_end: int = 0


@dataclass(frozen=True)
class BatchTransformResult:
    rows_processed: int
    rows_rejected: int
    total_usd_delta: float
    record_preview: str


@dataclass
class JobAccumulators:
    rows_processed: int = 0
    rows_rejected: int = 0
    total_usd: float = 0.0
    wire_bytes_total: int = 0


def build_batch_progress(
    *,
    meta: BatchMeta,
    batch_result: BatchTransformResult,
    accumulators: JobAccumulators,
    pipeline_started_at: float,
    wire_bytes_batch: int,
    job_complete: bool,
) -> ProgressPayload:
    """Build a progress payload after ingest and transform finish one batch."""
    accumulators.rows_processed += batch_result.rows_processed
    accumulators.rows_rejected += batch_result.rows_rejected
    accumulators.total_usd += batch_result.total_usd_delta
    accumulators.wire_bytes_total += wire_bytes_batch

    elapsed = max(time.monotonic() - pipeline_started_at, 0.001)
    throughput = accumulators.rows_processed / elapsed
    bytes_throughput = meta.bytes_streamed / elapsed
    rows_in_batch = batch_result.rows_processed + batch_result.rows_rejected
    stage = "complete" if job_complete else "batch"

    if job_complete:
        message = (
            f"Pipeline finished ({format_bytes(meta.bytes_streamed)} streamed)"
        )
    else:
        message = (
            f"Lote {meta.chunk_index}/{meta.chunk_total}: "
            f"{rows_in_batch} filas procesadas "
            f"({format_bytes(meta.bytes_streamed)} streamed)"
        )

    return ProgressPayload(
        job_id=meta.job_id,
        stage=stage,
        timestamp_ms=now_ms(),
        record_preview=batch_result.record_preview,
        rows_processed=accumulators.rows_processed,
        rows_rejected=accumulators.rows_rejected,
        total_usd=round(accumulators.total_usd, 2),
        total_rows_estimate=meta.total_rows_estimate,
        throughput_rows_per_sec=round(throughput, 2),
        job_complete=job_complete,
        message=message,
        bytes_streamed=meta.bytes_streamed,
        total_file_bytes=meta.total_file_bytes,
        throughput_bytes_per_sec=round(bytes_throughput, 2),
        chunk_index=meta.chunk_index,
        chunk_total=meta.chunk_total,
        wire_bytes_total=accumulators.wire_bytes_total,
        wire_bytes_batch=wire_bytes_batch,
    )


def progress_payload_to_proto(payload: ProgressPayload) -> pipeline_pb2.ProgressEvent:
    """Convert a ProgressPayload to a gRPC ProgressEvent."""
    return pipeline_pb2.ProgressEvent(
        job_id=payload.job_id,
        stage=payload.stage,
        timestamp_ms=payload.timestamp_ms,
        record_preview=payload.record_preview,
        rows_processed=payload.rows_processed,
        rows_rejected=payload.rows_rejected,
        total_usd=payload.total_usd,
        total_rows_estimate=payload.total_rows_estimate,
        throughput_rows_per_sec=payload.throughput_rows_per_sec,
        job_complete=payload.job_complete,
        message=payload.message,
        bytes_streamed=payload.bytes_streamed,
        total_file_bytes=payload.total_file_bytes,
        throughput_bytes_per_sec=payload.throughput_bytes_per_sec,
        chunk_index=payload.chunk_index,
        chunk_total=payload.chunk_total,
        wire_bytes_total=payload.wire_bytes_total,
        wire_bytes_batch=payload.wire_bytes_batch,
    )
