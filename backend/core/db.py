"""SQLite access: one connection recipe, ordered migrations.

``connect()`` opens the configured database with the pragmas the contract
requires (WAL, foreign keys, 30 s busy timeout, synchronous=NORMAL).
``migrate()`` applies ``backend/core/migrations/*.sql`` in name order,
recording each in ``schema_version``.

CLI (from the repo root): ``python -m backend.core.db init``
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from backend.core import config

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def utcnow() -> str:
    """The stored timestamp form: timezone-aware UTC ISO 8601, +00:00."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def iso(ts: datetime) -> str:
    """Canonicalise an aware datetime to the stored +00:00 seconds form."""
    return ts.astimezone(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open *db_path* (default: the configured database) with the binding
    pragmas. Creates the parent directory if needed."""
    path = Path(db_path) if db_path is not None else config.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: FastAPI runs a sync dependency's teardown in
    # a different anyio worker thread than its body under concurrent
    # requests, so ``con.close()`` in ``get_db`` otherwise raises
    # ProgrammingError and 500s the request (found by scripts/
    # smoke_frontend.py, S3.2 — the Header stats poll racing a page load).
    # Each connection is still used by one request at a time, and CPython's
    # sqlite3 is threadsafety=3 (serialized).
    con = sqlite3.connect(path, timeout=30, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=30000")
    con.execute("PRAGMA synchronous=NORMAL")
    return con


def applied_versions(con: sqlite3.Connection) -> list[int]:
    con.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        " version INTEGER PRIMARY KEY,"
        " applied_at TEXT NOT NULL)"
    )
    return [row[0] for row in con.execute("SELECT version FROM schema_version ORDER BY version")]


def migrate(con: sqlite3.Connection) -> list[int]:
    """Apply pending migrations in order; return the versions applied now."""
    done = set(applied_versions(con))
    applied: list[int] = []
    for script in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = int(script.name.split("_", 1)[0])
        if version in done:
            continue
        con.executescript(script.read_text(encoding="utf-8"))
        con.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (version, utcnow()),
        )
        con.commit()
        applied.append(version)
    return applied


def init() -> Path:
    """Create/upgrade the configured database; return its path."""
    con = connect()
    try:
        applied = migrate(con)
    finally:
        con.close()
    path = config.db_path()
    print(f"{path}: schema at version(s) {applied_versions(connect(path))}, applied now: {applied or 'none'}")
    return path


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "init":
        init()
    else:
        print("usage: python -m backend.core.db init", file=sys.stderr)
        raise SystemExit(2)
