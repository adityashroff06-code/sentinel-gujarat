"""Object events — throttled, batched, best-effort (S2.5; F34, B13).

One ``object_detected`` event per camera per class at most every 5 s of
**stream time** (``occurred_at`` domain, never wall clock). Rows are
built here and enqueued as async batches through the supervisor's writer
thread; a lost batch is logged, never fatal. Throttle resets on restart.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Iterable, Sequence

from backend.core.db import iso, utcnow

MIN_GAP_S = 5.0

EVENT_INSERT = (
    "INSERT INTO events (camera_id, zone_id, event_type, object_class,"
    " confidence, occurred_at, wall_time, clock_source, provenance, bbox_json)"
    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


class EventThrottle:
    """Per-class 5 s gate on the stream-time clock; one per camera worker."""

    def __init__(self, min_gap_s: float = MIN_GAP_S) -> None:
        self.min_gap_s = min_gap_s
        self._last: dict[str, float] = {}

    def reset(self) -> None:
        """Forget every class (call on a restart tick — review D12)."""
        self._last.clear()

    def due(self, object_class: str, occurred_at_ts: float) -> bool:
        last = self._last.get(object_class)
        if last is not None and occurred_at_ts - last < self.min_gap_s:
            return False
        self._last[object_class] = occurred_at_ts
        return True


def object_event_row(*, camera_id: str, object_class: str, confidence: float,
                     occurred_at: datetime, wall_time: datetime,
                     clock_source: str, provenance: str,
                     bbox_json: str | None = None) -> tuple:
    """One executemany row for :data:`EVENT_INSERT` (object_detected)."""
    return (camera_id, None, "object_detected", object_class, confidence,
            iso(occurred_at), iso(wall_time), clock_source, provenance, bbox_json)


def insert_events(con: sqlite3.Connection, rows: Iterable[Sequence]) -> int:
    """Batched insert (runs inside the writer thread's transaction)."""
    rows = list(rows)
    if rows:
        con.executemany(EVENT_INSERT, rows)
    return len(rows)


def insert_zone_event(con: sqlite3.Connection, *, camera_id: str, zone_id: str,
                      event_type: str, object_class: str | None,
                      occurred_at: datetime, wall_time: datetime,
                      clock_source: str, provenance: str) -> sqlite3.Row:
    """One zone event (intrusion | line_cross), awaited — an alert may
    reference it, so it is never batched."""
    cur = con.execute(
        EVENT_INSERT,
        (camera_id, zone_id, event_type, object_class, None,
         iso(occurred_at), iso(wall_time), clock_source, provenance, None),
    )
    return con.execute("SELECT * FROM events WHERE event_id = ?",
                       (cur.lastrowid,)).fetchone()
