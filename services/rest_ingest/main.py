"""REST ingest API: paginated CSV records for batch comparison demo."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from services.common.csv_batch import file_meta, read_batch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [rest-ingest] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

HTTP_PORT = int(os.getenv("HTTP_PORT", "8091"))
DEFAULT_FILE = os.getenv("DEFAULT_FILE", "/data/transactions.csv")

app = FastAPI(title="REST Ingest API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _resolve_file(file_path: str | None) -> str:
    path = file_path or DEFAULT_FILE
    if not Path(path).exists():
        raise HTTPException(status_code=404, detail=f"file not found: {path}")
    return path


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/meta")
async def get_meta(file_path: str | None = Query(default=None)):
    path = _resolve_file(file_path)
    meta = file_meta(path)
    payload = {"file_path": path, **meta}
    body = json.dumps(payload, ensure_ascii=True)
    return {**payload, "response_bytes": len(body.encode("utf-8"))}


@app.get("/records")
async def get_records(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=10000),
    file_path: str | None = Query(default=None),
):
    path = _resolve_file(file_path)
    meta = file_meta(path)
    records = read_batch(path, offset, limit)
    has_more = offset + len(records) < meta["total_rows"]

    payload = {
        "offset": offset,
        "limit": limit,
        "total_rows": meta["total_rows"],
        "total_file_bytes": meta["total_file_bytes"],
        "records": records,
        "has_more": has_more,
    }
    body = json.dumps(payload, ensure_ascii=True)
    return {**payload, "response_bytes": len(body.encode("utf-8"))}


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=HTTP_PORT, log_level="info")


if __name__ == "__main__":
    main()
