"""Rotating, credential-masked logging for every process (root CLAUDE.md §7).

``setup(name)`` returns a logger writing to ``data/logs/<name>.log``
(5 × 10 MB rotation) and stderr. Every formatted record passes through
:func:`backend.core.config.masked`, so a credential can never reach a log
file even if a caller forgets to mask (root rule 1).
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from backend.core import config

_MAX_BYTES = 10 * 1024 * 1024
_BACKUPS = 5
_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


class _MaskingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return config.masked(super().format(record))


def setup(name: str) -> logging.Logger:
    """Configure and return the logger *name*. Idempotent — calling twice
    does not duplicate handlers. Raises OSError if the log dir cannot be
    created."""
    logger = logging.getLogger(name)
    if getattr(logger, "_sentinel_configured", False):
        return logger

    log_dir = config.log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = _MaskingFormatter(_FORMAT)
    file_handler = RotatingFileHandler(
        log_dir / f"{name}.log", maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8"
    )
    stderr_handler = logging.StreamHandler(sys.stderr)
    for handler in (file_handler, stderr_handler):
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(config.log_level())
    logger._sentinel_configured = True  # type: ignore[attr-defined]
    return logger
