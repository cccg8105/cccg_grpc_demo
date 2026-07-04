"""In-memory job registry and SSE fan-out."""

from __future__ import annotations

import asyncio
import logging
import uuid

from generated.pipeline.v1 import pipeline_pb2

from services.gateway.mappers import progress_event_to_dict
from services.gateway.state import JobState

logger = logging.getLogger(__name__)


class JobHub:
    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}
        self._lock = asyncio.Lock()

    async def create_job(self) -> JobState:
        job_id = str(uuid.uuid4())
        job = JobState(job_id=job_id, status="created")
        async with self._lock:
            self._jobs[job_id] = job
        return job

    async def get_job(self, job_id: str) -> JobState | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def subscribe(self, job_id: str) -> asyncio.Queue:
        job = await self.get_job(job_id)
        if job is None:
            raise KeyError(job_id)
        queue: asyncio.Queue = asyncio.Queue()
        job.subscribers.append(queue)
        if job.last_event is not None:
            await queue.put(job.last_event)
        return queue

    async def publish(self, event: pipeline_pb2.ProgressEvent) -> None:
        payload = progress_event_to_dict(event)
        job = await self.get_job(event.job_id)
        if job is None:
            logger.warning("Unknown job_id in progress event: %s", event.job_id)
            return

        job.last_event = payload
        if event.job_complete:
            job.status = "complete"
        else:
            job.status = "running"

        for queue in list(job.subscribers):
            await queue.put(payload)


hub = JobHub()
