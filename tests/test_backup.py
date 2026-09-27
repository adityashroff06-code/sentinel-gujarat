"""S6.1b — the database is copied before it changes and on demand.

``backend.core.db.migrate()`` snapshots a database that already holds data
before applying a pending migration; ``scripts/backup_db.py`` takes the same
``VACUUM INTO`` copy on demand, proves it opens read-only with the live
tables, and keeps the newest N. Everything runs on tmp_path databases.
"""

from __future__ import annotations

import importlib.util
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.core import db as dbmod

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_backup_script():
    spec = importlib.util.spec_from_file_location(
        "backup_db", REPO_ROOT / "scripts" / "backup_db.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def bk():
    return _load_backup_script()


def _db_at_v1(path: Path) -> sqlite3.Connection:
    """A database with only migration 0001 applied and one row of evidence
    in a table no migration touches — the shape of a live DB before an
    upgrade."""
    con = dbmod.connect(path)
    dbmod.applied_versions(con)
    first = sorted(dbmod.MIGRATIONS_DIR.glob("*.sql"))[0]
    con.executescript(first.read_text(encoding="utf-8"))
    con.execute("INSERT INTO schema_version (version, applied_at) VALUES (1, ?)",
                (dbmod.utcnow(),))
    con.execute("CREATE TABLE evidence (plate TEXT)")
    con.execute("INSERT INTO evidence VALUES ('GJ01AB1234')")
    con.commit()
    return con


def _versions(path: Path) -> list[int]:
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        return [r[0] for r in con.execute("SELECT version FROM schema_version ORDER BY 1")]
    finally:
        con.close()


# ------------------------------------------------------ migrate() snapshot

def test_migrate_snapshots_a_database_with_data_before_upgrading(tmp_path):
    db = tmp_path / "sentinel.db"
    con = _db_at_v1(db)
    applied = dbmod.migrate(con)
    con.close()

    snap = tmp_path / "backup" / "sentinel-pre-v2.db"
    assert applied and applied[0] == 2
    assert snap.is_file()
    assert _versions(snap) == [1], "the snapshot is the database BEFORE the migration"
    assert _versions(db)[:2] == [1, 2]
    ro = sqlite3.connect(f"file:{snap.as_posix()}?mode=ro", uri=True)
    assert ro.execute("SELECT plate FROM evidence").fetchall() == [("GJ01AB1234",)]
    ro.close()
    assert not list((tmp_path / "backup").glob("*.part"))


def test_fresh_and_up_to_date_databases_are_not_copied(tmp_path):
    db = tmp_path / "fresh.db"
    con = dbmod.connect(db)
    dbmod.migrate(con)  # fresh: nothing worth copying
    assert not (tmp_path / "backup").exists()
    assert dbmod.migrate(con) == []  # nothing pending: nothing copied
    con.close()
    assert not (tmp_path / "backup").exists()


def test_in_memory_database_migrates_without_a_snapshot():
    con = sqlite3.connect(":memory:")
    assert dbmod.database_file(con) is None
    dbmod.migrate(con)
    assert dbmod.migrate(con) == []
    con.close()


def test_an_existing_pre_migration_snapshot_is_kept_not_replaced(tmp_path):
    db = tmp_path / "sentinel.db"
    con = _db_at_v1(db)
    snap = tmp_path / "backup" / "sentinel-pre-v2.db"
    snap.parent.mkdir()
    snap.write_bytes(b"the copy from before the first attempt")
    dbmod.migrate(con)
    con.close()
    assert snap.read_bytes() == b"the copy from before the first attempt"
    assert 2 in _versions(db)


def test_a_failed_snapshot_blocks_the_migration(tmp_path, monkeypatch):
    db = tmp_path / "sentinel.db"
    con = _db_at_v1(db)

    def disk_full(con, target):
        raise sqlite3.OperationalError("database or disk is full")

    monkeypatch.setattr(dbmod, "snapshot", disk_full)
    with pytest.raises(sqlite3.OperationalError):
        dbmod.migrate(con)
    con.close()
    assert _versions(db) == [1], "nothing migrates without its snapshot"


def test_snapshot_never_overwrites_and_leaves_no_partial_file(tmp_path):
    con = dbmod.connect(tmp_path / "a.db")
    dbmod.migrate(con)
    target = tmp_path / "copy.db"
    dbmod.snapshot(con, target)
    with pytest.raises(FileExistsError):
        dbmod.snapshot(con, target)
    con.execute("BEGIN")
    con.execute("INSERT INTO schema_version VALUES (999, 'x')")
    with pytest.raises(sqlite3.OperationalError):  # VACUUM inside a transaction
        dbmod.snapshot(con, tmp_path / "second.db")
    con.rollback()
    con.close()
    assert not (tmp_path / "second.db").exists()
    assert not list(tmp_path.glob("*.part"))


# ------------------------------------------------------ scripts/backup_db.py

def test_backup_script_writes_a_verified_read_only_snapshot(bk, tmp_path, capsys):
    db = tmp_path / "sentinel.db"
    con = _db_at_v1(db)
    dbmod.migrate(con)
    con.close()

    assert bk.main(["--db", str(db)]) == 0
    out = capsys.readouterr().out
    snaps = bk.periodic_snapshots(tmp_path / "backup", db)
    assert len(snaps) == 1
    assert "integrity_check: ok" in out
    assert "since the snapshot" not in out, "nothing wrote in between: counts equal"
    ro = bk.open_read_only(snaps[0])
    with pytest.raises(sqlite3.OperationalError):
        ro.execute("DELETE FROM evidence")
    ro.close()
    live = sqlite3.connect(db)
    assert bk.table_counts(bk.open_read_only(snaps[0])) == bk.table_counts(live)
    live.close()


def test_rotation_keeps_the_newest_and_never_touches_other_snapshots(bk, tmp_path):
    db = tmp_path / "sentinel.db"
    backup = tmp_path / "backup"
    backup.mkdir()
    t0 = datetime(2026, 9, 27, 1, 0, tzinfo=timezone.utc)
    for i in range(9):
        (backup / bk.snapshot_name(db, t0 + timedelta(hours=i))).write_bytes(b"x")
    (backup / "sentinel-pre-v2.db").write_bytes(b"x")
    (backup / "sentinel-pre-renormalise-20260925T120000Z.db").write_bytes(b"x")

    deleted = bk.rotate(backup, db, keep=7)

    assert [p.name for p in deleted] == [bk.snapshot_name(db, t0),
                                         bk.snapshot_name(db, t0 + timedelta(hours=1))]
    assert len(bk.periodic_snapshots(backup, db)) == 7
    assert (backup / "sentinel-pre-v2.db").exists()
    assert (backup / "sentinel-pre-renormalise-20260925T120000Z.db").exists()
    with pytest.raises(ValueError):
        bk.rotate(backup, db, keep=0)


def test_a_snapshot_that_does_not_verify_is_removed(bk, tmp_path, monkeypatch, capsys):
    db = tmp_path / "sentinel.db"
    con = dbmod.connect(db)
    dbmod.migrate(con)
    con.close()

    def garbage(con, target):
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        Path(target).write_bytes(b"not a database at all" * 100)
        return Path(target)

    monkeypatch.setattr(bk.dbmod, "snapshot", garbage)
    assert bk.main(["--db", str(db)]) == 1
    assert bk.periodic_snapshots(tmp_path / "backup", db) == []
    assert "did not verify" in capsys.readouterr().err


def test_backup_script_usage_errors(bk, tmp_path, capsys):
    assert bk.main(["--db", str(tmp_path / "absent.db")]) == 2
    with pytest.raises(SystemExit) as exc:
        bk.main(["--db", str(tmp_path / "absent.db"), "--keep", "0"])
    assert exc.value.code == 2
