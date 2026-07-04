"""REST transform API: batch JSON transformation (pure worker)."""

from __future__ import annotations

import logging
import os
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from services.common.pipeline_utils import preview_record, transform_record

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [rest-transform] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

HTTP_PORT = int(os.getenv("HTTP_PORT", "8092"))


class TransformRequest(BaseModel):
    records: list[dict[str, Any]] = Field(default_factory=list)


class TransformResponse(BaseModel):
    rows_processed: int
    rows_rejected: int
    total_usd_delta: float
    record_preview: str = ""


app = FastAPI(title="REST Transform API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/transform", response_model=TransformResponse)
async def transform_batch(body: TransformRequest):
    rows_processed = 0
    rows_rejected = 0
    total_usd_delta = 0.0
    last_preview = ""

    for record in body.records:
        result, error = transform_record(record)
        if error:
            rows_rejected += 1
        else:
            rows_processed += 1
            total_usd_delta += result["amount_usd"]
            last_preview = preview_record(result)

    return TransformResponse(
        rows_processed=rows_processed,
        rows_rejected=rows_rejected,
        total_usd_delta=round(total_usd_delta, 2),
        record_preview=last_preview,
    )


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=HTTP_PORT, log_level="info")


if __name__ == "__main__":
    main()
