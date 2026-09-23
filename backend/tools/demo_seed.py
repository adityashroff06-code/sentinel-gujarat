"""Demo vehicle seeder — labelled, through the real pipeline (S3.1a; C10, F26).

``inject`` drives the hero ``GJ01AB1234`` (watchlisted stolen/high)
through **``record_sighting`` and ``find_match``/``create_alert``** —
the same functions every live read takes — with ``provenance='demo'``,
``clock_source='demo'`` and ``DEMO-`` track ids: three cameras at t,
t+7 min and t+15 min, an ambiguity near-miss ``GJ01A81234`` on the third
at t+21 min, and ~20 background plates. A demo row never passes as a
live one (root rule 12): provenance is stored on every row and the
demo clock domain never mixes with live routes (B6).

``purge`` deletes only ``provenance='demo'`` rows and their alerts;
alerting keeps working afterwards (cooldowns derive from the table, D4).

The three cameras come from the best-working pick once S3.7's
``seed_registry --pick-active`` exists (F49); until a pick is recorded
the pinned fallback is cam06 (GSRTC), cam10 (Municipal), cam09 (Police)
— one geographic cluster, three departments — and the tests pin it.

CLI: ``python -m backend.tools.demo_seed inject|purge [--at ISO8601]``
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timedelta, timezone

from backend.core import db as dbmod
from backend.core.db import utcnow
from backend.core.matcher import WatchlistCache
from ml.worker import process_read

HERO = "GJ01AB1234"
NEAR_MISS = "GJ01A81234"  # 8<->B ambiguity of the hero
# ponytail: pinned fallback until S3.7's probe pick exists (F49)
ROUTE = [("cam06", "GSRTC"), ("cam10", "Municipal"), ("cam09", "Police")]
ROUTE_OFFSETS_MIN = (0, 7, 15)  # elapsed 420 s and 480 s between stops
NEAR_MISS_OFFSET_MIN = 21       # 360 s after the third stop

# Invented, chosen not to exact-, ambiguity- or fuzzy-alert against the
# seeded watchlist (distinct letter pairs and numbers).
BACKGROUND = [
    ("cam06", "GJ01KT4821", "car"), ("cam06", "GJ03RV9034", "truck"),
    ("cam06", "GJ11DN7745", "car"), ("cam06", "GJ05PW3390", "motorcycle"),
    ("cam06", "GJ18HM6017", "bus"), ("cam06", "GJ02TR8852", "car"),
    ("cam06", "GJ25VK1409", "car"), ("cam10", "GJ04MN7263", "truck"),
    ("cam10", "GJ09RA5528", "car"), ("cam10", "GJ15KP9944", "car"),
    ("cam10", "GJ22TR4076", "motorcycle"), ("cam10", "GJ07DN1385", "car"),
    ("cam10", "GJ28HM7621", "bus"), ("cam09", "GJ10RV3849", "car"),
    ("cam09", "GJ17KT6690", "car"), ("cam09", "GJ20PW2277", "truck"),
    ("cam09", "GJ25MN8104", "car"), ("cam09", "GJ13RA4433", "motorcycle"),
    ("cam09", "GJ06VK9752", "car"), ("cam09", "GJ23KP5518", "car"),
]


def _ensure_cameras(con: sqlite3.Connection) -> None:
    """Minimal rows for the fallback cameras when the registry lacks them
    (a fresh test database); a seeded registry is left untouched."""
    now = utcnow()
    for camera_id, department in ROUTE:
        con.execute(
            "INSERT INTO cameras (camera_id, department, created_at, updated_at)"
            " VALUES (?, ?, ?, ?) ON CONFLICT(camera_id) DO NOTHING",
            (camera_id, department, now, now))


def _ensure_hero_watchlisted(con: sqlite3.Connection) -> None:
    con.execute(
        "INSERT INTO watchlist (plate, plate_canonical, category, severity,"
        " description, reason, authority, source_ref, added_at)"
        " SELECT ?, '', 'stolen_vehicle', 'high', 'Demo hero vehicle (C10)',"
        "  'Reported stolen (demonstration)', 'Gujarat Police (demo)',"
        "  'FIR-DEMO-2026-001', ?"
        " WHERE NOT EXISTS (SELECT 1 FROM watchlist WHERE plate = ?)",
        (HERO, utcnow(), HERO))


def inject(con: sqlite3.Connection, at: datetime | None = None) -> dict[str, int]:
    """Purge any previous demo data, then seed the route. Returns counts."""
    purge(con)
    _ensure_cameras(con)
    _ensure_hero_watchlisted(con)
    con.commit()
    cache = WatchlistCache()
    cache.refresh(con)
    t0 = at or (datetime.now(timezone.utc) - timedelta(minutes=NEAR_MISS_OFFSET_MIN + 1))

    counts = {"sightings": 0, "alerts": 0}

    def read(camera_id: str, plate: str, seen: datetime, conf: float,
             vehicle_class: str, track_no: int) -> None:
        _, alert = process_read(
            con, cache, camera_id=camera_id, plate=plate, plate_raw=plate,
            confidence=conf, seen_at=seen, wall_time=seen, clock_source="demo",
            provenance="demo", vehicle_class=vehicle_class,
            track_id=f"DEMO-{camera_id}-{track_no}")
        counts["sightings"] += 1
        counts["alerts"] += 1 if alert is not None else 0

    for (camera_id, _dept), offset in zip(ROUTE, ROUTE_OFFSETS_MIN):
        read(camera_id, HERO, t0 + timedelta(minutes=offset), 0.96, "car", 1)
    read(ROUTE[2][0], NEAR_MISS, t0 + timedelta(minutes=NEAR_MISS_OFFSET_MIN),
         0.88, "car", 2)

    for i, (camera_id, plate, vehicle_class) in enumerate(BACKGROUND):
        seen = t0 - timedelta(minutes=3 * (i + 1))
        read(camera_id, plate, seen, 0.82 + (i % 15) * 0.01, vehicle_class, 100 + i)
    con.commit()
    return counts


def purge(con: sqlite3.Connection) -> dict[str, int]:
    """Delete only demo rows — and their alerts. Nothing else."""
    counts = {}
    counts["alerts"] = con.execute(
        "DELETE FROM alerts WHERE clock_source = 'demo'"
        " OR sighting_id IN (SELECT sighting_id FROM sightings WHERE provenance = 'demo')"
        " OR event_id IN (SELECT event_id FROM events WHERE provenance = 'demo')"
    ).rowcount
    counts["events"] = con.execute(
        "DELETE FROM events WHERE provenance = 'demo'").rowcount
    counts["sightings"] = con.execute(
        "DELETE FROM sightings WHERE provenance = 'demo'").rowcount
    con.commit()
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["inject", "purge"])
    parser.add_argument("--at", help="route start (ISO 8601, aware); default ~22 min ago")
    args = parser.parse_args()
    at = datetime.fromisoformat(args.at) if args.at else None
    if at is not None and at.tzinfo is None:
        parser.error("--at must carry a timezone offset")
    con = dbmod.connect()
    try:
        dbmod.migrate(con)
        if args.action == "inject":
            counts = inject(con, at)
            print(f"demo injected: {counts['sightings']} sightings,"
                  f" {counts['alerts']} alerts (provenance=demo)")
        else:
            counts = purge(con)
            print(f"demo purged: {counts['sightings']} sightings,"
                  f" {counts['events']} events, {counts['alerts']} alerts")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
