"""S3.1a acceptance: analytics API field-for-field against docs/api.md §7.

Route response for the seeded demo scenario, fuzzy neighbour, mixed clock
sources (warning, no cross-group speed), the SSE tailer (subscribe →
insert → receive within 4 s; purge; insert; receive again; Last-Event-ID
replay), pagination totals honouring filters, and purge → alerts empty →
a new sighting alerts again.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.core import db as dbmod
from backend.core.matcher import WatchlistCache
from backend.tools import demo_seed
from ml.worker import process_read

ADMIN = {"X-API-Key": "test-admin-key-not-a-secret"}
VIEWER = {"X-API-Key": "test-viewer-key-not-a-secret"}

T0 = datetime(2026, 9, 23, 10, 0, 0, tzinfo=timezone.utc)

# The pinned demo cluster (decision F55) with the committed seed geography
# (data/camera_seed.csv), so the route legs have real distances and the
# implied speeds stay plausible.
CAMERAS = [
    ("cam06", "GSRTC", "Timbavadi Gate Junagadh", 21.4922, 70.4530),
    ("cam09", "Police", "New Bypass Circle Junagadh", 21.5480, 70.4890),
    ("cam10", "Municipal", "Char Chowk Road Junagadh", 21.5250, 70.4580),
]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A migrated per-test DB with the demo cluster's geography, and a
    TestClient on it (base_url must be a trusted host)."""
    monkeypatch.setenv("SENTINEL_DB", str(tmp_path / "api.db"))
    con = dbmod.connect()
    dbmod.migrate(con)
    now = dbmod.utcnow()
    for camera_id, dept, name, lat, lon in CAMERAS:
        con.execute(
            "INSERT INTO cameras (camera_id, department, location_name, lat, lon,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (camera_id, dept, name, lat, lon, now, now),
        )
    con.commit()
    con.close()
    from backend.app.main import app

    with TestClient(app, base_url="http://localhost") as c:
        yield c


@pytest.fixture()
def seeded(client):
    """The demo scenario injected through the real pipeline (C10)."""
    con = dbmod.connect()
    try:
        demo_seed.inject(con, at=T0)
    finally:
        con.close()
    return client


def _read(con, cache, camera_id, plate, seen, *, clock="demo", provenance="demo",
          conf=0.9, track="TEST-1"):
    """One read through the real pipeline (record → match → alert)."""
    return process_read(
        con, cache, camera_id=camera_id, plate=plate, plate_raw=plate,
        confidence=conf, seen_at=seen, wall_time=seen, clock_source=clock,
        provenance=provenance, track_id=track)


def _pipeline_read(camera_id, plate, seen, **kw):
    """A read on its own connection; returns the alert row (or None)."""
    con = dbmod.connect()
    try:
        cache = WatchlistCache()
        cache.refresh(con)
        _, alert = _read(con, cache, camera_id, plate, seen, **kw)
        return alert
    finally:
        con.close()


# ------------------------------------------------------------------ the route

def test_route_field_for_field_for_the_seeded_scenario(seeded) -> None:
    r = seeded.get("/api/plates/GJ01AB1234/route", headers=VIEWER)
    assert r.status_code == 200
    body = r.json()

    assert body["query_plate"] == "GJ01AB1234"
    assert body["normalised"] == "GJ01AB1234"
    assert body["match_mode"] == "ambiguity"          # the near miss widens it
    assert body["total_sightings"] == 4
    assert body["first_seen"] == "2026-09-23T10:00:00+00:00"
    assert body["last_seen"] == "2026-09-23T10:21:00+00:00"
    assert body["duration_seconds"] == 1260
    assert body["departments_crossed"] == ["GSRTC", "Municipal", "Police"]
    assert body["gaps"] == []
    assert body["warnings"] == []
    assert 5.0 < body["distance_km"] < 10.0           # the Junagadh cluster

    stops = body["stops"]
    assert [s["sequence"] for s in stops] == [1, 2, 3, 4]
    assert [s["camera_id"] for s in stops] == ["cam06", "cam10", "cam09", "cam09"]
    assert [s["match_type"] for s in stops] == ["exact", "exact", "exact", "ambiguity"]
    assert [s["elapsed_from_previous_s"] for s in stops] == [None, 420, 480, 360]
    speeds = [s["implied_speed_kmh"] for s in stops]
    assert speeds[0] is None
    assert 20 < speeds[1] < 45 and 20 < speeds[2] < 45   # plausible
    assert speeds[3] == 0.0                              # same camera
    for s in stops:
        assert s["clock_source"] == "demo" and s["provenance"] == "demo"
        assert s["suspect"] is False
        assert s["match_distance"] == 0.0
        assert s["lat"] is not None and s["lon"] is not None
        assert s["department"] and s["location_name"]
        assert s["confidence"] > 0.8
    assert stops[3]["plate_raw"] == demo_seed.NEAR_MISS


def test_fuzzy_neighbour_appears_as_a_flagged_stop(seeded) -> None:
    # GJ01AB1235: one plain substitution -> confusion-weighted distance 1.0.
    assert _pipeline_read("cam09", "GJ01AB1235", T0 + timedelta(minutes=30),
                          track="TEST-F1") is None      # fuzzy never alerts (F21)
    body = seeded.get("/api/plates/GJ01AB1234/route", headers=VIEWER).json()
    assert body["match_mode"] == "fuzzy"
    assert body["total_sightings"] == 5
    last = body["stops"][-1]
    assert last["plate_raw"] == "GJ01AB1235"
    assert last["match_type"] == "fuzzy"
    assert last["match_distance"] == 1.0
    # 9 minutes after the near miss on the same clock -> a flagged gap.
    assert body["gaps"] == [
        {"after_sequence": 4, "minutes": 9, "note": "no camera coverage on this corridor"}
    ]


def test_mixed_clock_sources_warn_and_never_cross_speed(seeded) -> None:
    _pipeline_read("cam06", demo_seed.HERO, T0 + timedelta(minutes=40),
                   clock="replay", provenance="test", track="TEST-M1")
    body = seeded.get("/api/plates/GJ01AB1234/route", headers=VIEWER).json()
    stops = body["stops"]
    assert len(stops) == 5
    assert stops[-1]["clock_source"] == "replay"
    assert stops[-1]["elapsed_from_previous_s"] is None
    assert stops[-1]["implied_speed_kmh"] is None
    assert len(body["warnings"]) == 1
    warning = body["warnings"][0]
    assert "different clock" in warning and "replay" in warning and "4-5" in warning


def test_suspect_flag_on_implausible_speed(seeded) -> None:
    t = T0 + timedelta(hours=3)
    _pipeline_read("cam06", "GJ05ZZ9999", t, track="TEST-S1")
    _pipeline_read("cam09", "GJ05ZZ9999", t + timedelta(seconds=30), track="TEST-S2")
    body = seeded.get("/api/plates/GJ05ZZ9999/route", headers=VIEWER).json()
    assert [s["suspect"] for s in body["stops"]] == [False, True]
    assert body["stops"][1]["implied_speed_kmh"] > 150


def test_route_for_an_unknown_plate_is_empty_not_an_error(client) -> None:
    body = client.get("/api/plates/GJ99ZZ0000/route", headers=VIEWER).json()
    assert body["match_mode"] == "none" and body["stops"] == []
    assert body["total_sightings"] == 0 and body["distance_km"] == 0.0
    assert body["first_seen"] is None and body["duration_seconds"] is None
    assert body["departments_crossed"] == [] and body["warnings"] == []


# ------------------------------------------------------------------ sightings

def test_sightings_filters_and_pagination_total(seeded) -> None:
    c = seeded
    r = c.get("/api/sightings", headers=VIEWER).json()
    assert r["total"] == 24 and r["count"] == 24

    # total honours the same WHERE as the rows (B11).
    r = c.get("/api/sightings?camera_id=cam06&limit=3", headers=VIEWER).json()
    assert r["total"] == 8 and r["count"] == 3
    assert all(s["camera_id"] == "cam06" for s in r["sightings"])
    r = c.get("/api/sightings?camera_id=cam06&limit=3&offset=6", headers=VIEWER).json()
    assert r["total"] == 8 and r["count"] == 2

    r = c.get("/api/sightings?plate=GJ01AB1234", headers=VIEWER).json()
    assert r["total"] == 3            # the near miss GJ01A81234 does not match

    assert c.get("/api/sightings?provenance=demo", headers=VIEWER).json()["total"] == 24
    r = c.get("/api/sightings?provenance=live", headers=VIEWER).json()
    assert r["total"] == 0 and r["sightings"] == []

    # 'Z' canonicalised at the boundary; background rows are before T0.
    r = c.get("/api/sightings?from=2026-09-23T10:00:00Z", headers=VIEWER).json()
    assert r["total"] == 4

    r = c.get("/api/sightings?min_confidence=0.94", headers=VIEWER).json()
    assert r["total"] == 6            # 3 hero stops + 3 background >= 0.94

    ordered = [s["seen_at"] for s in c.get("/api/sightings?limit=5", headers=VIEWER).json()["sightings"]]
    assert ordered == sorted(ordered, reverse=True)   # newest first


# ------------------------------------------------------------------ watchlist

def test_watchlist_crud_and_roles(seeded) -> None:
    c = seeded
    rows = c.get("/api/watchlist", headers=VIEWER).json()
    assert any(w["plate"] == demo_seed.HERO for w in rows)

    body = {"plate": "gj 18 ab 9999", "category": "suspect", "severity": "medium",
            "description": "test entry"}
    assert c.post("/api/watchlist", json=body, headers=VIEWER).status_code == 403
    r = c.post("/api/watchlist", json=body, headers=ADMIN)
    assert r.status_code == 201
    row = r.json()
    assert row["plate"] == "GJ18AB9999"                # normalised at the boundary
    assert row["plate_canonical"] == "6J18A89999"      # canonical-folded
    assert c.post("/api/watchlist", json=body, headers=ADMIN).status_code == 409

    wid = row["watchlist_id"]
    assert c.delete(f"/api/watchlist/{wid}", headers=VIEWER).status_code == 403
    r = c.delete(f"/api/watchlist/{wid}", headers=ADMIN)
    assert r.status_code == 200 and r.json() == {"deleted": wid}
    assert c.delete(f"/api/watchlist/{wid}", headers=ADMIN).status_code == 404

    bad = dict(body, plate="???")
    assert c.post("/api/watchlist", json=bad, headers=ADMIN).status_code == 422


# --------------------------------------------------------------------- alerts

def test_alerts_list_filters_ack_and_purge_cycle(seeded) -> None:
    c = seeded
    alerts = c.get("/api/alerts", headers=VIEWER).json()
    assert len(alerts) == 4
    assert all(a["kind"] == "watchlist" and a["severity"] == "high" for a in alerts)
    assert all(a["department"] for a in alerts)        # camera join present
    seqs = [a["alert_seq"] for a in alerts]
    assert seqs == sorted(seqs, reverse=True)          # newest first

    assert len(c.get("/api/alerts?severity=high", headers=VIEWER).json()) == 4
    assert c.get("/api/alerts?severity=low", headers=VIEWER).json() == []
    assert len(c.get("/api/alerts?kind=watchlist", headers=VIEWER).json()) == 4
    assert c.get("/api/alerts?kind=zone", headers=VIEWER).json() == []
    assert len(c.get("/api/alerts?limit=2", headers=VIEWER).json()) == 2
    assert len(c.get("/api/alerts?acknowledged=false", headers=VIEWER).json()) == 4
    assert c.get("/api/alerts?acknowledged=true", headers=VIEWER).json() == []

    # Acknowledge persists the actor; viewers may not acknowledge.
    target = alerts[0]
    assert c.post(f"/api/alerts/{target['alert_id']}/ack", headers=VIEWER).status_code == 403
    r = c.post(f"/api/alerts/{target['alert_id']}/ack", headers=ADMIN)
    assert r.status_code == 200
    acked = r.json()
    assert acked["acknowledged_at"] and acked["acknowledged_by"]
    # ...and by numeric alert_seq too.
    assert c.post(f"/api/alerts/{alerts[1]['alert_seq']}/ack", headers=ADMIN).status_code == 200
    assert len(c.get("/api/alerts?acknowledged=true", headers=VIEWER).json()) == 2
    assert c.post("/api/alerts/ALERT-NOPE/ack", headers=ADMIN).status_code == 404

    # After purge the alerts list is empty, and a new sighting alerts again
    # (cooldowns derive from the table, so the purge reset them — B7).
    con = dbmod.connect()
    try:
        demo_seed.purge(con)
    finally:
        con.close()
    assert c.get("/api/alerts", headers=VIEWER).json() == []
    alert = _pipeline_read("cam06", demo_seed.HERO, T0 + timedelta(hours=1),
                           track="DEMO-cam06-9")
    assert alert is not None
    fresh = c.get("/api/alerts", headers=VIEWER).json()
    assert len(fresh) == 1 and fresh[0]["plate"] == demo_seed.HERO


# ------------------------------------------------------------------ SSE
#
# The TestClient's transport runs the ASGI app to completion, so an
# unbounded SSE stream cannot be consumed through it. These tests drive
# the app object directly over the ASGI interface instead — in-process,
# no port bound — which is exactly what a real server does.

class _SseStream:
    """One open SSE request against the raw ASGI app."""

    def __init__(self, app, headers: dict[str, str]):
        self._app = app
        self._headers = headers
        self._inbox: asyncio.Queue = asyncio.Queue()
        self._disconnected = asyncio.Event()
        self._request_sent = False
        self._task: asyncio.Task | None = None
        self._buffer = ""
        self.status: int | None = None

    async def _receive(self):
        if not self._request_sent:
            self._request_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await self._disconnected.wait()
        return {"type": "http.disconnect"}

    async def _send(self, message):
        await self._inbox.put(message)

    async def open(self) -> "_SseStream":
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/alerts/stream",
            "raw_path": b"/api/alerts/stream",
            "query_string": b"",
            "root_path": "",
            "headers": [(b"host", b"localhost")]
            + [(k.lower().encode(), v.encode()) for k, v in self._headers.items()],
            "client": ("testclient", 50000),
            "server": ("localhost", 80),
        }
        self._task = asyncio.create_task(self._app(scope, self._receive, self._send))
        start = await asyncio.wait_for(self._inbox.get(), 10)
        assert start["type"] == "http.response.start"
        self.status = start["status"]
        return self

    async def next_frame(self, timeout: float = 20.0) -> str:
        """The next whole SSE frame (ends with a blank line)."""
        deadline = asyncio.get_running_loop().time() + timeout
        while "\n\n" not in self._buffer:
            remaining = deadline - asyncio.get_running_loop().time()
            msg = await asyncio.wait_for(self._inbox.get(), max(0.1, remaining))
            if msg["type"] == "http.response.body":
                self._buffer += msg.get("body", b"").decode("utf-8")
        frame, self._buffer = self._buffer.split("\n\n", 1)
        return frame

    async def next_alert(self, timeout: float = 20.0) -> tuple[int, dict]:
        """Skip comments/keepalives; return (id, payload) of the next alert."""
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            frame = await self.next_frame(max(0.1, remaining))
            if frame.startswith(":"):
                continue
            lines = frame.split("\n")
            frame_id = int(next(l[4:] for l in lines if l.startswith("id: ")))
            payload = json.loads(next(l[6:] for l in lines if l.startswith("data: ")))
            return frame_id, payload

    async def close(self) -> None:
        self._disconnected.set()
        try:
            await asyncio.wait_for(self._task, 5)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            self._task.cancel()


def test_sse_receive_purge_reinsert_and_last_event_id_replay(seeded) -> None:
    from backend.app.main import app

    async def scenario():
        # Subscribe -> insert -> receive within 4 s (the tailer polls every 2 s).
        s1 = await _SseStream(app, VIEWER).open()
        assert s1.status == 200
        assert (await s1.next_frame()) == ": connected"
        started = time.monotonic()
        alert = await asyncio.to_thread(
            _pipeline_read, "cam10", demo_seed.HERO, T0 + timedelta(hours=2),
            track="DEMO-sse-1")
        assert alert is not None
        frame_id, payload = await s1.next_alert()
        elapsed = time.monotonic() - started
        assert elapsed < 4.0, f"alert arrived after {elapsed:.1f}s"
        assert frame_id == alert["alert_seq"]
        assert payload["plate"] == demo_seed.HERO
        assert payload["alert_seq"] == alert["alert_seq"]
        await s1.close()
        first_seq = alert["alert_seq"]

        # Purge, insert, receive again (AUTOINCREMENT keeps the cursor
        # monotonic, so the tailer survives the purge).
        def _purge():
            con = dbmod.connect()
            try:
                demo_seed.purge(con)
            finally:
                con.close()

        await asyncio.to_thread(_purge)
        s2 = await _SseStream(app, VIEWER).open()
        assert (await s2.next_frame()) == ": connected"
        alert2 = await asyncio.to_thread(
            _pipeline_read, "cam09", demo_seed.HERO, T0 + timedelta(hours=4),
            track="DEMO-sse-2")
        assert alert2 is not None and alert2["alert_seq"] > first_seq
        frame_id, payload = await s2.next_alert()
        assert frame_id == alert2["alert_seq"]
        assert payload["camera_id"] == "cam09"
        await s2.close()

        # Reconnect with Last-Event-ID -> the gap replays from the table at
        # once, without waiting for a poll tick.
        headers = dict(VIEWER)
        headers["Last-Event-ID"] = str(first_seq)
        s3 = await _SseStream(app, headers).open()
        assert (await s3.next_frame()) == ": connected"
        started = time.monotonic()
        frame_id, payload = await s3.next_alert(timeout=5.0)
        assert time.monotonic() - started < 1.0        # replayed, not polled
        assert frame_id == alert2["alert_seq"]
        assert payload["plate"] == demo_seed.HERO
        await s3.close()

    asyncio.run(scenario())


def test_sse_accepts_the_session_cookie_and_rejects_anonymous(seeded) -> None:
    from backend.app.main import app

    c = seeded
    assert c.get("/api/alerts/stream").status_code == 401
    # POST /api/session sets the cookie to the validated key (F23).
    r = c.post("/api/session", json={"api_key": VIEWER["X-API-Key"]})
    assert r.status_code == 200

    async def scenario():
        cookie = {"Cookie": f"sentinel_key={VIEWER['X-API-Key']}"}
        s = await _SseStream(app, cookie).open()       # cookie only, no header
        assert s.status == 200
        assert (await s.next_frame()) == ": connected"
        await s.close()

    asyncio.run(scenario())


# --------------------------------------------------------------------- events

def test_events_list_and_summary(seeded) -> None:
    con = dbmod.connect()
    try:
        rows = [
            ("cam06", None, "object_detected", "car", 0.9, T0),
            ("cam06", None, "object_detected", "person", 0.8, T0 + timedelta(minutes=1)),
            ("cam09", "z1", "intrusion", "person", 0.7, T0 + timedelta(minutes=2)),
            # Outside the 60-minute window anchored at the newest event:
            ("cam06", None, "object_detected", "car", 0.9, T0 - timedelta(hours=3)),
        ]
        for camera_id, zone_id, etype, oclass, conf, at in rows:
            con.execute(
                "INSERT INTO events (camera_id, zone_id, event_type, object_class,"
                " confidence, occurred_at, wall_time, clock_source, provenance)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, 'demo', 'demo')",
                (camera_id, zone_id, etype, oclass, conf, dbmod.iso(at), dbmod.iso(at)),
            )
        con.commit()
    finally:
        con.close()

    c = seeded
    assert len(c.get("/api/events", headers=VIEWER).json()) == 4
    assert len(c.get("/api/events?camera_id=cam06", headers=VIEWER).json()) == 3
    assert len(c.get("/api/events?event_type=intrusion", headers=VIEWER).json()) == 1
    ts = [e["occurred_at"] for e in c.get("/api/events", headers=VIEWER).json()]
    assert ts == sorted(ts, reverse=True)

    s = c.get("/api/events/summary?minutes=60", headers=VIEWER).json()
    assert s["minutes"] == 60 and s["total"] == 3      # the -3h row is outside
    assert s["cameras"]["cam06"]["objects"] == {"car": 1, "person": 1}
    assert s["cameras"]["cam09"]["intrusion"] == 1
    assert s["cameras"]["cam09"]["line_cross"] == 0


# -------------------------------------------------------------------- workers

def test_workers_snapshot(client, tmp_path, monkeypatch) -> None:
    from backend.app import routes_analytics

    missing = tmp_path / "missing.json"
    monkeypatch.setattr(routes_analytics, "_worker_stats_path", lambda: missing)
    r = client.get("/api/workers", headers=VIEWER)
    assert r.status_code == 200 and r.json()["available"] is False

    snap = tmp_path / "worker_stats.json"
    snap.write_text(json.dumps({
        "written_at": "2026-09-24T10:00:00+00:00", "uptime_s": 600.0,
        "fps_sustained": 11.5, "motion_skip_rate": 0.4,
        "detections_per_min": 42.0, "sightings": 12, "alerts": 1,
        "zone_events": 0, "cameras": {"cam06": {"frames": 1800, "alive": True}},
    }), encoding="utf-8")
    monkeypatch.setattr(routes_analytics, "_worker_stats_path", lambda: snap)
    body = client.get("/api/workers", headers=VIEWER).json()
    assert body["available"] is True
    assert body["fps_sustained"] == 11.5
    assert body["cameras"]["cam06"]["alive"] is True


# ----------------------------------------------------------------------- auth

def test_every_analytics_path_rejects_anonymous(client) -> None:
    for path in (
        "/api/sightings",
        "/api/plates/GJ01AB1234/route",
        "/api/watchlist",
        "/api/alerts",
        "/api/events",
        "/api/events/summary",
        "/api/workers",
    ):
        assert client.get(path).status_code == 401, path
