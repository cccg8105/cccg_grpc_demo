"""In-memory job state for REST gateway SSE subscribers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass
class JobState:
    job_id: str
    status: str = "pending"
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    last_event: dict | None = None
