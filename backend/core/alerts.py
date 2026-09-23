"""Alert creation — one table, watchlist and zone kinds (S2.5; api.md §4).

Cooldown 5 minutes per (``plate_canonical``, ``camera_id``) for watchlist
alerts, per (``zone_id``, ``camera_id``) for zone alerts — **derived from
the last matching ``alerts`` row with the same ``clock_source``**, never
from process memory, so a purge resets it (B7, F34).

``alert_seq`` is the AUTOINCREMENT allocation and the SSE cursor;
``alert_id = ALERT-YYYYMMDD-NNNN`` is derived from it, never counted.

The ordering invariant is the caller's: the sighting (or event) row is
committed before this runs, and the returned row commits before anything
broadcasts (root CLAUDE.md §4).
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Any, Mapping

from backend.core.db import iso
from backend.core.logging_setup import setup

log = setup("alerts")

COOLDOWN_S = 300.0


def _cooled_down(con: sqlite3.Connection, *, kind: str, key_column: str,
                 key_value: str, camera_id: str, clock_source: str,
                 fired_at: datetime) -> bool:
    """True when no matching alert exists within the cooldown window."""
    lo = iso(fired_at - timedelta(seconds=COOLDOWN_S))
    hi = iso(fired_at + timedelta(seconds=COOLDOWN_S))
    row = con.execute(
        f"SELECT alert_seq FROM alerts WHERE kind = ? AND {key_column} = ?"
        "  AND camera_id = ? AND clock_source = ? AND fired_at BETWEEN ? AND ?"
        "  LIMIT 1",
        (kind, key_value, camera_id, clock_source, lo, hi),
    ).fetchone()
    return row is None


def create_alert(
    con: sqlite3.Connection,
    *,
    kind: str,
    camera_id: str,
    severity: str,
    seen_at: datetime,
    clock_source: str,
    sighting: Mapping[str, Any] | None = None,
    wl_row: Mapping[str, Any] | None = None,
    rule: str = "none",
    distance: float = 0.0,
    event: Mapping[str, Any] | None = None,
) -> sqlite3.Row | None:
    """Insert an alert unless its cooldown suppresses it; return the row.

    ``kind='watchlist'`` needs *sighting* and *wl_row*; ``kind='zone'``
    needs *event* (with ``event_id`` and ``zone_id``). Runs inside the
    caller's transaction (the worker's single writer thread) and does not
    commit. Returns None when suppressed. Raises ``ValueError`` for an
    unknown *kind* or missing companion rows.
    """
    fired_iso = iso(seen_at)
    if kind == "watchlist":
        if sighting is None or wl_row is None:
            raise ValueError("watchlist alert needs sighting and wl_row")
        key_column, key_value = "plate_canonical", sighting["plate_canonical"]
    elif kind == "zone":
        if event is None or event.get("zone_id") is None:
            raise ValueError("zone alert needs an event with zone_id")
        key_column, key_value = "zone_id", event["zone_id"]
    else:
        raise ValueError(f"unknown alert kind {kind!r}")

    if not _cooled_down(con, kind=kind, key_column=key_column, key_value=key_value,
                        camera_id=camera_id, clock_source=clock_source,
                        fired_at=seen_at):
        log.debug("alert suppressed by cooldown: %s %s @ %s", kind, key_value, camera_id)
        return None

    placeholder = f"PENDING-{uuid.uuid4().hex}"
    cur = con.execute(
        "INSERT INTO alerts (alert_id, kind, sighting_id, watchlist_id, event_id,"
        " zone_id, plate, plate_canonical, camera_id, category, severity,"
        " match_type, match_distance, clock_source, fired_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            placeholder, kind,
            sighting["sighting_id"] if sighting is not None else None,
            wl_row["watchlist_id"] if wl_row is not None else None,
            event["event_id"] if event is not None else None,
            event["zone_id"] if event is not None else None,
            sighting["plate"] if sighting is not None else None,
            sighting["plate_canonical"] if sighting is not None else None,
            camera_id,
            wl_row["category"] if wl_row is not None else None,
            severity, rule, distance, clock_source, fired_iso,
        ),
    )
    alert_seq = int(cur.lastrowid)
    alert_id = f"ALERT-{fired_iso[:10].replace('-', '')}-{alert_seq:04d}"
    con.execute("UPDATE alerts SET alert_id = ? WHERE alert_seq = ?", (alert_id, alert_seq))
    row = con.execute("SELECT * FROM alerts WHERE alert_seq = ?", (alert_seq,)).fetchone()
    log.info("alert %s: %s %s @ %s severity=%s", alert_id, kind, key_value,
             camera_id, severity)
    return row
