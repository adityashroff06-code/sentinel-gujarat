"""Health (open) and stats (docs/api.md §7)."""

from __future__ import annotations

import sqlite3
from typing import Iterator

from fastapi import APIRouter, Depends

from backend.app import schemas
from backend.app.auth import require_auth
from backend.core import db as dbmod

router = APIRouter(prefix="/api", tags=["meta"])


def get_db() -> Iterator[sqlite3.Connection]:
    con = dbmod.connect()
    try:
        yield con
    finally:
        con.close()


def _count(con: sqlite3.Connection, sql: str) -> int:
    try:
        return con.execute(sql).fetchone()[0]
    except sqlite3.Error:
        return 0


@router.get("/health", response_model=schemas.HealthOut)
def health(con: sqlite3.Connection = Depends(get_db)):
    """Open endpoint — no auth (docs/api.md §7 open paths)."""
    try:
        con.execute("SELECT 1")
        db_status = "ok"
    except sqlite3.Error as exc:
        db_status = f"error: {exc}"
    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "db": db_status,
        "time": dbmod.utcnow(),
        "counts": {
            "cameras": _count(con, "SELECT COUNT(*) FROM cameras"),
            "sightings": _count(con, "SELECT COUNT(*) FROM sightings"),
            "alerts": _count(con, "SELECT COUNT(*) FROM alerts"),
            "workers": 0,  # the supervisor snapshot lands in S3.1a
        },
    }


@router.get("/stats", response_model=schemas.StatsOut)
def stats(con: sqlite3.Connection = Depends(get_db), _: str = Depends(require_auth)):
    return {
        "cameras_online": _count(con, "SELECT COUNT(*) FROM cameras WHERE health = 'online'"),
        "cameras_total": _count(con, "SELECT COUNT(*) FROM cameras"),
        "departments": _count(
            con, "SELECT COUNT(DISTINCT department) FROM cameras WHERE department IS NOT NULL"
        ),
        "sightings_total": _count(con, "SELECT COUNT(*) FROM sightings"),
        "plates_unique": _count(con, "SELECT COUNT(DISTINCT plate_canonical) FROM sightings"),
        "events_total": _count(con, "SELECT COUNT(*) FROM events"),
        "zone_events": _count(
            con, "SELECT COUNT(*) FROM events WHERE event_type IN ('intrusion', 'line_cross')"
        ),
        "alerts_active": _count(con, "SELECT COUNT(*) FROM alerts WHERE acknowledged_at IS NULL"),
    }
