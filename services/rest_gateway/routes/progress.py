"""Internal progress ingestion from rest-ingest."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from services.common.progress import ProgressPayload
from services.rest_gateway.hub import hub

router = APIRouter(tags=["internal"])


@router.post("/internal/progress")
async def receive_progress(body: ProgressPayload):
    job = await hub.get_job(body.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    await hub.publish(body)
    return {"ok": True}
