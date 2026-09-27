"""SQLite access: one connection recipe, ordered migrations.

``connect()`` opens the configured database with the pragmas the contract
requires (WAL, foreign keys, 30 s busy timeout, synchronous=NORMAL).
``migrate()`` applies ``backend/core/migrations/*.sql`` in name order,
recording each in ``schema_version`` — after a ``snapshot()`` of a database
that already holds data (S6.1b: the database is the evidence, so it is
copied before anything changes its shape).

CLI (from the repo root): ``python -m backend.core.db init``
"""

from __future__ import annotations

import logging
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from backend.core import config

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

log = logging.getLogger(__name__)


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


def database_file(con: sqlite3.Connection) -> Path | None:
    """The file behind *con*'s main database; None for an in-memory or
    temporary database (nothing on disk to protect)."""
    for _seq, name, file in con.execute("PRAGMA database_list"):
        if name == "main":
            return Path(file) if file else None
    return None


def backup_dir(db_file: Path) -> Path:
    """Where snapshots of *db_file* go: ``backup/`` beside it — for the
    configured ``data/sentinel.db`` that is ``data/backup/`` (gitignored)."""
    return db_file.parent / "backup"


def snapshot(con: sqlite3.Connection, target: str | Path) -> Path:
    """Write a consistent copy of *con*'s database to *target* with
    ``VACUUM INTO`` (WAL contents included; readers and the worker keep
    running) and return *target*.

    The copy is written to ``<target>.part`` and renamed only once complete,
    so an interrupted snapshot never looks like a good one. Raises
    ``FileExistsError`` if *target* exists (a snapshot is never overwritten)
    and ``sqlite3.Error`` if the copy fails (disk full, a transaction open on
    *con*); the partial file is removed either way."""
    target = Path(target)
    if target.exists():
        raise FileExistsError(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    part.unlink(missing_ok=True)
    try:
        con.execute("VACUUM INTO ?", (str(part),))
        os.replace(part, target)
    finally:
        part.unlink(missing_ok=True)
    return target


def migrate(con: sqlite3.Connection) -> list[int]:
    """Apply pending migrations in order; return the versions applied now.

    If a migration is pending and the database already holds at least one
    applied version, a snapshot is taken first to
    ``backup/<stem>-pre-v<N>.db`` beside the file (N = the first pending
    version). An existing snapshot of that name is kept, not replaced: after
    a failed attempt, the copy from before the first attempt is the one worth
    having. A fresh or in-memory database is not copied. If the snapshot
    fails its error propagates and nothing is migrated."""
    done = set(applied_versions(con))
    pending: list[tuple[int, Path]] = []
    for script in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = int(script.name.split("_", 1)[0])
        if version not in done:
            pending.append((version, script))
    db_file = database_file(con)
    if pending and done and db_file is not None:
        target = backup_dir(db_file) / f"{db_file.stem}-pre-v{pending[0][0]}.db"
        if target.exists():
            log.warning("pre-migration snapshot %s already exists - kept as is", target)
        else:
            snapshot(con, target)
            log.info("pre-migration snapshot written: %s", target)
    applied: list[int] = []
    for version, script in pending:
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
