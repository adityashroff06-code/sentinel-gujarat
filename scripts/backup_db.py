"""Snapshot the platform database on demand and keep the last few (S6.1b).

Takes the same consistent copy ``migrate()`` takes before a schema change
(``backend.core.db.snapshot``: ``VACUUM INTO``, safe while the API and the
worker are writing), then proves it: the copy is opened **read-only**, must
pass ``PRAGMA integrity_check`` and hold the same tables as the live
database, and its row counts are printed beside the live ones. Live counts
may be higher by the rows written since the snapshot; that is reported, not
failed.

Snapshots are ``<backup dir>/<stem>-<UTC stamp>.db`` — for the configured
database, ``data/backup/sentinel-20260927T101500Z.db`` (gitignored). Only
these periodic snapshots are rotated; the pre-migration
(``*-pre-v<N>.db``) and pre-renormalise copies are never deleted here.

Usage::

    .venv/Scripts/python scripts/backup_db.py [--db PATH] [--dir PATH] [--keep 7]

Exit codes: 0 snapshot written and verified; 1 snapshot failed or did not
verify (a bad copy is removed, never kept as the newest); 2 no database.
"""

from __future__ import annotations

import argparse
import logging
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.core import config, db as dbmod  # noqa: E402

log = logging.getLogger("backup")

DEFAULT_KEEP = 7
_STAMP = "%Y%m%dT%H%M%SZ"


def snapshot_name(db_file: Path, now: datetime | None = None) -> str:
    """``<stem>-<UTC stamp>.db`` for *db_file* at *now* (default: now)."""
    now = now or datetime.now(timezone.utc)
    return f"{db_file.stem}-{now.astimezone(timezone.utc).strftime(_STAMP)}.db"


def periodic_snapshots(backup_dir: Path, db_file: Path) -> list[Path]:
    """This tool's snapshots of *db_file* in *backup_dir*, oldest first.
    Pre-migration and any other snapshot names do not match."""
    pattern = re.compile(re.escape(db_file.stem) + r"-\d{8}T\d{6}Z\.db")
    if not backup_dir.is_dir():
        return []
    return sorted(p for p in backup_dir.iterdir() if pattern.fullmatch(p.name))


def rotate(backup_dir: Path, db_file: Path, keep: int) -> list[Path]:
    """Delete all but the newest *keep* periodic snapshots; return the
    deleted paths. Raises ValueError if *keep* < 1 (never delete them all)."""
    if keep < 1:
        raise ValueError("keep must be at least 1")
    old = periodic_snapshots(backup_dir, db_file)[:-keep]
    for p in old:
        p.unlink()
    return old


def table_counts(con: sqlite3.Connection) -> dict[str, int]:
    """Row count of every table in *con*'s main database, by name."""
    names = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
        " AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {n: con.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in names}


def open_read_only(path: Path) -> sqlite3.Connection:
    """Open *path* read-only (URI ``mode=ro``): nothing can write to it."""
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)


def verify(snap: Path, live: dict[str, int]) -> tuple[bool, list[str]]:
    """Check *snap* opens read-only, passes ``integrity_check`` and holds
    exactly the tables in *live* (name -> count). Returns (ok, report lines);
    never raises for a bad copy — a sqlite3.Error is a failed verification."""
    try:
        con = open_read_only(snap)
        try:
            integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
            counts = table_counts(con)
        finally:
            con.close()
    except sqlite3.Error as exc:
        return False, [f"snapshot unreadable: {exc}"]
    lines = [f"integrity_check: {integrity}"]
    ok = integrity == "ok"
    if set(counts) != set(live):
        ok = False
        lines.append(f"TABLES DIFFER: only in snapshot {sorted(set(counts) - set(live))},"
                     f" only in live {sorted(set(live) - set(counts))}")
    width = max((len(n) for n in counts), default=5)
    lines.append(f"{'table':<{width}}  {'snapshot':>9}  {'live':>9}")
    for name in sorted(counts):
        snap_n, live_n = counts[name], live.get(name)
        note = ""
        if live_n is not None and live_n != snap_n:
            note = f"  ({live_n - snap_n:+d} since the snapshot)"
        lines.append(f"{name:<{width}}  {snap_n:>9}  {live_n if live_n is not None else '-':>9}{note}")
    return ok, lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Snapshot the platform database (VACUUM INTO), verify it, keep the last N.")
    parser.add_argument("--db", help="database path (default: SENTINEL_DB)")
    parser.add_argument("--dir", help="backup directory (default: backup/ beside the database)")
    parser.add_argument("--keep", type=int, default=DEFAULT_KEEP,
                        help=f"periodic snapshots to keep (default {DEFAULT_KEEP})")
    args = parser.parse_args(argv)
    if args.keep < 1:
        parser.error("--keep must be at least 1")

    db_file = Path(args.db) if args.db else config.db_path()
    if not db_file.is_file():
        print(f"no database at {db_file}", file=sys.stderr)
        return 2
    backup_dir = Path(args.dir) if args.dir else dbmod.backup_dir(db_file)
    target = backup_dir / snapshot_name(db_file)

    con = dbmod.connect(db_file)
    try:
        try:
            dbmod.snapshot(con, target)
        except (sqlite3.Error, OSError) as exc:
            log.error("snapshot of %s failed: %s", db_file, exc)
            print(f"FAILED: snapshot of {db_file} -> {target}: {exc}", file=sys.stderr)
            return 1
        live = table_counts(con)
    finally:
        con.close()

    ok, lines = verify(target, live)
    print(f"snapshot : {target} ({target.stat().st_size / 1e6:.1f} MB)")
    for line in lines:
        print(f"           {line}")
    if not ok:
        target.unlink(missing_ok=True)
        log.error("snapshot %s did not verify - removed", target)
        print("FAILED: the snapshot did not verify and was removed", file=sys.stderr)
        return 1
    deleted = rotate(backup_dir, db_file, args.keep)
    kept = periodic_snapshots(backup_dir, db_file)
    log.info("snapshot %s verified; %d kept, %d rotated out", target, len(kept), len(deleted))
    print(f"kept     : {len(kept)} periodic snapshot(s) in {backup_dir}"
          + (f"; rotated out {', '.join(p.name for p in deleted)}" if deleted else ""))
    return 0


if __name__ == "__main__":
    from backend.core.logging_setup import setup
    setup("backup")
    sys.exit(main())
