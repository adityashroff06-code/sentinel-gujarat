"""Health (open) and stats (docs/api.md §7)."""

from __future__ import annotations

import json
import sqlite3
from typing import Iterator

from fastapi import APIRouter, Depends

from backend.app import schemas
from backend.app import routes_analytics
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


def _worker_count() -> int:
    """Alive workers from the same supervisor snapshot ``GET /api/workers``
    serves (S3.1b fix: this was hardcoded 0); 0 when no snapshot exists."""
    try:
        data = json.loads(
            routes_analytics._worker_stats_path().read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return 0
    cameras = data.get("cameras") if isinstance(data, dict) else None
    if not isinstance(cameras, dict):
        return 0
    return sum(1 for v in cameras.values() if isinstance(v, dict) and v.get("alive"))


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
            "workers": _worker_count(),
        },
    }


@router.get("/stats", response_model=schemas.StatsOut)
def stats(con: sqlite3.Connection = Depends(get_db), _: str = Depends(require_auth)):
    """Dashboard header counts."""
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
