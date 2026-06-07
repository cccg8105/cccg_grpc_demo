"""Shared CSV batch reading for gRPC ingest and REST APIs."""

from __future__ import annotations

import csv
from pathlib import Path


def count_rows(file_path: str) -> int:
    with open(file_path, newline="", encoding="utf-8") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def file_meta(file_path: str) -> dict[str, int]:
    path = Path(file_path)
    return {
        "total_rows": count_rows(file_path),
        "total_file_bytes": path.stat().st_size,
    }


def read_batch(file_path: str, offset: int, limit: int) -> list[dict[str, str]]:
    """Return up to `limit` data rows starting at zero-based `offset`."""
    if limit <= 0:
        return []

    rows: list[dict[str, str]] = []
    skipped = 0

    with open(file_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if skipped < offset:
                skipped += 1
                continue
            rows.append(dict(row))
            if len(rows) >= limit:
                break

    return rows
