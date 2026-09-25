"""Demo seeder: labelled rows through the real pipeline (S3.1a pull-forward)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.core.db import utcnow
from backend.core.matcher import WatchlistCache
from backend.tools import demo_seed
from ml.worker import process_read

T0 = datetime(2026, 9, 23, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _demo_crops_in_tmp(tmp_path, monkeypatch):
    """Rendered demo crops go to a per-test directory, never data/crops/."""
    monkeypatch.setattr(demo_seed, "CROPS_ROOT", tmp_path / "crops")
    return tmp_path / "crops"


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


# --- rendered demo crops (ANPR search lane, 25 Sep) ---------------------------

def test_every_demo_sighting_gets_a_rendered_demo_crop(seeded, _demo_crops_in_tmp) -> None:
    from PIL import Image

    from backend.tools import demo_crops

    con, _ = seeded
    rows = con.execute("SELECT sighting_id, plate, crop_path FROM sightings").fetchall()
    assert len(rows) == 24
    for r in rows:
        assert r["crop_path"] == f"data/crops/demo/{r['sighting_id']}.jpg"  # live form
        path = _demo_crops_in_tmp / "demo" / f"{r['sighting_id']}.jpg"
        with Image.open(path) as img:
            assert img.format == "JPEG"
            assert img.size == (demo_crops.WIDTH, demo_crops.PLATE_H + demo_crops.BAND_H)
            # the DEMO band (rule 12 on the image itself): demo orange
            band = img.convert("RGB").getpixel((8, demo_crops.PLATE_H + 3))
            assert all(abs(a - b) <= 24 for a, b in zip(band, (224, 145, 47))), band
    # the API serves it at the live crop URL shape
    from backend.services.route import crop_url
    assert crop_url(rows[0]["crop_path"]) == f"/crops/demo/{rows[0]['sighting_id']}.jpg"


def test_demo_crop_prints_the_registration_as_a_plate() -> None:
    from backend.tools.demo_crops import display_text

    assert display_text("GJ01AB1234") == "GJ 01 AB 1234"
    assert display_text("GJ01A81234") == "GJ 01 AB 1234"   # the plate the misread came from
    assert display_text("22BH1234AA") == "22 BH 1234 AA"
    assert display_text("GJ05JB432") == "GJ05JB432"        # partial: as read


def test_purge_deletes_the_demo_crops_and_nothing_else(seeded, _demo_crops_in_tmp) -> None:
    con, _ = seeded
    demo_dir = _demo_crops_in_tmp / "demo"
    assert len(list(demo_dir.glob("*.jpg"))) == 24
    live_crop = _demo_crops_in_tmp / "cam06" / "217.jpg"   # a live crop beside them
    live_crop.parent.mkdir(parents=True)
    live_crop.write_bytes(b"live")
    stray = demo_dir / "not-referenced.jpg"                 # unreferenced: left alone
    stray.write_bytes(b"x")

    # a demo row whose stored path climbs out of data/crops/demo/ is never followed
    con.execute("UPDATE sightings SET crop_path = 'data/crops/demo/../cam06/217.jpg'"
                " WHERE sighting_id = (SELECT MIN(sighting_id) FROM sightings)")
    con.commit()

    counts = demo_seed.purge(con)
    assert counts["crops"] == 23
    assert sorted(p.name for p in demo_dir.iterdir()) == ["1.jpg", "not-referenced.jpg"]
    assert live_crop.read_bytes() == b"live"


def test_reinject_replaces_the_crops_of_the_previous_run(seeded, _demo_crops_in_tmp) -> None:
    con, _ = seeded
    first = {p.name for p in (_demo_crops_in_tmp / "demo").glob("*.jpg")}
    demo_seed.inject(con, at=T0 + timedelta(minutes=5))
    second = {p.name for p in (_demo_crops_in_tmp / "demo").glob("*.jpg")}
    assert len(second) == 24 and first.isdisjoint(second)   # old files purged
