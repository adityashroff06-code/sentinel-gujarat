"""GET /api/cameras/activity — the GIS Activity layer's data (docs/api.md §7).

What these prove: the route is reachable (registered before the
``/{camera_id}`` catch-all, which would otherwise answer "camera not
found"); only reads and alerts inside the trailing window count; distinct
plates are counted per camera; and every count is split by provenance so a
demo read never passes as a live one (root rule 12).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.core import db as dbmod

ADMIN = {"X-API-Key": "test-admin-key-not-a-secret"}
VIEWER = {"X-API-Key": "test-viewer-key-not-a-secret"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SENTINEL_DB", str(tmp_path / "activity.db"))
    con = dbmod.connect()
    dbmod.migrate(con)
    now = dbmod.utcnow()
    for cam in ("cam01", "cam02", "cam03"):
        con.execute(
            "INSERT INTO cameras (camera_id, department, created_at, updated_at)"
            " VALUES (?, 'Police', ?, ?)", (cam, now, now))
    con.commit()
    con.close()
    from backend.app.main import app

    with TestClient(app, base_url="http://localhost") as c:
        yield c


def _ago(hours: float) -> str:
    return dbmod.iso(datetime.now(timezone.utc) - timedelta(hours=hours))


def _sighting(con, camera_id: str, plate: str, hours_ago: float,
              provenance: str = "live") -> str:
    """Insert one read; returns its stored seen_at."""
    seen = _ago(hours_ago)
    clock = {"live": "rtsp-live", "demo": "demo", "test": "replay"}[provenance]
    con.execute(
        "INSERT INTO sightings (plate, plate_raw, plate_canonical, confidence,"
        " camera_id, seen_at, wall_time, clock_source, provenance, created_at)"
        " VALUES (?, ?, ?, 0.9, ?, ?, ?, ?, ?, ?)",
        (plate, plate, plate, camera_id, seen, seen, clock, provenance, seen))
    return seen


def _alert(con, camera_id: str, hours_ago: float, seq: int,
           clock_source: str = "rtsp-live", sighting_id: int | None = None,
           event_id: int | None = None) -> None:
    con.execute(
        "INSERT INTO alerts (alert_id, kind, sighting_id, event_id, camera_id,"
        " severity, clock_source, fired_at) VALUES (?, ?, ?, ?, ?, 'high', ?, ?)",
        (f"ALERT-TEST-{seq:04d}", "watchlist" if sighting_id else "zone",
         sighting_id, event_id, camera_id, clock_source, _ago(hours_ago)))


def _last_id(con) -> int:
    return con.execute("SELECT last_insert_rowid()").fetchone()[0]


def _seed(rows) -> None:
    con = dbmod.connect()
    try:
        rows(con)
        con.commit()
    finally:
        con.close()


def test_activity_route_is_not_swallowed_by_the_camera_id_route(client):
    r = client.get("/api/cameras/activity", headers=VIEWER)
    assert r.status_code == 200, r.text
    assert r.json() == []  # no reads yet: an empty list, never "camera not found"


def test_activity_requires_sign_in(client):
    assert client.get("/api/cameras/activity").status_code == 401


def test_activity_counts_only_reads_and_alerts_inside_the_window(client):
    def rows(con):
        _sighting(con, "cam01", "GJ01AB1111", 1)
        _sighting(con, "cam01", "GJ01AB2222", 30)  # outside 24 h
        _alert(con, "cam01", 2, 1)
        _alert(con, "cam01", 40, 2)                 # outside 24 h
    _seed(rows)

    day = {e["camera_id"]: e for e in client.get(
        "/api/cameras/activity", headers=VIEWER).json()}
    assert day["cam01"]["sightings"] == 1
    assert day["cam01"]["alerts"] == 1

    two_days = {e["camera_id"]: e for e in client.get(
        "/api/cameras/activity?hours=48", headers=VIEWER).json()}
    assert two_days["cam01"]["sightings"] == 2
    assert two_days["cam01"]["alerts"] == 2


def test_activity_counts_distinct_plates_and_the_latest_read(client):
    seen: list[str] = []

    def rows(con):
        seen.append(_sighting(con, "cam02", "GJ05CD1234", 3))
        seen.append(_sighting(con, "cam02", "GJ05CD1234", 2))
        seen.append(_sighting(con, "cam02", "GJ06EF5678", 1))
    _seed(rows)

    body = client.get("/api/cameras/activity", headers=VIEWER).json()
    assert [e["camera_id"] for e in body] == ["cam02"]  # idle cameras omitted
    cam02 = body[0]
    assert cam02["sightings"] == 3 and cam02["plates"] == 2
    assert cam02["last_seen"] == seen[2]  # the newest read, stored +00:00 form
    assert cam02["last_seen"].endswith("+00:00")


def test_activity_splits_reads_by_provenance_so_demo_never_passes_as_live(client):
    def rows(con):
        _sighting(con, "cam03", "GJ01AB1234", 1, provenance="demo")
        _sighting(con, "cam03", "GJ01AB9999", 1, provenance="demo")
        _sighting(con, "cam03", "GJ27XY4321", 1, provenance="live")
    _seed(rows)

    cam03 = client.get("/api/cameras/activity", headers=VIEWER).json()[0]
    assert cam03["sightings"] == 3
    assert cam03["by_provenance"] == {"demo": 2, "live": 1}


def test_activity_zone_alert_without_reads_still_listed(client):
    _seed(lambda con: _alert(con, "cam01", 1, 7))
    body = client.get("/api/cameras/activity", headers=VIEWER).json()
    assert body == [{"camera_id": "cam01", "sightings": 0, "plates": 0,
                     "alerts": 1, "last_seen": None, "by_provenance": {},
                     "alerts_by_provenance": {"live": 1}}]


def test_activity_demo_alert_never_counts_as_live_next_to_live_reads(client):
    """Regression (review, 25 Sep; root rule 12): the alert count had no
    provenance split, so on the live DB cam06 answered alerts=1 beside
    by_provenance {demo: 8, live: 122} and the map painted a red "1 alert"
    ring that read as coming from the live reads — the alert was a demo
    one. Alerts are now split in alerts_by_provenance the way reads are."""
    def rows(con):
        _sighting(con, "cam01", "GJ01AB1111", 1, provenance="live")
        _sighting(con, "cam01", "GJ01AB2222", 1, provenance="live")
        _sighting(con, "cam01", "GJ01AB9999", 1, provenance="demo")
        _alert(con, "cam01", 1, 1, clock_source="demo", sighting_id=_last_id(con))
    _seed(rows)

    cam01 = client.get("/api/cameras/activity", headers=VIEWER).json()[0]
    assert cam01["by_provenance"] == {"live": 2, "demo": 1}
    assert cam01["alerts"] == 1
    assert cam01["alerts_by_provenance"] == {"demo": 1}


def test_activity_alert_provenance_follows_its_source_row_then_its_clock(client):
    """A watchlist alert takes its sighting's provenance, a zone alert its
    event's; with neither, the alert's clock_source maps as F26 maps it —
    demo stays demo and an unknown clock is test, never live."""
    def rows(con):
        _sighting(con, "cam02", "GJ05CD1234", 1, provenance="live")
        _alert(con, "cam02", 1, 1, clock_source="rtsp-live", sighting_id=_last_id(con))
        now = _ago(1)
        con.execute(
            "INSERT INTO events (camera_id, zone_id, event_type, occurred_at,"
            " wall_time, clock_source, provenance) VALUES"
            " ('cam02', 'z1', 'intrusion', ?, ?, 'demo', 'demo')", (now, now))
        _alert(con, "cam02", 1, 2, clock_source="demo", event_id=_last_id(con))
        _alert(con, "cam02", 1, 3, clock_source="demo")      # no source row
        _alert(con, "cam02", 1, 4, clock_source="replay")
        _alert(con, "cam02", 1, 5, clock_source="mystery")   # unknown clock
    _seed(rows)

    cam02 = client.get("/api/cameras/activity", headers=VIEWER).json()[0]
    assert cam02["alerts"] == 5
    assert cam02["alerts_by_provenance"] == {"live": 1, "demo": 2, "test": 2}


@pytest.mark.parametrize("hours", [0, 169])
def test_activity_rejects_a_window_outside_one_hour_to_a_week(client, hours):
    r = client.get(f"/api/cameras/activity?hours={hours}", headers=ADMIN)
    assert r.status_code == 422
