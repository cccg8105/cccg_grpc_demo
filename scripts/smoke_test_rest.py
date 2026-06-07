#!/usr/bin/env python3
"""Smoke test for REST batch APIs."""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "transactions.csv"
INGEST_URL = "http://localhost:8091"
TRANSFORM_URL = "http://localhost:8092"


def wait_for_health(url: str, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.5)
    raise RuntimeError(f"Service not ready: {url}")


def fetch_json(url: str, method: str = "GET", body: dict | None = None) -> dict:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["DEFAULT_FILE"] = str(DATA_FILE)

    python = sys.executable
    procs = [
        subprocess.Popen([python, "-m", "services.rest_ingest.main"], env=env),
        subprocess.Popen([python, "-m", "services.rest_transform.main"], env=env),
    ]

    try:
        wait_for_health(f"{INGEST_URL}/health")
        wait_for_health(f"{TRANSFORM_URL}/health")

        file_qs = urllib.parse.urlencode({"file_path": str(DATA_FILE)})
        meta = fetch_json(f"{INGEST_URL}/meta?{file_qs}")
        total_rows = meta["total_rows"]
        chunk_size = 100
        offset = 0
        processed = 0
        rejected = 0
        request_count = 1

        while offset < total_rows:
            records_qs = urllib.parse.urlencode(
                {
                    "offset": offset,
                    "limit": chunk_size,
                    "file_path": str(DATA_FILE),
                }
            )
            batch = fetch_json(f"{INGEST_URL}/records?{records_qs}")
            request_count += 1

            result = fetch_json(
                f"{TRANSFORM_URL}/transform",
                method="POST",
                body={"records": batch["records"]},
            )
            request_count += 1

            processed += result["rows_processed"]
            rejected += result["rows_rejected"]
            offset += len(batch["records"])
            if not batch["has_more"] or not batch["records"]:
                break

        if processed <= 0:
            raise RuntimeError("Expected rows_processed > 0")
        if request_count < 3:
            raise RuntimeError("Expected multiple REST requests")

        print(
            f"REST smoke test OK processed={processed} rejected={rejected} "
            f"requests={request_count}"
        )
        return 0
    finally:
        for proc in procs:
            proc.terminate()
        for proc in procs:
            proc.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
