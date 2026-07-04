"""Gateway configuration from environment variables."""

from __future__ import annotations

import os

INGEST_TARGET = os.getenv("INGEST_TARGET", "ingest-service:50051")
HTTP_PORT = int(os.getenv("HTTP_PORT", "8080"))
DEFAULT_FILE = os.getenv("DEFAULT_FILE", "/data/transactions.csv")
