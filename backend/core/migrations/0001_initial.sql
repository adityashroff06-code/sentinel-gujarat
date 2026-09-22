-- Schema v1 — docs/api.md Part A (folded with Part B in task S1.1).
-- Every shape change updates docs/api.md in the same commit.

CREATE TABLE cameras (
    camera_id        TEXT PRIMARY KEY,       -- from the catalogue or onboarding, ^[A-Za-z0-9_-]{1,64}$
    department       TEXT,                   -- Health | Police | GSRTC | Panchayat | Municipal | Unknown
    location_name    TEXT,
    lat              REAL,
    lon              REAL,
    bearing_deg      REAL,
    fov_deg          REAL,
    range_m          REAL,
    codec            TEXT,                   -- h264 | hevc
    width            INTEGER,
    height           INTEGER,
    declared_fps     REAL,                   -- as reported — NEVER used for timing
    measured_fps     REAL,
    bitrate_kbps     INTEGER,
    hls_url          TEXT,                   -- no credentials, ever
    rtsp_url_template TEXT,                  -- <email>/<password> placeholders, or a plain local
                                             -- URL; for transport='replay' the local file path
    whep_url_template TEXT,
    transport        TEXT,                   -- hls | rtsp | replay | none
    ownership        TEXT DEFAULT 'government',  -- government | private
    health           TEXT,                   -- online | degraded | offline
    last_seen        TEXT,                   -- ISO8601 UTC
    fps_tier         TEXT DEFAULT 'registered',  -- active | registered
    roi_json         TEXT,                   -- [[x,y],...] normalised 0-1, nullable
    zones_json       TEXT,                   -- zones, docs/api.md §5, nullable
    source           TEXT,                   -- catalogue | manual | csv | api
    notes            TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE INDEX idx_cameras_dept   ON cameras(department);
CREATE INDEX idx_cameras_health ON cameras(health);
CREATE INDEX idx_cameras_tier   ON cameras(fps_tier);

CREATE TABLE sightings (
    sighting_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    plate            TEXT NOT NULL,          -- normalised (docs/api.md §6)
    plate_raw        TEXT NOT NULL,          -- exactly what OCR returned; never overwritten
    plate_canonical  TEXT NOT NULL,          -- ambiguity-folded at write time (§6)
    confidence       REAL NOT NULL,          -- 0.0-1.0
    camera_id        TEXT NOT NULL REFERENCES cameras(camera_id),
    seen_at          TEXT NOT NULL,          -- the STREAM-TIME instant (decision F13)
    wall_time        TEXT NOT NULL,          -- when this system observed it
    clock_source     TEXT NOT NULL,          -- rtsp-live | hls-vod | harvest | demo | replay
    provenance       TEXT NOT NULL,          -- live | harvest | demo | test
    pts_ms           REAL,                   -- raw presentation timestamp, for audit
    bbox_json        TEXT,                   -- [x,y,w,h] in source pixels
    vehicle_class    TEXT,                   -- car | truck | bus | motorcycle | auto | unknown
    crop_path        TEXT,
    frame_path       TEXT,                   -- full frame — ONLY for watchlist hits
    track_id         TEXT,
    created_at       TEXT NOT NULL
);
CREATE INDEX idx_sightings_plate     ON sightings(plate, seen_at);
CREATE INDEX idx_sightings_canonical ON sightings(plate_canonical, seen_at);
CREATE INDEX idx_sightings_camera    ON sightings(camera_id, seen_at);
CREATE INDEX idx_sightings_time      ON sightings(seen_at);

CREATE TABLE watchlist (
    watchlist_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    plate            TEXT NOT NULL UNIQUE,   -- normalised
    plate_canonical  TEXT NOT NULL,
    category         TEXT NOT NULL,          -- stolen_vehicle | wanted_person | missing_person | blacklisted | suspect
    severity         TEXT NOT NULL,          -- high | medium | low
    description      TEXT,
    reason           TEXT,
    authority        TEXT,
    source_ref       TEXT,                   -- notional FIR / case reference
    expires_at       TEXT,                   -- nullable
    active           INTEGER NOT NULL DEFAULT 1,
    added_at         TEXT NOT NULL
);
CREATE INDEX idx_watchlist_canonical ON watchlist(plate_canonical);

CREATE TABLE events (
    event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_id   TEXT NOT NULL REFERENCES cameras(camera_id),
    zone_id     TEXT,
    event_type  TEXT NOT NULL,               -- intrusion | line_cross | object_detected
    object_class TEXT,
    confidence  REAL,
    occurred_at TEXT NOT NULL,               -- stream-time instant
    wall_time   TEXT NOT NULL,
    clock_source TEXT NOT NULL,              -- rtsp-live | hls-vod | harvest | demo | replay
    provenance  TEXT NOT NULL,               -- live | harvest | demo | test
    bbox_json   TEXT,
    crop_path   TEXT
);
CREATE INDEX idx_events_time   ON events(occurred_at);
CREATE INDEX idx_events_camera ON events(camera_id, occurred_at);

CREATE TABLE alerts (
    alert_seq        INTEGER PRIMARY KEY AUTOINCREMENT,  -- SSE cursor; never COUNT(*)+1 (B7)
    alert_id         TEXT NOT NULL UNIQUE,   -- ALERT-YYYYMMDD-NNNN, derived from alert_seq
    kind             TEXT NOT NULL,          -- watchlist | zone
    sighting_id      INTEGER NULL REFERENCES sightings(sighting_id),
    watchlist_id     INTEGER NULL REFERENCES watchlist(watchlist_id),
    event_id         INTEGER NULL REFERENCES events(event_id),
    zone_id          TEXT NULL,
    plate            TEXT NULL,
    plate_canonical  TEXT NULL,
    camera_id        TEXT NOT NULL REFERENCES cameras(camera_id),
    category         TEXT NULL,
    severity         TEXT NOT NULL,          -- high | medium | low | critical
    match_type       TEXT NOT NULL DEFAULT 'none',  -- exact | ambiguity | fuzzy | none
    match_distance   REAL NOT NULL DEFAULT 0,       -- confusion-weighted (§6), fractional
    clock_source     TEXT NOT NULL,          -- cooldowns key on it, same clock domain only
    fired_at         TEXT NOT NULL,          -- stream-time instant (seen_at domain)
    acknowledged_at  TEXT,
    acknowledged_by  TEXT,
    clip_path        TEXT,                   -- Pipeline 3, nullable
    clip_sha256      TEXT
);
CREATE INDEX idx_alerts_fired     ON alerts(fired_at);
CREATE INDEX idx_alerts_canonical ON alerts(plate_canonical, camera_id, fired_at);

CREATE TABLE audit (
    audit_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    at          TEXT NOT NULL,
    actor       TEXT,
    role        TEXT,
    action      TEXT NOT NULL,
    entity      TEXT,
    entity_id   TEXT,
    before_json TEXT,                        -- written by handlers, not middleware
    after_json  TEXT
);
