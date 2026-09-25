# API and data contracts (BINDING)

**Editor's note (20 Sep 2026).** Part A is the previous build's `03-data-contracts.md`, **copied verbatim**. It is the shape the submitted deliverables already describe (`deliverables/HLD.md` §1.4, `deliverables/registry-api.json`), so it is the fresh build's starting contract. Part B records, from the previous build's code and its review (`docs/reference/old-build/P7-enhancements.md`), every place the implementation diverged from Part A or learned something Part A does not say. **The API plan must resolve each item in Part B and fold the result back into Part A in the same commit** — after that, Part A alone is binding and Part B is history.

**Resolved in S1.1 (22 Sep 2026):** every Part B item is folded into Part A below (schema v1, `backend/core/migrations/0001_initial.sql`). **Part A alone is binding**; Part B is kept verbatim as history because other documents cite its item numbers.

Stale pointers inside Part A: `docs/04-feed-rules.md` → `docs/feed-rules.md`; `plan/STATUS.md` → `docs/progress.md`; `src/anpr/plates.py` and the §8 layout → the fresh build's layout (`docs/decisions.md`).

---

# Part A — The contracts *(verbatim)*

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
    rtsp_url_template TEXT,                  -- <email>/<password> placeholders or a plain local
                                             -- URL; for transport='replay' the local file path
    whep_url_template TEXT,
    transport        TEXT,                   -- hls | rtsp | replay | none
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

**Local stock feeds (F58, 25 Sep):** the committed register `data/local_feeds.csv` (`local01`…`local28`) is upserted by `backend.tools.seed_registry` on every run as `source = 'manual'`, `transport = 'rtsp'`, `rtsp_url_template = rtsp://127.0.0.1:8554/stream/<id>` (plain local URL), with the register's `department`, `location_name`, `lat`, `lon`, `bearing_deg`, `fov_deg`, `range_m` and `fps_tier`; `ownership`, `health` and `last_seen` are left as they are. Every such `location_name` carries the disclosure "(stock footage, seeded coordinates)" — the clips are looped stock footage, not the sandbox and not a filmed route (rule 12). A catalogue row is never touched by the register. The worker's active pick orders catalogue cameras first, then the rest by `camera_id`, under `SENTINEL_ACTIVE_CAMERAS`.

**`camera_id` hygiene (B11):** `camera_id` matches `^[A-Za-z0-9_-]{1,64}$` — it flows into filesystem paths and URLs, so nothing else is accepted, at every boundary. `rtsp_url_template` may carry `<email>`/`<password>` placeholders (filled from the environment in memory) **or** be a plain local URL used as-is; no stored URL ever contains a credential.

---

## 2. `sightings` — every plate read, the spine of the whole system

```sql
CREATE TABLE sightings (
    sighting_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    plate            TEXT NOT NULL,          -- normalised (§6); a structurally full OCR read is
                                             -- stored in its coerced form, coerce() (25 Sep)
    plate_raw        TEXT NOT NULL,          -- exactly what OCR returned; never overwritten
    plate_canonical  TEXT NOT NULL,          -- ambiguity-folded at write time (§6)
    confidence       REAL NOT NULL,          -- 0.0-1.0
    camera_id        TEXT NOT NULL REFERENCES cameras(camera_id),
    seen_at          TEXT NOT NULL,          -- the STREAM-TIME instant — see Time base below
    wall_time        TEXT NOT NULL,          -- when this system observed it
    clock_source     TEXT NOT NULL,          -- rtsp-live | hls-vod | harvest | demo | replay
    provenance       TEXT NOT NULL,          -- live | harvest | demo | test
    pts_ms           REAL,                   -- raw presentation timestamp, for audit
    bbox_json        TEXT,                   -- [x,y,w,h] in source pixels (the detector's
                                             -- internal xyxy is converted when the row is written)
    vehicle_class    TEXT,                   -- car | truck | bus | motorcycle | auto | unknown
                                             -- (the COCO detector emits the first four or unknown)
    crop_path        TEXT,                   -- plate crop on disk (~2 KB), forward slashes;
                                             -- demo rows: a rendered DEMO-marked plate image,
                                             -- data/crops/demo/<sighting_id>.jpg (25 Sep)
    frame_path       TEXT,                   -- full frame — ONLY for watchlist hits
    track_id         TEXT,                   -- within-camera tracker id
    created_at       TEXT NOT NULL
);
CREATE INDEX idx_sightings_plate     ON sightings(plate, seen_at);
CREATE INDEX idx_sightings_canonical ON sightings(plate_canonical, seen_at);
CREATE INDEX idx_sightings_camera    ON sightings(camera_id, seen_at);
CREATE INDEX idx_sightings_time      ON sightings(seen_at);
```

**Time base (B6, decision F13):** `seen_at` keeps its name and means the **stream-time instant** — for RTSP, `pull_start + PTS` (never `datetime.now()` at detection: inference latency and GOP replay both corrupt it); for HLS-VOD/harvest, `RECORDING_EPOCH + position`; for replay, `pull_start + index/fps`, continuous across loops (F36). `wall_time` is when this system observed it. `clock_source` names the clock; `provenance` ∈ `live | harvest | demo | test` — replay-transport reads are `test` (F26). Route reconstruction groups stops by `clock_source`, computes elapsed time and speed only within a group, and returns `warnings[]` instead of a speed when it would have to cross groups. Every export carries `provenance` (B14).

**Dedupe rule (mandatory, bounded — B13):** the same `plate_canonical` on the same camera **in the same `clock_source`** within **60 seconds of `seen_at`** (absolute difference — the bound is two-sided, so an out-of-order writer can never swallow a distant real sighting) **and within 10 minutes of `wall_time`** (S2.4: two reads whose stream times collide but that this system observed in different runs are different observations) is one sighting, not many. Keep the existing row and raise its confidence if the new read is better; do not insert. Every cooldown and throttle keys on `seen_at` (stream time), never on wall clock, and derives from stored rows, never from process memory.

---

## 3. `watchlist`

```sql
CREATE TABLE watchlist (
    watchlist_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    plate            TEXT NOT NULL UNIQUE,   -- normalised
    plate_canonical  TEXT NOT NULL,          -- ambiguity-folded (§6), indexed
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
```

Representative data created by us, which the rules permit. Seed it partly from **plates actually observed in the feeds** so the demo produces genuine hits, and partly from invented entries so the table looks like a real watchlist. Record in `docs/progress.md` which entries were seeded from observation.

---

## 4. `alerts`

```sql
CREATE TABLE alerts (
    alert_seq        INTEGER PRIMARY KEY AUTOINCREMENT,  -- the SSE cursor; never COUNT(*)+1 (B7)
    alert_id         TEXT NOT NULL UNIQUE,   -- ALERT-YYYYMMDD-NNNN, derived from alert_seq
    kind             TEXT NOT NULL,          -- watchlist | zone
    sighting_id      INTEGER NULL REFERENCES sightings(sighting_id),
    watchlist_id     INTEGER NULL REFERENCES watchlist(watchlist_id),
    event_id         INTEGER NULL REFERENCES events(event_id),
    zone_id          TEXT NULL,              -- zone cooldowns key on it (F34)
    plate            TEXT NULL,
    plate_canonical  TEXT NULL,
    camera_id        TEXT NOT NULL REFERENCES cameras(camera_id),
    category         TEXT NULL,
    severity         TEXT NOT NULL,          -- high | medium | low | critical
    match_type       TEXT NOT NULL DEFAULT 'none',  -- exact | ambiguity | fuzzy | none
    match_distance   REAL NOT NULL DEFAULT 0,       -- confusion-weighted (§6), fractional
    clock_source     TEXT NOT NULL,          -- rtsp-live | hls-vod | harvest | demo | replay
    fired_at         TEXT NOT NULL,          -- stream-time instant (the seen_at domain)
    acknowledged_at  TEXT,
    acknowledged_by  TEXT,
    clip_path        TEXT,                   -- Pipeline 3, nullable
    clip_sha256      TEXT
);
CREATE INDEX idx_alerts_fired     ON alerts(fired_at);
CREATE INDEX idx_alerts_canonical ON alerts(plate_canonical, camera_id, fired_at);
```

A **watchlist** alert has `sighting_id`, `watchlist_id`, `plate`, `plate_canonical` and `category` set; a **zone** alert (B8/F27) has `event_id` and `zone_id` set and those five NULL — one table, one SSE stream, `kind` tells them apart.

**Ordering invariant:** the sighting (or event) row is committed **before** the matcher/alert logic runs. An alert always references a row that already exists on disk. Never the reverse.

**Ids and cooldowns (B7, F27):** `alert_seq` is the allocation and the SSE cursor — SSE frames carry `id: <alert_seq>` and honour `Last-Event-ID`; the human id `ALERT-YYYYMMDD-NNNN` is derived from `alert_seq`, never counted. The 5-minute alert cooldown per (plate_canonical, camera) — for zone alerts per (zone_id, camera) — derives from the last matching `alerts` row **in the same `clock_source` domain**, never from process memory, so a purge resets it.

---

## 5. Camera zones (P5, intrusion detection)

`cameras.zones_json` — the canonical shape (B1; what the UI editor and the analytics actually use):

```json
[{"zone_id":"z1","name":"Platform edge","type":"intrusion","severity":"high","points":[[0.1,0.6],[0.9,0.6],[0.9,1.0],[0.1,1.0]]},
 {"zone_id":"z2","name":"Exit lane","type":"line","severity":"medium","points":[[0.0,0.5],[1.0,0.5]]}]
```

`type` ∈ `intrusion | line`; the geometry is always `points` (a polygon for intrusion, two points for a line); `severity` ∈ `high | medium | low` — a **high-severity** zone hit also writes an `alerts` row (`kind='zone'`, §4). Line crossing fires once, downward; upward is ignored. Coordinates normalised 0–1 so they survive resolution differences. `events` table for zone and object hits:

```sql
CREATE TABLE events (
    event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_id   TEXT NOT NULL REFERENCES cameras(camera_id),
    zone_id     TEXT,
    event_type  TEXT NOT NULL,               -- intrusion | line_cross | object_detected
    object_class TEXT,
    confidence  REAL,
    occurred_at TEXT NOT NULL,               -- stream-time instant (same rule as sightings.seen_at)
    wall_time   TEXT NOT NULL,
    clock_source TEXT NOT NULL,              -- rtsp-live | hls-vod | harvest | demo | replay
    provenance  TEXT NOT NULL,               -- live | harvest | demo | test
    bbox_json   TEXT,
    crop_path   TEXT
);
CREATE INDEX idx_events_time   ON events(occurred_at);
CREATE INDEX idx_events_camera ON events(camera_id, occurred_at);
```

The object-event throttle resets on `stream_restart` and keys on `occurred_at` (B13).

---

## 6. Plate grammar and matching (one implementation, `backend/core/plates.py` — B10)

Indian plate formats: standard `SS DD L(LL) NNNN` — two-letter state, two-digit district, one-to-three-letter series, four-digit number (Gujarat plates begin `GJ`) — **and** the national BH-series `NN BH NNNN L(L)`.

- `normalise(raw)`: uppercase, strip everything that is not `A-Z0-9`. Stored alongside `plate_raw`, never overwriting it.
- `canonical(plate)`: the ambiguity map folded to one form (`O→0, I→1, S→5, B→8, Z→2, G→6, Q→0`), stored as `plate_canonical` and indexed on `sightings`, `watchlist` and `alerts`.
- `plate_like(s)` → `full` when, after **position-aware ambiguity coercion** (where a letter is expected `0→O, 1→I, 5→S, 8→B, 2→Z, 6→G`; where a digit is expected the reverse), `s` matches the standard form `^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{4}$` with a state code in `AN AP AR AS BR CG CH DD DL DN GA GJ HP HR JH JK KA KL LA LD MH ML MN MP MZ NL OD OR PB PY RJ SK TN TR TS UK UP WB`, **or** the BH-series form `^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$`; `partial` when `s` (uncoerced) is a structural prefix of either form with length ≥ 4 and not full; otherwise `None` (rejected — e.g. burned-in captions).
- `coerce(s)` → the registration a `full` read parses as, after that same position-aware coercion (`6J23H1548 → GJ23H1548`, `GJ1157924 → GJ11S7924`, `GJO3XH0407 → GJ03XH0407`; an already-valid plate comes back unchanged), or `None` whenever `plate_like(s) != "full"` — a partial read is never coerced into a registration (F40). Coercion moves characters only inside their ambiguity class, so `canonical(coerce(s)) == canonical(s)`. **The ANPR pipeline stores `plate = coerce(read)` for a full read** (25 Sep: the live DB held `6J23H1548` beside `GJ23H1548`, so search and dedupe saw two plates); `plate_raw` keeps the OCR text. Rows written before that are re-stored by `python -m backend.tools.renormalise_plates` (dry run by default; `--apply` snapshots with `VACUUM INTO` first; live/harvest rows only — never demo or test; `plate_canonical` asserted unchanged; a watchlist alert's `plate` copy follows its sighting). The demo seeder writes its scripted plates as given (the `GJ01A81234` near-miss is deliberate).
- `is_partial(s)`: a read is **partial** when `plate_like(s) != "full"`. Partial reads are stored with their confidence, may appear on a route as low-confidence candidates clearly labelled, and **never fire an alert and never fuzzy-match**.
- `plate_match(a, b)` → `(matched, distance, rule)`: `exact` (distance 0) → `ambiguity` (same length, differs only inside ambiguity classes; distance 0) → `fuzzy` (both sides `full`; **confusion-weighted edit distance** where a substitution inside an ambiguity class costs 0.25 and any other substitution or indel costs 1.0; matched when ≤ 1.0) → `none`.
- **Alert policy (decision F21):** alerts fire on `exact` and `ambiguity`; on `fuzzy` only when `SENTINEL_ALERT_ON_FUZZY=true`. Fuzzy candidates are always shown on a route, flagged.

The ambiguity map is applied during canonicalisation and matching, and to the stored `plate` of a full OCR read only through `coerce()`; never to `plate_raw`.

---

## 7. API surface (FastAPI, prefix `/api`)

| Method | Path | Returns |
|---|---|---|
| GET | `/health` | service status, DB status, active worker count — **open** |
| POST | `/auth/login` | **(schema v2, decision F41)** username + password → sets the `sentinel_session` cookie; rate-limited, audited on success and failure — **open** |
| POST | `/auth/logout` | clears the session and revokes it server-side; audited |
| GET | `/auth/me` | the signed-in username, role and session expiry (what the UI renders its menu from) |
| GET | `/users` · POST · PATCH `/{id}` · DELETE `/{id}` | account administration, **admin only**; passwords are never returned and never logged |
| POST | `/session` | validates an API key, sets the `sentinel_key` cookie (F23) — kept for scripts |
| DELETE | `/session` | clears the cookie — behind auth like every non-open path (schema v2) |
| GET | `/cameras` | list; filters `department`, `health`, `tier`, `q` |
| GET | `/cameras/gap-analysis` | uncovered areas + ageing/offline cameras (Model 1 deliverable) — registered **before** `/{camera_id}` |
| GET | `/cameras/activity` | `?hours=` (1–168, default 24) — the GIS Activity layer: `[{camera_id, sightings, plates, alerts, last_seen, by_provenance{live\|harvest\|demo\|test: count}}]`, one row per camera with any read or alert whose `seen_at` / `fired_at` is at or after the server's wall clock minus `hours`; idle cameras are omitted; `plates` counts distinct plates; `by_provenance` splits `sightings` so a demo read never passes as a live one (root rule 12); sorted by reads, then alerts — registered **before** `/{camera_id}` |
| POST | `/cameras/import` | CSV bulk onboarding; per-row `accepted[] / rejected[]{row, reason}`, one transaction, no partial commit — registered **before** `/{camera_id}` |
| GET | `/cameras/{camera_id}` | one camera, full record |
| POST | `/cameras` | manual onboarding (Model 1 deliverable) |
| PATCH | `/cameras/{camera_id}` | edit metadata, ROI, zones, tier |
| GET | `/cameras/{camera_id}/stream` | `{"hls": "/api/hls/{camera_id}/live.m3u8"}` — only backend-relayed paths, never an upstream URL |
| GET | `/sightings` | **ANPR search.** Filters `plate` (≤ 64 chars), `match`, `camera_id`, `from`, `to`, `min_confidence`, `provenance`, `vehicle_class`; returns `{"total", "count", "sightings", "match", "query"}` with `limit` (≤ 2000) and `offset`; `total` reuses the row query's WHERE. `match` = `contains` (default, unchanged: `plate LIKE %q%`, newest first) \| `exact` (`plate = q`) \| `anpr` — OCR-tolerant, ranked **exact → ambiguity** (`plate_canonical` equality) **→ fuzzy** (`plate_match` over the plates sharing the first 4 canonical characters, both sides `full`, weighted distance ≤ 1.0), then newest first; a **partial** `anpr` query never fuzzy-matches (§6) and instead matches as an OCR-tolerant fragment (`plate_canonical LIKE %canonical(q)%`). Every row adds `match_type` (`exact \| ambiguity \| fuzzy \| contains`, null without a plate) and `match_distance` (0 for exact/ambiguity, the confusion-weighted distance for fuzzy, null for contains); `query` = `{plate, normalised, canonical, kind, coerced}` (null without a plate). A plate query's audit row names the plate (`entity='plate_search'`, `entity_id` = the normalised plate, `after_json` = `{match, camera_id, provenance, total}`) — B12 |
| GET | `/plates/suggest` | `?limit=` (1–50, default 8) → `{demo, watchlist, top_live}`, items `{plate, reads, cameras, last_seen, provenance, on_watchlist}` — the "plates to try" for Search: `demo` = the labelled demo plates (watchlisted first, then reads); `watchlist` = active unexpired entries (seen first, reads over every provenance joined on the canonical fold, `provenance` of the latest read, null if never seen; then severity); `top_live` = the most-read structurally full `live` plates, grouped by their coerced form. `cameras` is a count. Audited like every `/plates/*` query (B12) |
| GET | `/plates/{plate}/route` | **the scored endpoint** — see below |
| GET | `/watchlist` · POST · DELETE `/{id}` | watchlist CRUD (POST takes `plate, category, severity, description?, source_ref?`) |
| GET | `/alerts` | recent alerts, filters `severity`, `acknowledged`, `kind`, `limit` |
| POST | `/alerts/{alert_id}/ack` | acknowledge; accepts the human `alert_id` or the numeric `alert_seq`; persists `acknowledged_by` = the auth actor (username, or `key:<role>` for the key transport) |
| GET | `/alerts/stream` | **SSE** — one background tailer over `alerts` (both kinds); frames carry `id: <alert_seq>`, honours `Last-Event-ID` |
| GET | `/events` | zone/object events; filters `camera_id`, `event_type`, `limit` |
| GET | `/events/summary` | `?minutes=` — `{minutes, total, cameras{<cam>: {objects{class: count}, intrusion, line_cross}}}`, anchored at the newest event |
| GET | `/workers` | the supervisor's stats snapshot verbatim (`{available, written_at, uptime_s, restarts, rss_mb, frames, fps_sustained, inferred, motion_skip_rate, detections, detections_per_min, sightings, alerts, zone_events, ocr_attempts, full_reads, vehicle_tracks, plate_read_rate, cameras{<cam>: {…, alive}}}` mirroring `ml/supervisor._write_stats`; the S4.1 counters — `ocr_attempts`, structurally-`full` consensus `full_reads`, unique `vehicle_tracks` and their ratio `plate_read_rate` — are per camera too, so `launch.py measure` (F18) can window-delta them); `{available: false}` when no snapshot exists |
| GET | `/stats` | `cameras_online, cameras_total, departments, sightings_total, plates_unique, events_total, zone_events, alerts_active` |
| GET | `/reports/detections` | **timestamped detection report — a named deliverable**; `?format=csv\|html` + filters `camera_id`, `from`, `to`, `plate`; every row carries `provenance` |
| GET | `/reports/gap-analysis` | rendered gap report (HTML) |
| GET | `/reports/route/{plate}` | route report export |
| GET | `/hls/{camera_id}/live.m3u8` · `/source` · `/mtx/{name}` · `/key` · `/seg/{name}` · `/local/{name}` | the Pipeline 1 relay — **every camera plays through it; nothing is stored**. `live.m3u8` takes, in order: **(1)** the worker's tee when fresh (< 20 s; segments at `/local/{name}`); **(2)** a **local feed** (`rtsp_url_template` on `127.0.0.1`/`localhost`) through mediamtx's own HLS server at `http://127.0.0.1:{SENTINEL_MEDIAMTX_HLS_PORT}/{path}/` — child playlist and segments at `/mtx/{name}?session=…`, only names listed in the playlist last fetched for that viewer's mediamtx session, host pinned to 127.0.0.1 (the stored RTSP port is irrelevant), mediamtx's `?cookieCheck=1` redirect followed only on that origin; **(3)** a sandbox camera's stale tee while younger than 120 s (a worker's brief reconnect never flips the source); **(4)** the organisers' **CDN VOD** as a sliding window at the shared-timeline position (`/seg/{name}`, `/key` — only names present in the upstream playlist, only inside the configured CDN origin; the URL is `hls_url`, or `{cdn}/<id>/index.m3u8` for a `source='catalogue'` camera). **Sandbox cameras fall to the CDN** — this replaces "a `transport='rtsp'` camera never falls back to the CDN" (25 Sep): the five analysed cameras' workers hold five of the gateway's ~6 RTSP sessions, so the organisers' HLS copy, relayed once, is the only viewing path for the other 25 that keeps one pull per camera (rule 2). CDN segments and the key sit in a bounded in-memory single-flight cache (48 MB, 120 s — N viewers cost one upstream fetch per segment); upstream VOD playlists are cached 10 min, an expired copy keeps serving while one caller refreshes it, and their fetches start at most one per 1.5 s relay-wide (a wall opening on 16 CDN cameras is not a 16-fetch burst); a relay-wide breaker backs off (2 s base, 30 s cap, ×random(0.5, 1.5)) after a refusal and admits a single probe until the CDN has answered. Every playlist response carries **`X-Sentinel-Source: tee \| stale-tee \| mediamtx \| cdn`**; **`/source`** returns `HlsSourceOut {camera_id, source: tee \| stale-tee \| mediamtx \| cdn \| none, detail}` without touching any upstream. Errors carry a machine-readable `detail`: `503` `cdn-backoff` (with `Retry-After`) · `cdn-unavailable` · `cdn-login-failed` · `cdn-not-configured` · `local feed server not running` · `local feed not publishing` · `local feed server timed out`; `502` `cdn-not-found` · `local feed server returned no playlist`; `403` a name not in the playlist; `404` `no-live-source` |

**Auth transport (B12, F23, and decision F41 from schema v2 onward):** two credentials reach the same authorisation check.

- **People sign in** (F41): `POST /api/auth/login` with a username and password sets `sentinel_session` — `HttpOnly`, `Secure`, `SameSite=Strict`, 8 hours, revocable server-side. Because the UI and the API share one origin, that cookie carries `<img>` crops, hls.js segments and the alert `EventSource` as well as ordinary calls, and it authorises **whatever the role allows, mutations included** (the `SameSite=Strict` cookie plus an `Origin` check on every **session-authenticated** mutation is what closes CSRF; a cross-site form cannot send either. `X-API-Key` mutations are exempt from the `Origin` check — a script sends no Origin, and the header itself cannot be attached cross-site).
- **Scripts use a key**: the `X-API-Key` header keeps working exactly as F23 describes, as does `POST /api/session` for the `sentinel_key` cookie on GET media. The API refuses to start if either key is unset.
- **Roles** are `viewer` (read), `evaluator` (read, acknowledge, watchlist add and remove, reports, the onboarding form) and `admin` (everything, including `/api/users`, zones and tier changes).
- **Open paths** are `/`, `/assets/*`, `/api/health` and `/api/auth/login` **only**. `/docs` and `/openapi.json` move behind the login once the platform is public (the committed `deliverables/registry-api.json` remains the API-documentation deliverable).
- **Audit actor**: the `audit.actor` column carries the username the auth dependency resolved (or `key:<role>` for the key transport); the bare role appears only on paths that never authenticated. `/docs` alone gets a relaxed CSP (cdn.jsdelivr.net + inline bootstrap — Swagger UI cannot boot under the strict policy); the strict CSP applies everywhere else.
- `TrustedHostMiddleware` allows `localhost`, `127.0.0.1` **and the published tunnel hostname** from `SENTINEL_PUBLIC_HOST` (decision F42). Every mutation and every plate/route query writes an `audit` row (`audit(audit_id, at, actor, role, action, entity, entity_id, before_json, after_json)` — `before/after` supplied by handlers). Every endpoint declares a `response_model`, so the exported OpenAPI (`deliverables/registry-api.json`) is the real contract; no `snapshot.jpg` endpoint exists. Every timestamp is canonicalised at the API boundary to the stored `+00:00` form; HTML reports escape their inputs; CSV cells beginning `= + - @` are prefixed (B11).

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
      "clock_source": "rtsp-live",
      "provenance": "live",
      "plate_raw": "GJ01AB1234",
      "confidence": 0.94,
      "match_type": "exact",
      "match_distance": 0,
      "suspect": false,
      "crop_url": "/crops/cam04_00123.jpg",
      "elapsed_from_previous_s": null,
      "implied_speed_kmh": null
    }
  ],
  "gaps": [
    {"after_sequence": 3, "minutes": 14, "note": "no camera coverage on this corridor"}
  ],
  "warnings": [
    "stops 4-5 come from a different clock (hls-vod); elapsed time and speed not computed across the boundary"
  ]
}
```

Per stop, `match_distance` is the confusion-weighted edit distance (§6) and `suspect` is set when the implied speed is implausible (B2). The stop-collapse window is 2 minutes on the same camera; the gap-flag threshold is configurable. Stops are grouped by `clock_source`; `elapsed_from_previous_s` and `implied_speed_kmh` are computed only within a group, with `warnings[]` explaining every boundary (B6).

`gaps` is not an admission of failure — it is the system being honest about coverage, and it ties directly to the Model 1 gap-analysis report. Surface it in the UI.

**`departments_crossed` matters:** the feeds span five named departments. A route crossing several of them is direct evidence for the central claim that heterogeneous departmental systems have been integrated. Make it prominent in the UI and in the demo.

---

## 8. Directory layout on disk *(superseded — decision F12; the old layout is history, B4)*

Top-level packages, run from the repo root (`python -m backend.app`, `python -m ml`):

```
backend/
  core/                shared with ml/: config.py, logging_setup.py,
                       db.py + migrations/, timeline.py, plates.py,
                       matcher.py, alerts.py, cdn_session.py
  app/                 __main__.py, main.py, auth.py, audit.py, schemas.py,
                       routes_cameras.py, routes_meta.py, routes_analytics.py,
                       routes_reports.py, routes_hls.py
  services/            gap_analysis.py, route.py, reports.py, health.py
  tools/               probe.py, seed_registry.py, seed_watchlist.py,
                       export_openapi.py, demo_seed.py
ml/                    the worker process (ingest/, anpr modules, tools/)
frontend/              React + Vite app (dist/ ignored; zipped on the submission tag, F30)
tests/                 pytest suite; pytest.ini at the root (pythonpath = .)
scripts/               one-off helpers (doctor.py, replay_publish.py)
data/                  sentinel.db, crops/, logs/ (runtime, gitignored) +
                       the three committed evidence files (catalogue, probe, seed)
```

---

## 9. Auth tables and public-exposure rules (schema v2 — decisions F41, F42)

Added by migration `0002_auth.sql`. Everything in §1–§8 is unchanged by it.

```sql
CREATE TABLE users (
    user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,          -- hashlib.scrypt(n=2**14, r=8, p=1), per-user salt, stored as
                                          -- scrypt$<n>$<r>$<p>$<salt_b64>$<hash_b64> — never a plain hash
    role          TEXT NOT NULL,          -- viewer | evaluator | admin
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL,
    last_login    TEXT
);
CREATE TABLE sessions (
    session_id    TEXT PRIMARY KEY,       -- secrets.token_urlsafe(32); the cookie value, never a JWT
    user_id       INTEGER NOT NULL REFERENCES users(user_id),
    issued_at     TEXT NOT NULL,
    expires_at    TEXT NOT NULL,          -- issued_at + 8 h
    revoked_at    TEXT,
    user_agent    TEXT                    -- truncated, for the audit trail only
);
CREATE INDEX idx_sessions_user ON sessions(user_id, expires_at);
```

- **Passwords** are never stored, logged, returned or placed in `.env`. Accounts come from `python -m backend.tools.users add <username> --role <role>`, which prompts for the password. The same tool has `passwd`, `disable` and `list` (names and roles only).
- **`audit.actor` is the username** once a session exists (the role alone is kept for key-authenticated calls). Login success, login failure and logout each write an audit row; a failure row never contains the password or the attempted value.
- **Login throttle:** 5 failures for one username, or from one address, lock further attempts for 15 minutes; the lock is in the database, so a restart does not clear it.
- **Rate limits** on the expensive reads — the route query, the report exports and the HLS relay — per session, returning `429` rather than queueing.
- **The relay's limit is 3,000 requests/minute per identity** (25 Sep; was 600), sized for a 16-tile wall. Per tile per minute, worst case: a 2 s-segment feed (the worker tee, or mediamtx with `MTX_HLSSEGMENTDURATION=2s`) is 60/2 = **30 segments** plus up to **60 playlist reloads** (hls.js reloads at half the target duration while the playlist is unchanged) = **90**; a CDN tile (6 s segments, target 7 s) is 10 segments + ≤ 17 reloads + 1 key ≈ **28**. A 16-tile wall of 2 s feeds is therefore 16 × 90 = **1,440/min**, plus one `/source` per tile mount; doubling that for player retries and a second tab of the same user gives ~2,900 → **3,000**. The old 600/min would have answered `429` to a 9-tile wall of 2 s feeds (9 × 90 = 810) inside the first minute.
- **Response headers** on every response: `Content-Security-Policy` (self, plus the OSM tile host and `data:` images), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, and HSTS when `SENTINEL_PUBLIC_HOST` is set.
- **Body limits:** the CSV import accepts at most 2 MB and 5,000 rows, and rejects anything else with a reason, not a stack trace.
- **Only the API port is published** (decision F42). mediamtx (RTSP 8554, and HLS on `SENTINEL_MEDIAMTX_HLS_PORT`, default 8888 — `http://127.0.0.1:8888/stream/<id>/index.m3u8`, MPEG-TS, 2 s segments, the relay's local source) and the Vite dev server bind to `127.0.0.1` and are never tunnelled.

---

# Part B — Corrections and lessons from the previous implementation

> **Resolved in S1.1 on 22 Sep 2026 — historical; Part A above is binding.** Every item below is folded into Part A (and schema v1). The text is kept verbatim because other documents cite its item numbers.

Each item names the code that shipped (`D:\projects\Sentinel_Repo\src\…`) and what the fresh build must decide. Items B1–B5 are divergences between Part A and the code; B6–B14 are design defects the review found that the contract must prevent.

## B1. Zones are stored in a different shape from §5

The UI editor (`ui/src/pages/Zones.jsx`) and the analytics (`src/analytics/zones.py`) use:

```json
[{"zone_id":"z1","name":"Platform edge","type":"intrusion","severity":"high","points":[[0.1,0.6],[0.9,0.6],[0.9,1.0],[0.1,1.0]]},
 {"zone_id":"z2","name":"Exit lane","type":"line","severity":"medium","points":[[0.0,0.5],[1.0,0.5]]}]
```

— `type` is `intrusion | line` (not `line_cross`), the geometry is always `points`, there is a `severity` (high-severity zones broadcast an alert), and there is no `direction` or `classes`. Line crossing fires once, downward; upward is ignored. **Decide the canonical shape and put it in §5.** The `events.event_type` values written were `intrusion | line_cross | object_detected` (as §5).

## B2. The route response carries two extra per-stop fields

`src/analytics/route.py` returns everything in §7 plus, per stop, `match_distance` (integer edit distance) and `suspect` (boolean, set when the implied speed is implausible). Both are used by the route UI. **Add them to §7.** The stop-collapse window is 2 minutes on the same camera; the gap flag threshold is configurable.

## B3. Endpoints that existed beyond §7, and one that no longer does

| Method | Path | Notes |
|---|---|---|
| GET | `/api/events/summary?minutes=` | object/zone counts per camera per class over the last N minutes of the *recording* timeline |
| GET | `/api/workers` | the worker supervisor's stats snapshot (`data/worker_stats.json`) — sustained fps, skip rate, detections/min per camera |
| GET | `/api/reports/gap-analysis` | rendered gap report (HTML) |
| GET | `/api/reports/detections?format=csv\|html` | plus filters camera_id / from / to / plate |
| GET | `/api/hls/{camera_id}/live.m3u8`, `/key`, `/seg/{name}`, `/local/{name}` | the Pipeline 1 relay (rewritten playlist, proxied AES key, proxied segment, worker's local tee) |
| GET | `/api/cameras/{camera_id}/snapshot.jpg` | **removed from the code but still listed in `deliverables/registry-api.json`** — the exported OpenAPI is stale; re-export from the fresh build |

`GET /api/sightings` returns `{"total", "count", "sightings"}` with `limit` (≤2000) and `offset`. `GET /api/alerts` filters `severity`, `acknowledged`, `limit`. `GET /api/events` filters `camera_id`, `event_type`, `limit`. `GET /api/stats` returns `cameras_online, cameras_total, departments, sightings_total, plates_unique, events_total, zone_events, alerts_active` — `sightings_today` was dropped because "today" is meaningless on a recording timeline. `GET /api/health` returns `status, db, time, counts`. `POST /api/watchlist` takes `plate, category, severity, description?, source_ref?`. `GET /api/cameras/gap-analysis` returns `generated_at, cameras_total, online, active_tier, cameras_offline_or_degraded[], isolated_coverage[] (nearest_neighbour_km, radius_km), department_summary`. `POST /api/cameras/import` returns per-row `accepted[] / rejected[] (reason)` with no partial commit. No endpoint declared a `response_model`; every response was an untyped `dict`. **The fresh build declares response models so the exported OpenAPI is the real contract.**

## B4. The §8 layout was never fully realised

`src/models.py` and `src/ingest/catalogue.py` never existed (the catalogue fetch lives in `src/tools/probe.py`); `src/ingest/timeline.py`, `src/ingest/session.py`, `src/ingest/health.py`, `src/anpr/pipeline.py`, `src/anpr/sightings.py`, `src/anpr/track.py`, `src/api/routes_hls.py`, `src/api/routes_meta.py`, `src/api/routes_reports.py` and eight `src/tools/*` were added. The fresh build has its own layout (`docs/decisions.md`); §8 is superseded.

## B5. The catalogue is `{id, name}` only

§1's "from the catalogue, never invented" holds for `camera_id`; department, coordinates and tier come from the committed, disclosed `data/camera_seed.csv` (`source = 'catalogue'` for the id, seed for the rest). Names from cam21 onward carry a different number from the id — key on `id` only.

## B6. Time base (review defect D3 — the one that breaks the scored route)

RTSP sightings were stamped with wall-clock `now()`; HLS and harvest sightings with a synthetic `RECORDING_EPOCH + offset` (June 2026, in UTC although the footage clock is IST). The two never align, so a route mixing transports computes nonsense. **Contract change (decision F13):** `seen_at` keeps its name and means the **stream-time instant** (the recording-timeline instant for HLS/harvest, `pull_start + PTS` for RTSP); every sighting and event additionally stores `wall_time` (when this system observed it), `clock_source` (`rtsp-live | hls-vod | harvest | demo | replay`) and `provenance` (`live | harvest | demo | test` — `test` is what replay-transport reads carry, decision F26), on every row and in every export; `events` rows carry the same three columns. Route reconstruction groups stops by `clock_source`, computes elapsed time and speed only within a group, and returns a `warnings[]` field instead of a speed when it would have to cross groups.

## B7. Alert ids (defect D4)

`alert_id` was allocated as `COUNT(*)+1` for the day — a thread race loses alerts, and after `demo-clear` the primary key collides and **every later alert that day fails**. The SSE cursor used the reusable implicit `rowid`. **Contract change (decisions F27):** `alert_seq INTEGER PRIMARY KEY AUTOINCREMENT`; the human id `ALERT-YYYYMMDD-NNNN` is derived from it, never counted; SSE frames carry `id: <alert_seq>` and honour `Last-Event-ID`. The row gains `kind` (`watchlist | zone`), nullable `event_id` and `zone_id`, and `sighting_id`, `watchlist_id`, `plate`, `category` become nullable so a zone alert can exist; `match_type` ∈ `exact | ambiguity | fuzzy | none` (default `none`), `match_distance` becomes `REAL` (the confusion-weighted distance of §6 is fractional), and `clock_source` is stored so the 5-minute cooldown is derived from the last matching `alerts` row in the same clock domain — never from memory, so a purge resets it.

## B8. Zone alerts never reached the dashboard (defect D5)

High-severity zone events were broadcast on an in-process bus inside the worker process, which the API never sees. **Contract change (decision F27):** a high-severity zone hit writes an `alerts` row with `kind='zone'` and `event_id` set; the API runs **one** background tailer over `alerts` (only) that broadcasts every new row on the SSE stream with its `kind`.

## B9. Matching semantics and indexes (defect D6)

Route lookup scanned the whole `sightings` table with per-row Levenshtein; watchlist matching was a linear scan per sighting; plain Levenshtein ≤ 1 merges neighbouring real registrations (`GJ01AB1234` vs `…1235`) into one route. **Contract change:** a `plate_canonical` column (ambiguity-folded at write time) indexed on `sightings` and `watchlist`, exact-first matching, and a confusion-weighted distance for fuzzy candidates (ambiguity-class substitutions cheap, arbitrary substitutions expensive). The `events` table had **no indexes**; add `(occurred_at)` and `(camera_id, occurred_at)`.

## B10. Plate grammar (defect D11)

The structural filter rejected the national **BH-series** format (`##BH####LL`), making an entire registration class invisible, and the regex was duplicated in two files. §6 must be rewritten to exactly this (one module, `backend/core/plates.py`; S1.2 implements it):

- `normalise(raw)`: uppercase, strip everything that is not `A-Z0-9`. Stored alongside `plate_raw`, never overwriting it.
- `canonical(plate)`: the ambiguity map folded to one form (`O→0, I→1, S→5, B→8, Z→2, G→6, Q→0`), stored as `plate_canonical` and indexed on `sightings` and `watchlist`.
- `plate_like(s)` → `full` when, after **position-aware ambiguity coercion** (where a letter is expected `0→O, 1→I, 5→S, 8→B, 2→Z, 6→G`; where a digit is expected the reverse), `s` matches the standard form `^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{4}$` with a state code in `AN AP AR AS BR CG CH DD DL DN GA GJ HP HR JH JK KA KL LA LD MH ML MN MP MZ NL OD OR PB PY RJ SK TN TR TS UK UP WB`, **or** the BH-series form `^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$`; `partial` when `s` (uncoerced) is a structural prefix of either form with length ≥ 4 and not full; otherwise `None` (rejected — e.g. burned-in captions).
- A read is **partial** when `plate_like(s) != "full"`. Partial reads are stored with their confidence, may appear on a route as low-confidence candidates clearly labelled, and **never fire an alert and never fuzzy-match**.
- `plate_match(a, b)` → `(matched, distance, rule)`: `exact` (distance 0) → `ambiguity` (same length, differs only inside ambiguity classes; distance 0) → `fuzzy` (both sides `full`; confusion-weighted edit distance where a substitution inside an ambiguity class costs 0.25 and any other substitution or indel costs 1.0; matched when ≤ 1.0) → `none`.
- Alerts fire on `exact` and `ambiguity`; on `fuzzy` only when `SENTINEL_ALERT_ON_FUZZY=true` (decision F21). Fuzzy candidates are always shown on a route, flagged.

## B11. Input and output hygiene (defects D7, D8)

Server-side fetch of an arbitrary `hls_url` (SSRF); un-validated segment `name` escaping via `urljoin`; reflected XSS in the detection report's query parameters; `camera_id` flowing into filesystem paths; CSV exports without formula-prefix escaping; pagination `total` computed without the filters; time-range filters comparing mixed-format ISO strings lexicographically. **Contract rules:** `camera_id` matches `^[A-Za-z0-9_-]{1,64}$`; relay fetches only within the configured CDN origin and only names present in the upstream playlist; every timestamp is canonicalised at the API boundary to the stored `+00:00` form; every HTML report escapes its inputs; CSV cells beginning with `= + - @` are prefixed.

## B12. Authentication and audit (defect D2)

Every endpoint was open, including watchlist add/delete, camera edits and alert acknowledgement, and plate crops (PII) were served openly. **Contract addition (decisions F4, F23):** an `X-API-Key` header (which forces a CORS preflight and so closes the CSRF hole), roles `viewer` and `admin` from two configured keys; additionally a `sentinel_key` cookie (`SameSite=Strict`, `HttpOnly`, set by `POST /api/session`, cleared by `DELETE /api/session`) is accepted for **GET** on `/crops/*`, `/api/hls/*` and `/api/alerts/stream` only, because `<img>`, hls.js and `EventSource` cannot send custom headers; mutations always require the header **and** admin. Open paths: `/`, `/assets/*`, `/docs`, `/openapi.json`, `/api/health`. `TrustedHostMiddleware` on. An append-only `audit` table (actor, role, action, entity, entity_id, before_json, after_json, timestamp) written by middleware for every mutation **and every plate or route query** — operator-misuse lookups are the documented ANPR scandal pattern; handlers supply `before/after`.

## B13. Dedupe and cooldown bounds (defect D12)

The 60-second dedupe in §2 had no upper time bound (out-of-order writers swallowed real sightings), the object-event throttle did not reset on `stream_restart`, and cooldowns were keyed on wall clock rather than stream time. State the bounds in §2 and key cooldowns on `seen_at` (the stream-time instant).

## B14. Provenance in every export

Detection reports and route exports must carry the `provenance` column so a demo row can never pass as a live detection (defect D15). The sample `deliverables/detection-report.csv` on disk contains the demo vehicle's rows and must be regenerated.

## B15. Small contract facts settled by the plan (21 Sep)

- `cameras.transport` ∈ `hls | rtsp | replay | none`; for `replay` (a local file used by tests and the soak) `rtsp_url_template` holds the file path.
- `sightings.bbox_json` stays `[x, y, w, h]` in source-frame pixels; the detector's internal `xyxy` is converted when the sighting is written.
- `sightings.vehicle_class` keeps `auto` as an allowed value; the COCO detector emits `car | truck | bus | motorcycle` or `unknown`.
- `alerts.fired_at` and every cooldown are stream-time instants (`seen_at`), not wall clock.
- `GET /api/sightings` accepts a `provenance` filter; every report carries the column (B14).
- New endpoints: `POST /api/session`, `DELETE /api/session` (F23); `GET /api/reports/route/{plate}`; `GET /api/workers` returns the supervisor's stats snapshot.
