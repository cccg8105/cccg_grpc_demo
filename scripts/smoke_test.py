#!/usr/bin/env python3
"""Run a quick end-to-end smoke test against local services."""

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
    env["GATEWAY_TARGET"] = "localhost:50053"
    env["TRANSFORM_TARGET"] = "localhost:50052"
    env["INGEST_TARGET"] = "localhost:50051"
    env["DEFAULT_FILE"] = str(DATA_FILE)

    python = sys.executable
    procs = [
        subprocess.Popen([python, "-m", "services.gateway.main"], env=env),
        subprocess.Popen([python, "-m", "services.transform.server"], env=env),
        subprocess.Popen([python, "-m", "services.ingest.server"], env=env),
    ]

    try:
        wait_for_health("http://localhost:8080/health")
        payload = json.dumps(
            {
                "file_path": str(DATA_FILE),
                "chunk_size": 200,
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
        print("Started job:", job["job_id"])

        deadline = time.time() + 120
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
                print(f"Smoke test OK (bytes_streamed={bytes_streamed})")
                return 0
            time.sleep(2)

        raise RuntimeError("Job did not complete in time")
    finally:
        for proc in procs:
            proc.terminate()
        for proc in procs:
            proc.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
