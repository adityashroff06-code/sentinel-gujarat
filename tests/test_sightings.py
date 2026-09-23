"""S2.4 acceptance: sighting dedupe matrix + provenance (docs/tasks.md)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from backend.core.config import REPO_ROOT
from backend.core.db import utcnow
from backend.core.matcher import WatchlistCache
from ml.anpr.sightings import record_sighting

T0 = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def cam(con):
    con.execute("INSERT INTO cameras (camera_id, created_at, updated_at)"
                " VALUES ('testcam', ?, ?)", (utcnow(), utcnow()))
    con.commit()
    return "testcam"


def _record(con, cam, *, seen=T0, wall=None, conf=0.9, plate="GJ01AB1234",
            clock="replay", **kw):
    return record_sighting(
        con, camera_id=cam, plate=plate, plate_raw=plate, confidence=conf,
        seen_at=seen, wall_time=wall or seen, clock_source=clock,
        provenance="test", **kw)


def _rows(con):
    return con.execute("SELECT * FROM sightings ORDER BY sighting_id").fetchall()


def test_same_plate_30s_later_is_one_row_with_the_higher_confidence(con, cam) -> None:
    sid, inserted = _record(con, cam, conf=0.80)
    assert inserted
    sid2, inserted2 = _record(con, cam, seen=T0 + timedelta(seconds=30), conf=0.95)
    assert (sid2, inserted2) == (sid, False)
    rows = _rows(con)
    assert len(rows) == 1 and rows[0]["confidence"] == 0.95


def test_dedupe_never_lowers_confidence(con, cam) -> None:
    _record(con, cam, conf=0.95)
    _record(con, cam, seen=T0 + timedelta(seconds=30), conf=0.50)
    assert _rows(con)[0]["confidence"] == 0.95


def test_same_plate_61s_later_is_two_rows(con, cam) -> None:
    _record(con, cam)
    _, inserted = _record(con, cam, seen=T0 + timedelta(seconds=61))
    assert inserted and len(_rows(con)) == 2


def test_wall_time_20min_apart_is_a_separate_row(con, cam) -> None:
    _record(con, cam)
    _, inserted = _record(con, cam, seen=T0 + timedelta(seconds=30),
                          wall=T0 - timedelta(minutes=20))
    assert inserted and len(_rows(con)) == 2


def test_different_clock_source_never_dedupes(con, cam) -> None:
    _record(con, cam, clock="replay")
    _, inserted = _record(con, cam, seen=T0 + timedelta(seconds=10), clock="demo")
    assert inserted and len(_rows(con)) == 2


def test_ambiguity_equivalent_plates_dedupe_via_canonical(con, cam) -> None:
    _record(con, cam, plate="GJ01AB1234")
    _, inserted = _record(con, cam, plate="GJ01A81234", seen=T0 + timedelta(seconds=10))
    assert not inserted and len(_rows(con)) == 1


def test_partial_read_is_stored_and_never_alertable(con, cam) -> None:
    sid, inserted = _record(con, cam, plate="GJ05JB432")
    assert inserted
    con.execute(
        "INSERT INTO watchlist (plate, plate_canonical, category, severity, added_at)"
        " VALUES ('GJ05JB4321', '', 'stolen_vehicle', 'high', ?)", (utcnow(),))
    con.commit()
    cache = WatchlistCache()
    cache.refresh(con)
    assert cache.find_match("GJ05JB432") is None  # partial: no fuzzy path (F21)


def test_rows_carry_the_callers_provenance_and_timestamps(con, cam) -> None:
    _record(con, cam)
    row = _rows(con)[0]
    assert row["provenance"] == "test" and row["clock_source"] == "replay"
    assert row["seen_at"] == "2026-09-23T12:00:00+00:00"  # +00:00, seconds


def test_crop_written_small_with_forward_slashes(con, cam) -> None:
    import cv2

    frame = cv2.imread(str(REPO_ROOT / "deliverables/deck/img/feed_cam01.jpg"))
    crop = frame[200:400, 300:600]  # a realistic vehicle-sized crop
    sid, _ = _record(con, cam, crop=crop)
    row = _rows(con)[0]
    assert row["crop_path"] == f"data/crops/testcam/{sid}.jpg"
    path = REPO_ROOT / row["crop_path"]
    try:
        assert path.is_file() and path.stat().st_size < 8192  # ~2 KB class
    finally:
        path.unlink(missing_ok=True)
        try:
            path.parent.rmdir()
        except OSError:
            pass
