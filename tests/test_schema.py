"""S1.1 acceptance: every table, column, enum default and index of schema v1
— extended in S3.0 with the schema v2 auth tables (docs/api.md §9)."""

from __future__ import annotations

import sqlite3

from backend.core import db as dbmod

EXPECTED_COLUMNS = {
    "cameras": {
        "camera_id", "department", "location_name", "lat", "lon", "bearing_deg",
        "fov_deg", "range_m", "codec", "width", "height", "declared_fps",
        "measured_fps", "bitrate_kbps", "hls_url", "rtsp_url_template",
        "whep_url_template", "transport", "ownership", "health", "last_seen",
        "fps_tier", "roi_json", "zones_json", "source", "notes", "created_at",
        "updated_at",
    },
    "sightings": {
        "sighting_id", "plate", "plate_raw", "plate_canonical", "confidence",
        "camera_id", "seen_at", "wall_time", "clock_source", "provenance",
        "pts_ms", "bbox_json", "vehicle_class", "crop_path", "frame_path",
        "track_id", "created_at",
    },
    "watchlist": {
        "watchlist_id", "plate", "plate_canonical", "category", "severity",
        "description", "reason", "authority", "source_ref", "expires_at",
        "active", "added_at",
    },
    "events": {
        "event_id", "camera_id", "zone_id", "event_type", "object_class",
        "confidence", "occurred_at", "wall_time", "clock_source", "provenance",
        "bbox_json", "crop_path",
    },
    "alerts": {
        "alert_seq", "alert_id", "kind", "sighting_id", "watchlist_id",
        "event_id", "zone_id", "plate", "plate_canonical", "camera_id",
        "category", "severity", "match_type", "match_distance", "clock_source",
        "fired_at", "acknowledged_at", "acknowledged_by", "clip_path",
        "clip_sha256",
    },
    "audit": {
        "audit_id", "at", "actor", "role", "action", "entity", "entity_id",
        "before_json", "after_json",
    },
    # schema v2 (0002_auth.sql — docs/api.md §9, task S3.0)
    "users": {
        "user_id", "username", "password_hash", "role", "active",
        "created_at", "last_login",
    },
    "sessions": {
        "session_id", "user_id", "issued_at", "expires_at", "revoked_at",
        "user_agent",
    },
    "login_attempts": {"key", "failures", "locked_until"},
    "schema_version": {"version", "applied_at"},
}

EXPECTED_INDEXES = {
    "idx_cameras_dept", "idx_cameras_health", "idx_cameras_tier",
    "idx_sightings_plate", "idx_sightings_canonical", "idx_sightings_camera",
    "idx_sightings_time", "idx_watchlist_canonical", "idx_events_time",
    "idx_events_camera", "idx_alerts_fired", "idx_alerts_canonical",
    "idx_sessions_user",
}

NOT_NULL = {
    "sightings": {"plate", "plate_raw", "plate_canonical", "confidence", "camera_id",
                  "seen_at", "wall_time", "clock_source", "provenance", "created_at"},
    "events": {"camera_id", "event_type", "occurred_at", "wall_time", "clock_source",
               "provenance"},
    "alerts": {"alert_id", "kind", "camera_id", "severity", "match_type",
               "match_distance", "clock_source", "fired_at"},
    "watchlist": {"plate", "plate_canonical", "category", "severity", "active", "added_at"},
    "audit": {"at", "action"},
    "users": {"username", "password_hash", "role", "active", "created_at"},
    "sessions": {"user_id", "issued_at", "expires_at"},
}


def _columns(con: sqlite3.Connection, table: str) -> dict[str, sqlite3.Row]:
    return {r["name"]: r for r in con.execute(f"PRAGMA table_info({table})")}


def test_tables_and_columns(con):
    tables = {
        r["name"]
        for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        if not r["name"].startswith("sqlite_")
    }
    assert tables == set(EXPECTED_COLUMNS)
    for table, expected in EXPECTED_COLUMNS.items():
        assert set(_columns(con, table)) == expected, f"columns of {table}"


def test_not_null_and_defaults(con):
    for table, cols in NOT_NULL.items():
        info = _columns(con, table)
        for col in cols:
            assert info[col]["notnull"] == 1, f"{table}.{col} must be NOT NULL"
    alerts = _columns(con, "alerts")
    assert alerts["match_type"]["dflt_value"] == "'none'"
    assert alerts["match_distance"]["dflt_value"] == "0"
    cameras = _columns(con, "cameras")
    assert cameras["ownership"]["dflt_value"] == "'government'"
    assert cameras["fps_tier"]["dflt_value"] == "'registered'"
    watchlist = _columns(con, "watchlist")
    assert watchlist["active"]["dflt_value"] == "1"


def test_indexes(con):
    names = {
        r["name"]
        for r in con.execute("SELECT name FROM sqlite_master WHERE type='index'")
        if not r["name"].startswith("sqlite_")
    }
    assert EXPECTED_INDEXES <= names
    canonical = con.execute(
        "SELECT sql FROM sqlite_master WHERE name='idx_sightings_canonical'"
    ).fetchone()["sql"]
    assert "plate_canonical" in canonical and "seen_at" in canonical


def test_autoincrement_and_foreign_keys(con):
    for table in ("sightings", "watchlist", "events", "alerts", "audit"):
        sql = con.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()["sql"]
        assert "AUTOINCREMENT" in sql, f"{table} primary key must be AUTOINCREMENT"
    fks = {r["table"] for r in con.execute("PRAGMA foreign_key_list(alerts)")}
    assert fks == {"sightings", "watchlist", "events", "cameras"}
    assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_pragmas_and_migration_idempotent(con):
    assert con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert con.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
    assert dbmod.migrate(con) == []  # second run applies nothing
    versions = [r["version"] for r in con.execute("SELECT version FROM schema_version")]
    assert versions == [1, 2]  # schema v2: 0002_auth.sql (S3.0)


def test_zone_alert_can_exist_without_sighting(con):
    now = dbmod.utcnow()
    con.execute(
        "INSERT INTO cameras (camera_id, created_at, updated_at) VALUES ('cam01', ?, ?)",
        (now, now),
    )
    con.execute(
        "INSERT INTO events (camera_id, zone_id, event_type, occurred_at, wall_time,"
        " clock_source, provenance) VALUES ('cam01', 'z1', 'intrusion', ?, ?, 'replay', 'test')",
        (now, now),
    )
    con.execute(
        "INSERT INTO alerts (alert_id, kind, event_id, zone_id, camera_id, severity,"
        " clock_source, fired_at) VALUES ('ALERT-20260922-0001', 'zone', 1, 'z1',"
        " 'cam01', 'high', 'replay', ?)",
        (now,),
    )
    row = con.execute("SELECT * FROM alerts").fetchone()
    assert row["kind"] == "zone" and row["sighting_id"] is None
    assert row["match_type"] == "none" and row["match_distance"] == 0.0
