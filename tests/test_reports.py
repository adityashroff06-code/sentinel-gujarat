"""S3.1b acceptance: report endpoints (docs/api.md §7 report rows, B11, B14).

A ``<script>`` in the plate filter comes back HTML-escaped; a CSV cell
beginning ``=`` is formula-prefix escaped; the provenance column is present
in both formats and in the route report; the gap-analysis report renders;
reports are an evaluator action; the report rate limit answers 429.
"""

from __future__ import annotations

import csv
import io
import urllib.parse

import pytest
from fastapi.testclient import TestClient

import backend.app.main as main_mod
import backend.app.routes_reports as routes_reports
from backend.core import plates
from backend.core import db as dbmod

ADMIN = {"X-API-Key": "test-admin-key-not-a-secret"}
VIEWER = {"X-API-Key": "test-viewer-key-not-a-secret"}

XSS = "<script>alert(1)</script>"
#: A hostile location name: opening the CSV in a spreadsheet must not run it.
FORMULA = "=cmd|' /C calc'!A0"

CAMERAS = [
    ("cam01", "Police", "Naroda Road Junction", 23.0712, 72.6301),
    ("cam02", "GSRTC", FORMULA, 23.0300, 72.5800),
]

SIGHTINGS = [
    # plate, camera, seen_at, clock_source, provenance
    ("GJ01AB1234", "cam01", "2026-09-20T10:00:00+00:00", "rtsp-live", "live"),
    ("GJ01AB1234", "cam02", "2026-09-20T10:10:00+00:00", "demo", "demo"),
    ("GJ05XY9999", "cam01", "2026-09-20T11:00:00+00:00", "replay", "test"),
]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A migrated per-test DB with two cameras and three sightings."""
    monkeypatch.setenv("SENTINEL_DB", str(tmp_path / "reports.db"))
    con = dbmod.connect()
    dbmod.migrate(con)
    now = dbmod.utcnow()
    for camera_id, dept, name, lat, lon in CAMERAS:
        con.execute(
            "INSERT INTO cameras (camera_id, department, location_name, lat, lon,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (camera_id, dept, name, lat, lon, now, now),
        )
    for plate, camera_id, seen_at, clock, provenance in SIGHTINGS:
        con.execute(
            "INSERT INTO sightings (plate, plate_raw, plate_canonical, confidence,"
            " camera_id, seen_at, wall_time, clock_source, provenance,"
            " vehicle_class, created_at)"
            " VALUES (?, ?, ?, 0.9, ?, ?, ?, ?, ?, 'car', ?)",
            (plate, plate, plates.canonical(plate), camera_id, seen_at, seen_at,
             clock, provenance, now),
        )
    con.commit()
    con.close()
    with TestClient(main_mod.create_app(), base_url="http://localhost") as c:
        yield c


# ---------------------------------------------------------------- detections

def test_detections_html_escapes_the_plate_filter(client) -> None:
    """B11: a <script> smuggled through the plate filter renders escaped."""
    r = client.get("/api/reports/detections", params={"plate": XSS}, headers=ADMIN)
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert XSS not in r.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in r.text


def test_detections_html_carries_the_provenance_column(client) -> None:
    r = client.get("/api/reports/detections", headers=ADMIN)
    assert r.status_code == 200
    assert "<th>Provenance</th>" in r.text
    for value in ("live", "demo", "test"):
        assert f">{value}</span>" in r.text
    # The hostile location renders escaped, not raw.
    assert FORMULA not in r.text
    assert "=cmd|&#x27; /C calc&#x27;!A0" in r.text


def test_detections_csv_prefixes_formula_cells_and_has_provenance(client) -> None:
    """B11/B14: '=cmd…' comes back prefixed with ' and provenance is a column."""
    r = client.get("/api/reports/detections", params={"format": "csv"}, headers=ADMIN)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    rows = list(csv.reader(io.StringIO(r.text)))
    header, body = rows[0], rows[1:]
    assert "provenance" in header
    assert len(body) == 3
    prov = {row[header.index("provenance")] for row in body}
    assert prov == {"live", "demo", "test"}
    location = [row[header.index("location")] for row in body if row[header.index("camera_id")] == "cam02"]
    assert location == ["'" + FORMULA]
    assert "'=cmd" in r.text


def test_detections_filters_apply(client) -> None:
    r = client.get(
        "/api/reports/detections",
        params={"format": "csv", "camera_id": "cam01", "plate": "GJ01"},
        headers=ADMIN,
    )
    rows = list(csv.reader(io.StringIO(r.text)))
    assert len(rows) == 2  # header + the single cam01 GJ01AB1234 row
    assert rows[1][csv_index(rows[0], "camera_id")] == "cam01"


def csv_index(header: list[str], name: str) -> int:
    return header.index(name)


# --------------------------------------------------------------------- route

def test_route_report_html_and_csv_carry_provenance(client) -> None:
    r = client.get("/api/reports/route/GJ01AB1234", headers=ADMIN)
    assert r.status_code == 200
    assert "Route Report" in r.text
    assert "<th>Provenance</th>" in r.text
    assert "cam01" in r.text and "cam02" in r.text

    r = client.get(
        "/api/reports/route/GJ01AB1234", params={"format": "csv"}, headers=ADMIN
    )
    assert r.status_code == 200
    rows = list(csv.reader(io.StringIO(r.text)))
    header, body = rows[0], rows[1:]
    assert "provenance" in header and "clock_source" in header
    assert [row[header.index("camera_id")] for row in body] == ["cam01", "cam02"]
    assert [row[header.index("provenance")] for row in body] == ["live", "demo"]


def test_route_report_escapes_a_hostile_plate(client) -> None:
    # No slash: a path segment cannot carry one; the detections test
    # covers the full <script>…</script> payload via the query filter.
    hostile = "<img src=x onerror=alert(1)>"
    r = client.get(f"/api/reports/route/{urllib.parse.quote(hostile, safe='')}",
                   headers=ADMIN)
    assert r.status_code == 200
    assert hostile not in r.text
    assert "&lt;img src=x onerror=alert(1)&gt;" in r.text


# -------------------------------------------------------------- gap analysis

def test_gap_analysis_report_renders(client) -> None:
    r = client.get("/api/reports/gap-analysis", headers=ADMIN)
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Gap Analysis" in r.text
    assert "cam01" in r.text  # health is NULL -> listed offline/degraded


# ---------------------------------------------------------------- auth, 429

def test_reports_are_an_evaluator_action(client) -> None:
    """docs/api.md §7 roles: reports belong to evaluator and above; the
    viewer key reads data, not exports."""
    for path in (
        "/api/reports/detections",
        "/api/reports/route/GJ01AB1234",
        "/api/reports/gap-analysis",
    ):
        assert client.get(path).status_code == 401
        assert client.get(path, headers=VIEWER).status_code == 403
        assert client.get(path, headers=ADMIN).status_code == 200


def test_report_rate_limit_answers_429(client, monkeypatch) -> None:
    """docs/api.md §9: the report exports are rate-limited per identity."""
    limiter = routes_reports._limit_reports
    monkeypatch.setattr(limiter, "limit", 2)
    monkeypatch.setattr(limiter, "_hits", {})
    codes = [
        client.get("/api/reports/gap-analysis", headers=ADMIN).status_code
        for _ in range(3)
    ]
    assert codes == [200, 200, 429]
