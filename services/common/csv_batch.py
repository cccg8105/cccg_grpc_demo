"""Shared CSV helpers for gRPC ingest and REST APIs.

Nota sobre diseño:
- `count_rows` y `file_meta` escanean el archivo una sola vez para obtener metadata.
- `read_batch` lee fila por fila desde el inicio hasta `offset + limit`.
  Para el demo (~50k filas) el overhead de escanear desde el offset es aceptable.
  En datasets muy grandes, una alternativa futura podría ser indexar el CSV o usar
  formatos binarios tipo Parquet / `read_csv_batched` de Polars.
"""

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
    """Devuelve hasta `limit` filas de datos desde `offset` (base cero).

    Implementación secuencial con csv.DictReader:
    - Escanea el CSV desde el inicio saltando `offset` filas.
    - No usa slicing en memoria ni DataFrame; O(limit) filas retenidas.
    - Completa metadata via `file_meta` en el endpoint REST para evitar recomputos.
    """
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
