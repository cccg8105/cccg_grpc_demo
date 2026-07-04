"""Shared progress event payload for SSE (gRPC mapper + REST gateway)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProgressPayload(BaseModel):
    job_id: str
    stage: str = ""
    timestamp_ms: int = 0
    record_preview: str = ""
    rows_processed: int = 0
    rows_rejected: int = 0
    total_usd: float = 0.0
    total_rows_estimate: int = 0
    throughput_rows_per_sec: float = 0.0
    job_complete: bool = False
    message: str = ""
    bytes_streamed: int = 0
    total_file_bytes: int = 0
    throughput_bytes_per_sec: float = 0.0
    chunk_index: int = 0
    chunk_total: int = 0
    wire_bytes_total: int = 0
    wire_bytes_batch: int = 0

    def to_sse_dict(self) -> dict:
        return self.model_dump()
