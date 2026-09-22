"""Test environment. Sets throw-away keys and a per-run database path
BEFORE anything imports backend.core.config, and never reads `.env`
(config loads it with override=False, so these environment values win)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="sentinel-tests-"))
os.environ["SENTINEL_DB"] = str(_TMP / "test.db")
os.environ["SENTINEL_LOG_DIR"] = str(_TMP / "logs")
os.environ["SENTINEL_API_KEY_ADMIN"] = "test-admin-key-not-a-secret"
os.environ["SENTINEL_API_KEY_VIEWER"] = "test-viewer-key-not-a-secret"

import pytest

from backend.core import db as dbmod


@pytest.fixture()
def con(tmp_path):
    """A migrated, empty database on a per-test path."""
    con = dbmod.connect(tmp_path / "t.db")
    dbmod.migrate(con)
    yield con
    con.close()
