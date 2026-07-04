#!/usr/bin/env python3
"""Run a quick end-to-end smoke test against local gRPC services."""

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
DEFAULT_CHUNK_SIZE = 80_000


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


def smoke_chunk_size() -> int:
    raw = os.environ.get("SMOKE_CHUNK_SIZE", str(DEFAULT_CHUNK_SIZE))
    return max(1, int(raw))


def main() -> int:
    chunk_size = smoke_chunk_size()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["TRANSFORM_TARGET"] = "localhost:50052"
    env["INGEST_TARGET"] = "localhost:50051"
    env["DEFAULT_FILE"] = str(DATA_FILE)

    python = sys.executable
    procs = [
        subprocess.Popen([python, "-m", "services.transform.server"], env=env),
        subprocess.Popen([python, "-m", "services.ingest.server"], env=env),
        subprocess.Popen([python, "-m", "services.gateway.main"], env=env),
    ]

    try:
        wait_for_health("http://localhost:8080/health")
        payload = json.dumps(
            {
                "file_path": str(DATA_FILE),
                "chunk_size": chunk_size,
                "sleep_ms": 0,
            }
        ).encode()
        request = urllib.request.Request(
            "http://localhost:8080/jobs",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            job = json.load(response)
        print(f"Started job: {job['job_id']} (chunk_size={chunk_size})")

        deadline = time.time() + 300
        while time.time() < deadline:
            with urllib.request.urlopen(
                f"http://localhost:8080/jobs/{job['job_id']}",
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
                if wire_bytes_total >= bytes_streamed:
                    raise RuntimeError(
                        "Expected wire_bytes_total < bytes_streamed for typed protobuf gRPC"
                    )
                rows_processed = last.get("rows_processed", 0)
                if rows_processed <= 0:
                    raise RuntimeError("Expected rows_processed > 0 on completion")
                chunk_total = last.get("chunk_total", 0)
                print(
                    f"Smoke test OK (bytes_streamed={bytes_streamed}, "
                    f"wire_bytes_total={wire_bytes_total}, "
                    f"wire_ratio={wire_bytes_total / bytes_streamed:.3f}, "
                    f"rows={rows_processed}, chunk_total={chunk_total}, "
                    f"chunk_size={chunk_size})"
                )
                return 0
            time.sleep(1)

        raise RuntimeError("Job did not complete in time")
    finally:
        for proc in procs:
            proc.terminate()
        for proc in procs:
            proc.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
