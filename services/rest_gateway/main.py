"""REST gateway entrypoint."""

from __future__ import annotations

import uvicorn

from services.rest_gateway.config import HTTP_PORT


def main() -> None:
    uvicorn.run(
        "services.rest_gateway.app:app",
        host="0.0.0.0",
        port=HTTP_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
