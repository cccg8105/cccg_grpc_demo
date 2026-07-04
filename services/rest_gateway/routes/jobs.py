"""Job creation and SSE progress endpoints."""

from __future__ import annotations

import json
import threading
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from services.rest_gateway.hub import hub
from services.rest_gateway.ingest_client import start_pipeline
from services.rest_gateway.schemas import CreateJobRequest, CreateJobResponse

router = APIRouter(tags=["jobs"])


@router.post("/jobs", response_model=CreateJobResponse)
async def create_job(body: CreateJobRequest):
    job = await hub.create_job()
    thread = threading.Thread(
        target=start_pipeline,
        args=(job.job_id, body.file_path, body.chunk_size, body.sleep_ms),
        daemon=True,
    )
    thread.start()
    job.status = "starting"
    return CreateJobResponse(job_id=job.job_id, status=job.status)


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = await hub.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "job_id": job.job_id,
        "status": job.status,
        "last_event": job.last_event,
    }


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str):
    try:
        queue = await hub.subscribe(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job not found") from None

    async def event_stream() -> AsyncIterator[str]:
        yield f"data: {json.dumps({'type': 'connected', 'job_id': job_id})}\n\n"
        while True:
            payload = await queue.get()
            yield f"data: {json.dumps(payload)}\n\n"
            if payload.get("job_complete"):
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
