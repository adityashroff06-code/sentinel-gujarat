"""Run the API: ``python -m backend.app`` (the venv's python — protocol §5)."""

from __future__ import annotations

import uvicorn

from backend.core import config, logging_setup


def main() -> None:
    logging_setup.setup("api")
    uvicorn.run(
        "backend.app.main:app",
        host="127.0.0.1",
        port=config.api_port(),
        log_level=config.log_level().lower(),
    )


if __name__ == "__main__":
    main()
