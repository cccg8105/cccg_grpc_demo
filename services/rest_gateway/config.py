"""REST gateway configuration."""

from __future__ import annotations

import os

HTTP_PORT = int(os.getenv("HTTP_PORT", "8090"))
REST_INGEST_URL = os.getenv("REST_INGEST_URL", "http://rest-ingest:8091")
DEFAULT_FILE = os.getenv("DEFAULT_FILE", "/data/transactions.csv")
