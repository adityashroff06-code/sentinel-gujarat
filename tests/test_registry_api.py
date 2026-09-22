"""S1.3a acceptance: auth, cookie transport, CRUD, CSV import, gap analysis,
stats, audit — all through TestClient (base_url must be a trusted host)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.core import db as dbmod

FIXTURES = Path(__file__).parent / "fixtures"

ADMIN = {"X-API-Key": "test-admin-key-not-a-secret"}
VIEWER = {"X-API-Key": "test-viewer-key-not-a-secret"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SENTINEL_DB", str(tmp_path / "api.db"))
    con = dbmod.connect()
    dbmod.migrate(con)
    con.close()
    from backend.app.main import app

    # TrustedHostMiddleware rejects the default "testserver" Host.
    with TestClient(app, base_url="http://localhost") as c:
        yield c


def _camera(camera_id="cam90", **overrides):
    body = {
        "camera_id": camera_id,
        "department": "Police",
        "location_name": "Test Junction",
        "lat": 21.52,
        "lon": 70.46,
    }
    body.update(overrides)
    return body


def test_health_is_open(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["db"] == "ok" and set(body["counts"]) >= {"cameras", "sightings", "alerts"}


def test_401_without_key(client):
    assert client.get("/api/cameras").status_code == 401
    assert client.get("/api/stats").status_code == 401
    assert client.post("/api/cameras", json=_camera()).status_code == 401


def test_403_for_viewer_on_post(client):
    r = client.post("/api/cameras", json=_camera(), headers=VIEWER)
    assert r.status_code == 403


def test_cookie_transport(client):
    r = client.post("/api/session", json={"api_key": VIEWER["X-API-Key"]})
    assert r.status_code == 200 and r.json()["role"] == "viewer"
    assert "sentinel_key" in client.cookies

    # Cookie authorises GET /crops/* — a missing file is 404, never 401.
    assert client.get("/crops/x.jpg").status_code == 404
    # ...but never a mutation: /crops has no POST route at all.
    assert client.post("/crops/x.jpg").status_code in (401, 405)
    # ...and not ordinary API GETs either (header-only paths).
    assert client.get("/api/cameras").status_code == 401

    bad = client.post("/api/session", json={"api_key": "wrong"})
    assert bad.status_code == 401


def test_create_conflict_and_validation(client):
    r = client.post("/api/cameras", json=_camera(), headers=ADMIN)
    assert r.status_code == 201
    assert r.json()["camera_id"] == "cam90"

    assert client.post("/api/cameras", json=_camera(), headers=ADMIN).status_code == 409

    bad_department = client.post(
        "/api/cameras", json=_camera("cam91", department="Navy"), headers=ADMIN
    )
    assert bad_department.status_code == 422
    bad_lat = client.post("/api/cameras", json=_camera("cam92", lat=123.0), headers=ADMIN)
    assert bad_lat.status_code == 422
    credential_url = client.post(
        "/api/cameras",
        json=_camera("cam93", rtsp_url_template="rtsp://user:pw@1.2.3.4/x"),
        headers=ADMIN,
    )
    assert credential_url.status_code == 422


def test_patch_and_stream(client):
    client.post("/api/cameras", json=_camera("cam94"), headers=ADMIN)
    r = client.patch(
        "/api/cameras/cam94", json={"health": "online", "fps_tier": "active"}, headers=ADMIN
    )
    assert r.status_code == 200
    assert r.json()["health"] == "online" and r.json()["fps_tier"] == "active"

    stream = client.get("/api/cameras/cam94/stream", headers=VIEWER)
    assert stream.status_code == 200
    assert stream.json() == {"hls": "/api/hls/cam94/live.m3u8"}


def test_csv_import_2_accepted_1_rejected(client):
    with open(FIXTURES / "import_3rows.csv", "rb") as fh:
        r = client.post(
            "/api/cameras/import",
            files={"file": ("import_3rows.csv", fh, "text/csv")},
            headers=ADMIN,
        )
    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] == ["imp01", "imp02"]
    assert len(body["rejected"]) == 1
    assert body["rejected"][0]["row"] == 3 and "lat" in body["rejected"][0]["reason"]
    assert client.get("/api/cameras/imp03", headers=VIEWER).status_code == 404
    assert client.get("/api/cameras/imp01", headers=VIEWER).status_code == 200


def test_list_filters(client):
    client.post("/api/cameras", json=_camera("cam95"), headers=ADMIN)
    client.post(
        "/api/cameras", json=_camera("cam96", department="GSRTC"), headers=ADMIN
    )
    r = client.get("/api/cameras", params={"department": "GSRTC"}, headers=VIEWER)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1 and body["cameras"][0]["camera_id"] == "cam96"


def test_gap_analysis_shape(client):
    client.post("/api/cameras", json=_camera("cam97"), headers=ADMIN)
    client.post(
        "/api/cameras",
        json=_camera("cam98", lat=23.02, lon=72.57, department="Municipal"),
        headers=ADMIN,
    )
    r = client.get("/api/cameras/gap-analysis", headers=VIEWER)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {
        "generated_at", "cameras_total", "online", "active_tier",
        "cameras_offline_or_degraded", "isolated_coverage", "department_summary",
    }
    assert body["cameras_total"] == 2
    # 200+ km apart: both isolated at the 5 km radius.
    assert {c["camera_id"] for c in body["isolated_coverage"]} == {"cam97", "cam98"}
    assert body["isolated_coverage"][0]["radius_km"] == 5.0
    assert body["department_summary"]["Police"]["total"] == 1


def test_stats_keys(client):
    r = client.get("/api/stats", headers=VIEWER)
    assert r.status_code == 200
    assert set(r.json()) == {
        "cameras_online", "cameras_total", "departments", "sightings_total",
        "plates_unique", "events_total", "zone_events", "alerts_active",
    }


def test_audit_row_for_post(client):
    client.post("/api/cameras", json=_camera("cam99"), headers=ADMIN)
    con = dbmod.connect()
    try:
        row = con.execute(
            "SELECT * FROM audit WHERE entity_id = 'cam99' ORDER BY audit_id DESC"
        ).fetchone()
    finally:
        con.close()
    assert row is not None
    assert row["action"].startswith("POST /api/cameras")
    assert row["role"] == "admin"
    assert row["after_json"] is not None and '"cam99"' in row["after_json"]
