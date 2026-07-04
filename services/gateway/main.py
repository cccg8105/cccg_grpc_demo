"""Gateway: REST + SSE for frontend, gRPC client to ingest."""

from __future__ import annotations

import logging

import uvicorn

from services.gateway.app import app
from services.gateway.config import HTTP_PORT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [gateway] %(levelname)s %(message)s",
)


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=HTTP_PORT, log_level="info")


if __name__ == "__main__":
    main()
