"""Pydantic schemas for REST gateway API."""

from __future__ import annotations

from pydantic import BaseModel, Field

from services.common.limits import MAX_CHUNK_SIZE, MIN_CHUNK_SIZE
from services.rest_gateway.config import DEFAULT_FILE


class CreateJobRequest(BaseModel):
    file_path: str = Field(default=DEFAULT_FILE)
    chunk_size: int = Field(default=100, ge=MIN_CHUNK_SIZE, le=MAX_CHUNK_SIZE)
    sleep_ms: int = Field(default=0, ge=0, le=5000)


class CreateJobResponse(BaseModel):
    job_id: str
    status: str


class StartPipelineRequest(BaseModel):
    job_id: str
    file_path: str
    chunk_size: int
    sleep_ms: int
