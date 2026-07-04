"""HTTP client to start the REST ingest pipeline."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from services.rest_gateway.config import REST_INGEST_URL
from services.rest_gateway.schemas import StartPipelineRequest

logger = logging.getLogger(__name__)


def start_pipeline(
    job_id: str,
    file_path: str,
    chunk_size: int,
    sleep_ms: int,
) -> None:
    """Call rest-ingest internal start. Intended to run in a background thread."""
    body = StartPipelineRequest(
        job_id=job_id,
        file_path=file_path,
        chunk_size=chunk_size,
        sleep_ms=sleep_ms,
    )
    payload = json.dumps(body.model_dump()).encode("utf-8")
    request = urllib.request.Request(
        f"{REST_INGEST_URL}/internal/start-pipeline",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        logger.info(
            "REST ingest acknowledged job_id=%s status=%s",
            data.get("job_id"),
            data.get("status"),
        )
    except urllib.error.URLError as exc:
        logger.error("Failed to start REST pipeline job_id=%s: %s", job_id, exc)
