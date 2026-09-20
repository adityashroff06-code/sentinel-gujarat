# 03 — Data contracts (BINDING)

Every module reads and writes these shapes. **Changing a field name, type or meaning requires updating this file in the same commit.** This document is what lets independently-written components fit together on the first run.

Rules that apply everywhere:

- All timestamps are **timezone-aware UTC, ISO 8601** in storage. Convert to local only at the display layer. A naive datetime is a bug.
- All plates are stored **normalised** (see §6) alongside the raw OCR output. Never overwrite the raw.
- SQLite runs in **WAL mode** with `foreign_keys=ON`.
- No URL containing a credential is ever stored. Store templates with `<email>` / `<password>` placeholders; build real URLs in memory from environment variables.

---

## 1. `cameras` — the Model 1 registry

```sql
CREATE TABLE cameras (
    camera_id        TEXT PRIMARY KEY,       -- 'cam01' — from the catalogue, never invented
    department       TEXT,                   -- Health | Police | GSRTC | Panchayat | Municipal | Unknown
    location_name    TEXT,                   -- human label, e.g. 'Naroda Road Junction'
    lat              REAL,
    lon              REAL,
    bearing_deg      REAL,                   -- direction camera faces, 0=N, nullable
    fov_deg          REAL,                   -- field of view, nullable
    range_m          REAL,                   -- effective range, nullable
    codec            TEXT,                   -- h264 | hevc
    width            INTEGER,
    height           INTEGER,
    declared_fps     REAL,                   -- as reported — NEVER used for timing
    measured_fps     REAL,                   -- counted over a wall-clock window
    bitrate_kbps     INTEGER,
    hls_url          TEXT,                   -- no credentials
    rtsp_url_template TEXT,                  -- with <email>/<password> placeholders
    whep_url_template TEXT,
    transport        TEXT,                   -- hls | rtsp | none
    ownership        TEXT DEFAULT 'government',  -- government | private
    health           TEXT,                   -- online | degraded | offline
    last_seen        TEXT,                   -- ISO8601 UTC
    fps_tier         TEXT DEFAULT 'registered',  -- active | registered
    roi_json         TEXT,                   -- JSON polygon [[x,y],...] normalised 0-1, nullable
    zones_json       TEXT,                   -- JSON intrusion zones, nullable — see §5
    source           TEXT,                   -- catalogue | manual | csv | api
    notes            TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE INDEX idx_cameras_dept   ON cameras(department);
CREATE INDEX idx_cameras_health ON cameras(health);
CREATE INDEX idx_cameras_tier   ON cameras(fps_tier);
```

**Department and coordinates:** if the catalogue supplies them, use them verbatim. If it does not, assign them once in a committed seed file (`data/camera_seed.csv`), never silently in code, and state in the submission that geography was assigned for demonstration because the catalogue did not carry it. Do not fabricate it invisibly.

---

## 2. `sightings` — every plate read, the spine of the whole system

```sql
CREATE TABLE sightings (
    sighting_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    plate            TEXT NOT NULL,          -- normalised
    plate_raw        TEXT NOT NULL,          -- exactly what OCR returned
    confidence       REAL NOT NULL,          -- 0.0-1.0
    camera_id        TEXT NOT NULL REFERENCES cameras(camera_id),
    seen_at          TEXT NOT NULL,          -- ISO8601 UTC, derived from PTS + stream epoch
    pts_ms           REAL,                   -- raw presentation timestamp, for audit
    bbox_json        TEXT,                   -- [x,y,w,h] in source pixels
    vehicle_class    TEXT,                   -- car | truck | bus | motorcycle | auto | unknown
    crop_path        TEXT,                   -- plate crop on disk (~2 KB)
    frame_path       TEXT,                   -- full frame — ONLY for watchlist hits
    track_id         TEXT,                   -- within-camera tracker id
    created_at       TEXT NOT NULL
);
CREATE INDEX idx_sightings_plate  ON sightings(plate, seen_at);
CREATE INDEX idx_sightings_camera ON sightings(camera_id, seen_at);
CREATE INDEX idx_sightings_time   ON sightings(seen_at);
```

**Dedupe rule (mandatory):** the same normalised plate on the same camera within **60 seconds** is one sighting, not many. Update the existing row's confidence if the new read is better; do not insert. Without this, a parked vehicle produces hundreds of rows and the route view becomes unreadable.

**`seen_at` derivation:** take the stream's wall-clock anchor at connect, add the PTS delta. Never use `datetime.now()` at the moment of detection — inference latency and GOP replay both corrupt it.

---

## 3. `watchlist`

```sql
CREATE TABLE watchlist (
    watchlist_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    plate            TEXT NOT NULL UNIQUE,   -- normalised
    category         TEXT NOT NULL,          -- stolen_vehicle | wanted_person | missing_person | blacklisted | suspect
    severity         TEXT NOT NULL,          -- high | medium | low
    description      TEXT,
    source_ref       TEXT,                   -- notional FIR / case reference
    active           INTEGER NOT NULL DEFAULT 1,
    added_at         TEXT NOT NULL
);
```

Representative data created by us, which the rules permit. Seed it partly from **plates actually observed in the feeds** so the demo produces genuine hits, and partly from invented entries so the table looks like a real watchlist. Record in `plan/STATUS.md` which entries were seeded from observation.

---

## 4. `alerts`

```sql
CREATE TABLE alerts (
    alert_id         TEXT PRIMARY KEY,       -- ALERT-YYYYMMDD-NNNN
    sighting_id      INTEGER NOT NULL REFERENCES sightings(sighting_id),
    watchlist_id     INTEGER NOT NULL REFERENCES watchlist(watchlist_id),
    plate            TEXT NOT NULL,
    camera_id        TEXT NOT NULL,
    category         TEXT NOT NULL,
    severity         TEXT NOT NULL,
    match_type       TEXT NOT NULL,          -- exact | fuzzy
    match_distance   INTEGER NOT NULL DEFAULT 0,
    fired_at         TEXT NOT NULL,
    acknowledged_at  TEXT,
    acknowledged_by  TEXT,
    clip_path        TEXT,                   -- Pipeline 3, nullable
    clip_sha256      TEXT
);
CREATE INDEX idx_alerts_fired ON alerts(fired_at);
```

**Ordering invariant:** the sighting row is committed **before** the matcher runs. An alert always references a sighting that already exists on disk. Never the reverse.

---

## 5. Camera zones (P5, intrusion detection)

`cameras.zones_json`:

```json
[{"zone_id":"z1","name":"Platform edge","type":"intrusion","polygon":[[0.1,0.6],[0.9,0.6],[0.9,1.0],[0.1,1.0]],"classes":["person"]},
 {"zone_id":"z2","name":"Exit lane","type":"line_cross","line":[[0.0,0.5],[1.0,0.5]],"direction":"down","classes":["car","truck"]}]
```

Coordinates normalised 0–1 so they survive resolution differences. `events` table for zone hits:

```sql
CREATE TABLE events (
    event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_id   TEXT NOT NULL REFERENCES cameras(camera_id),
    zone_id     TEXT,
    event_type  TEXT NOT NULL,               -- intrusion | line_cross | object_detected
    object_class TEXT,
    confidence  REAL,
    occurred_at TEXT NOT NULL,
    bbox_json   TEXT,
    crop_path   TEXT
);
```

---

## 6. Plate normalisation (one implementation, `src/anpr/plates.py`)

Indian plate format: `SS DD LL NNNN` — two-letter state, two-digit district, one-to-three-letter series, four-digit number. Gujarat plates begin `GJ`.

```
normalise(raw):
  uppercase, strip everything that is not A-Z0-9
  return the cleaned string
```

**Ambiguity map, applied only during matching, never during storage:**

```
O ↔ 0    I ↔ 1    S ↔ 5    B ↔ 8    Z ↔ 2    G ↔ 6    Q ↔ 0
```

`plate_match(a, b) -> (bool, distance)`:
1. Exact match after normalisation → `(True, 0)`.
2. Equal length, differing only by ambiguity-map substitutions → `(True, 0)`.
3. Levenshtein distance ≤ 1 with both strings ≥ 8 characters → `(True, 1)`.
4. Otherwise `(False, n)`.

Reads shorter than 8 characters are **partial**: store them with their confidence, but never fire an alert from them. They may still contribute to route reconstruction as low-confidence candidates, clearly labelled as such in the UI.

---

## 7. API surface (FastAPI, prefix `/api`)

| Method | Path | Returns |
|---|---|---|
| GET | `/health` | service status, DB status, active worker count |
| GET | `/cameras` | list; filters `department`, `health`, `tier`, `q` |
| GET | `/cameras/{camera_id}` | one camera, full record |
| POST | `/cameras` | manual onboarding (Model 1 deliverable) |
| POST | `/cameras/import` | CSV bulk onboarding (Model 1 deliverable) |
| PATCH | `/cameras/{camera_id}` | edit metadata, ROI, zones, tier |
| GET | `/cameras/gap-analysis` | uncovered areas + ageing/offline cameras (Model 1 deliverable) |
| GET | `/cameras/{camera_id}/stream` | playable HLS URL for this session |
| GET | `/sightings` | filters `plate`, `camera_id`, `from`, `to`, `min_confidence`; paginated |
| GET | `/plates/{plate}/route` | **the scored endpoint** — see below |
| GET | `/watchlist` · POST · DELETE `/{id}` | watchlist CRUD |
| GET | `/alerts` | recent alerts, filters `severity`, `acknowledged` |
| POST | `/alerts/{alert_id}/ack` | acknowledge |
| GET | `/alerts/stream` | **SSE** — live alert push to the dashboard |
| GET | `/events` | zone/object events (P5) |
| GET | `/stats` | counts for the dashboard header |
| GET | `/reports/detections` | **timestamped detection report — a named deliverable** (CSV + PDF) |

### `GET /api/plates/{plate}/route` — the response the whole submission turns on

```json
{
  "query_plate": "GJ01AB1234",
  "normalised": "GJ01AB1234",
  "match_mode": "fuzzy",
  "total_sightings": 7,
  "first_seen": "2026-09-15T09:12:04Z",
  "last_seen": "2026-09-15T09:41:55Z",
  "duration_seconds": 1791,
  "distance_km": 12.4,
  "departments_crossed": ["Police", "GSRTC", "Municipal"],
  "stops": [
    {
      "sequence": 1,
      "camera_id": "cam04",
      "department": "Police",
      "location_name": "Naroda Road Junction",
      "lat": 23.0712, "lon": 72.6301,
      "seen_at": "2026-09-15T09:12:04Z",
      "plate_raw": "GJ01AB1234",
      "confidence": 0.94,
      "match_type": "exact",
      "crop_url": "/crops/cam04_00123.jpg",
      "elapsed_from_previous_s": null,
      "implied_speed_kmh": null
    }
  ],
  "gaps": [
    {"after_sequence": 3, "minutes": 14, "note": "no camera coverage on this corridor"}
  ]
}
```

`gaps` is not an admission of failure — it is the system being honest about coverage, and it ties directly to the Model 1 gap-analysis report. Surface it in the UI.

**`departments_crossed` matters:** the feeds span five named departments. A route crossing several of them is direct evidence for the central claim that heterogeneous departmental systems have been integrated. Make it prominent in the UI and in the demo.

---

## 8. Directory layout on disk

```
src/
  config.py            environment config, one place
  db.py                connection, schema, migrations
  models.py            dataclasses mirroring the tables above
  ingest/
    frame_source.py    THE critical component — see docs/04-feed-rules.md
    catalogue.py       fetch and parse cameras.json
    worker.py          per-camera loop, tiering, lifecycle
  anpr/
    detect.py          vehicle + plate detection
    ocr.py             plate reading
    plates.py          normalisation + matching (§6)
    motion.py          MOG2 gate
  analytics/
    zones.py           intrusion / line-crossing (P5)
    route.py           route reconstruction (§7)
  alerting/
    matcher.py         sighting → watchlist
    alerts.py          alert creation, SSE broadcast
  api/
    main.py            FastAPI app
    routes_*.py        one module per resource group
  tools/
    probe.py           P0 probe
    seed_watchlist.py
    report.py          detection report generator
ui/                    React + Vite
data/                  sentinel.db, crops/, seed CSVs  (gitignored)
```
