"""Demo seeder: labelled rows through the real pipeline (S3.1a pull-forward)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.core.db import utcnow
from backend.core.matcher import WatchlistCache
from backend.tools import demo_seed
from ml.worker import process_read

T0 = datetime(2026, 9, 23, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def seeded(con):
    counts = demo_seed.inject(con, at=T0)
    return con, counts


def test_hero_route_is_three_exact_stops_plus_a_near_miss(seeded) -> None:
    con, counts = seeded
    rows = con.execute(
        "SELECT * FROM sightings WHERE plate_canonical ="
        " (SELECT plate_canonical FROM sightings WHERE plate = ? LIMIT 1)"
        " ORDER BY seen_at", (demo_seed.HERO,)).fetchall()
    assert [r["camera_id"] for r in rows] == ["cam06", "cam10", "cam09", "cam09"]
    assert [r["plate"] for r in rows] == [demo_seed.HERO] * 3 + [demo_seed.NEAR_MISS]
    times = [datetime.fromisoformat(r["seen_at"]) for r in rows]
    assert [(b - a).total_seconds() for a, b in zip(times, times[1:])] == [420.0, 480.0, 360.0]
    assert all(r["track_id"].startswith("DEMO-") for r in rows)


def test_every_row_is_labelled_demo(seeded) -> None:
    con, counts = seeded
    total = con.execute("SELECT COUNT(*) FROM sightings").fetchone()[0]
    demo = con.execute("SELECT COUNT(*) FROM sightings WHERE provenance = 'demo'"
                       " AND clock_source = 'demo'").fetchone()[0]
    assert total == demo == counts["sightings"] == 24  # 4 hero stops + 20 background


def test_alerts_fire_for_the_hero_only(seeded) -> None:
    con, counts = seeded
    alerts = con.execute("SELECT * FROM alerts ORDER BY alert_seq").fetchall()
    assert len(alerts) == counts["alerts"] == 4  # 3 exact + 1 ambiguity
    assert [a["match_type"] for a in alerts] == ["exact", "exact", "exact", "ambiguity"]
    assert all(a["clock_source"] == "demo" and a["severity"] == "high" for a in alerts)


def test_inject_twice_does_not_duplicate(seeded) -> None:
    con, _ = seeded
    demo_seed.inject(con, at=T0 + timedelta(minutes=5))
    assert con.execute("SELECT COUNT(*) FROM sightings").fetchone()[0] == 24
    assert con.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 4


def test_purge_removes_only_demo_rows_and_alerting_still_works(seeded) -> None:
    con, _ = seeded
    # One non-demo sighting through the same path, on a watchlisted plate.
    cache = WatchlistCache()
    cache.refresh(con)
    live_seen = T0 + timedelta(hours=2)
    sighting_id, alert = process_read(
        con, cache, camera_id="cam06", plate=demo_seed.HERO, plate_raw=demo_seed.HERO,
        confidence=0.9, seen_at=live_seen, wall_time=live_seen,
        clock_source="replay", provenance="test", track_id="cam06-9")
    assert alert is not None

    demo_seed.purge(con)
    assert con.execute("SELECT COUNT(*) FROM sightings WHERE provenance = 'demo'"
                       ).fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM alerts WHERE clock_source = 'demo'"
                       ).fetchone()[0] == 0
    survivors = con.execute("SELECT * FROM sightings").fetchall()
    assert [s["sighting_id"] for s in survivors] == [sighting_id]
    assert con.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 1

    # Alerts keep working after the purge (fresh seq, table-derived cooldown).
    later = live_seen + timedelta(minutes=10)
    _, alert2 = process_read(
        con, cache, camera_id="cam06", plate=demo_seed.HERO, plate_raw=demo_seed.HERO,
        confidence=0.9, seen_at=later, wall_time=later,
        clock_source="replay", provenance="test", track_id="cam06-10")
    assert alert2 is not None and alert2["alert_seq"] > alert["alert_seq"]


def test_background_plates_never_alert(con) -> None:
    demo_seed.inject(con, at=T0)
    plates = {a["plate"] for a in con.execute("SELECT plate FROM alerts")}
    assert plates == {demo_seed.HERO, demo_seed.NEAR_MISS}
