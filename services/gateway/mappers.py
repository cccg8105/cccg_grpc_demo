"""Map protobuf messages to JSON-serializable dicts."""

from __future__ import annotations

from generated.pipeline.v1 import pipeline_pb2


def progress_event_to_dict(event: pipeline_pb2.ProgressEvent) -> dict:
    """Convert a ProgressEvent protobuf to a dict for SSE payloads."""
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
        "chunk_index": event.chunk_index,
        "chunk_total": event.chunk_total,
        "wire_bytes_total": event.wire_bytes_total,
        "wire_bytes_batch": event.wire_bytes_batch,
    }
