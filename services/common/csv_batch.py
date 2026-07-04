"""Shared CSV batch reading for gRPC ingest and REST APIs."""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
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


@dataclass
class CsvBatch:
    chunk_index: int
    chunk_total: int
    chunk_size: int
    records: list[dict[str, str]]
    bytes_read: int
    total_rows_estimate: int
    total_file_bytes: int
    line_number_end: int


def iter_csv_batches(file_path: str, chunk_size: int):
    """Yield CSV rows in sequential batches (single pass over the file)."""
    if chunk_size <= 0:
        return

    meta = file_meta(file_path)
    total_estimate = meta["total_rows"]
    total_file_bytes = meta["total_file_bytes"]
    chunk_total = max(1, math.ceil(total_estimate / chunk_size)) if total_estimate else 1

    records: list[dict[str, str]] = []
    bytes_read = 0
    chunk_index = 0
    line_number_end = 1

    with open(file_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for line_number, row in enumerate(reader, start=2):
            record = dict(row)
            payload = json.dumps(record, ensure_ascii=True)
            bytes_read += len(payload.encode("utf-8"))
            records.append(record)
            line_number_end = line_number

            if len(records) >= chunk_size:
                chunk_index += 1
                yield CsvBatch(
                    chunk_index=chunk_index,
                    chunk_total=chunk_total,
                    chunk_size=chunk_size,
                    records=list(records),
                    bytes_read=bytes_read,
                    total_rows_estimate=total_estimate,
                    total_file_bytes=total_file_bytes,
                    line_number_end=line_number_end,
                )
                records = []

    if records:
        chunk_index += 1
        yield CsvBatch(
            chunk_index=chunk_index,
            chunk_total=chunk_total,
            chunk_size=chunk_size,
            records=list(records),
            bytes_read=bytes_read,
            total_rows_estimate=total_estimate,
            total_file_bytes=total_file_bytes,
            line_number_end=line_number_end,
        )
