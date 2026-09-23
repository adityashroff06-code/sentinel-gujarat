"""S2.5 acceptance: alerts, cooldowns, the D4 purge regression (docs/tasks.md)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.core.db import utcnow
from backend.core.matcher import WatchlistCache
from ml.worker import process_read

T0 = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def env(con):
    """A camera, the hero watchlist row, and a refreshed cache."""
    con.execute("INSERT INTO cameras (camera_id, created_at, updated_at)"
                " VALUES ('cam06', ?, ?)", (utcnow(), utcnow()))
    con.execute(
        "INSERT INTO watchlist (plate, plate_canonical, category, severity, added_at)"
        " VALUES ('GJ01AB1234', '', 'stolen_vehicle', 'high', ?)", (utcnow(),))
    con.commit()
    cache = WatchlistCache()
    cache.refresh(con)
    return con, cache


def _read(con, cache, *, plate="GJ01AB1234", seen=T0, clock="replay"):
    return process_read(
        con, cache, camera_id="cam06", plate=plate, plate_raw=plate,
        confidence=0.9, seen_at=seen, wall_time=seen, clock_source=clock,
        provenance="test", track_id="cam06-1")


def _alerts(con):
    return con.execute("SELECT * FROM alerts ORDER BY alert_seq").fetchall()


def test_watchlisted_plate_fires_exactly_one_alert(env) -> None:
    con, cache = env
    sighting_id, alert = _read(con, cache)
    assert alert is not None
    assert alert["kind"] == "watchlist" and alert["match_type"] == "exact"
    assert alert["sighting_id"] == sighting_id and alert["severity"] == "high"
    assert alert["category"] == "stolen_vehicle"
    assert alert["alert_id"] == "ALERT-20260923-0001"  # derived from alert_seq
    # Four more within 5 minutes of stream time: cooldown holds at one.
    for minutes in (1, 2, 3, 4):
        _, again = _read(con, cache, seen=T0 + timedelta(minutes=minutes))
    assert again is None and len(_alerts(con)) == 1


def test_cooldown_expires_after_five_minutes(env) -> None:
    con, cache = env
    _read(con, cache)
    _, second = _read(con, cache, seen=T0 + timedelta(minutes=5, seconds=1))
    assert second is not None and len(_alerts(con)) == 2


def test_partial_read_never_alerts(env) -> None:
    con, cache = env
    sighting_id, alert = _read(con, cache, plate="GJ01AB123")  # partial
    assert sighting_id and alert is None and _alerts(con) == []


def test_fuzzy_neighbour_never_alerts_by_default(env) -> None:
    con, cache = env
    _, alert = _read(con, cache, plate="GJ01AB1235")
    assert alert is None and _alerts(con) == []


def test_ambiguity_match_alerts(env) -> None:
    con, cache = env
    _, alert = _read(con, cache, plate="GJ01A81234")  # 8 <-> B fold
    assert alert is not None and alert["match_type"] == "ambiguity"


def test_purge_resets_the_cooldown_and_seq_stays_fresh(env) -> None:
    """Regression for D4: ids come from AUTOINCREMENT, never COUNT(*)+1,
    and the cooldown derives from the table, so a purge resets it."""
    con, cache = env
    _read(con, cache)
    first_seq = _alerts(con)[0]["alert_seq"]
    con.execute("DELETE FROM alerts")
    con.commit()
    _, alert = _read(con, cache, seen=T0 + timedelta(seconds=30))
    assert alert is not None, "purge must reset the cooldown"
    assert alert["alert_seq"] > first_seq  # AUTOINCREMENT never reuses
    assert alert["alert_id"].endswith(f"-{alert['alert_seq']:04d}")


def test_cooldown_is_per_clock_source_domain(env) -> None:
    con, cache = env
    _read(con, cache, clock="replay")
    _, alert = _read(con, cache, seen=T0 + timedelta(seconds=30), clock="demo")
    assert alert is not None and len(_alerts(con)) == 2
