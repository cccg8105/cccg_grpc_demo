#!/usr/bin/env python3
"""Smoke test for REST gateway pipeline (POST /jobs + SSE progress)."""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "transactions.csv"
GATEWAY_URL = "http://localhost:8090"


SMOKE_CHUNK_SIZE = 80_000


def smoke_chunk_size(data_file: Path) -> int:
    """Use the largest allowed batch to finish quickly on big CSVs."""
    total = 0
    with data_file.open(encoding="utf-8") as handle:
        next(handle, None)  # header
        for _ in handle:
            total += 1
    return max(1, min(total, SMOKE_CHUNK_SIZE))


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


def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["DEFAULT_FILE"] = str(DATA_FILE)
    env["REST_TRANSFORM_URL"] = "http://localhost:8092"
    env["REST_GATEWAY_URL"] = GATEWAY_URL
    env["REST_INGEST_URL"] = "http://localhost:8091"

    python = sys.executable
    procs = [
        subprocess.Popen([python, "-m", "services.rest_transform.main"], env=env),
        subprocess.Popen([python, "-m", "services.rest_ingest.main"], env=env),
        subprocess.Popen([python, "-m", "services.rest_gateway.main"], env=env),
    ]

    try:
        wait_for_health(f"{GATEWAY_URL}/health")
        payload = json.dumps(
            {
                "file_path": str(DATA_FILE),
                "chunk_size": smoke_chunk_size(DATA_FILE),
                "sleep_ms": 0,
            }
        ).encode()
        request = urllib.request.Request(
            f"{GATEWAY_URL}/jobs",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            job = json.load(response)
        print("Started REST job:", job["job_id"])

        deadline = time.time() + 600
        while time.time() < deadline:
            with urllib.request.urlopen(
                f"{GATEWAY_URL}/jobs/{job['job_id']}",
                timeout=10,
            ) as response:
                status = json.load(response)
            print("Status:", status.get("status"), status.get("last_event", {}))
            last = status.get("last_event") or {}
            if last.get("job_complete"):
                bytes_streamed = last.get("bytes_streamed", 0)
                if bytes_streamed <= 0:
                    raise RuntimeError("Expected bytes_streamed > 0 on completion")
                wire_bytes_total = last.get("wire_bytes_total", 0)
                if wire_bytes_total <= 0:
                    raise RuntimeError("Expected wire_bytes_total > 0 on completion")
                rows_processed = last.get("rows_processed", 0)
                if rows_processed <= 0:
                    raise RuntimeError("Expected rows_processed > 0 on completion")
                chunk_total = last.get("chunk_total", 0)
                if chunk_total <= 0:
                    raise RuntimeError("Expected chunk_total > 0 on completion")
                print(
                    f"REST smoke test OK (bytes_streamed={bytes_streamed}, "
                    f"wire_bytes_total={wire_bytes_total}, "
                    f"rows={rows_processed}, chunk_total={chunk_total})"
                )
                return 0
            time.sleep(1)

        raise RuntimeError("REST job did not complete in time")
    finally:
        for proc in procs:
            proc.terminate()
        for proc in procs:
            proc.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
