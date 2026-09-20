# backend/ — layer rules

The API process: FastAPI + uvicorn on `:8000`. Owns storage (SQLite, WAL), the binding contract (`docs/api.md`), auth + audit, the registry and onboarding, sightings/route/watchlist/alerts, the alert SSE stream, the HLS relay for the live wall, reports, health and stats, and serves the built frontend. Reads the root `CLAUDE.md` first; these rules add to it.

## Rules that bite this layer

- **The contract is `docs/api.md`.** Every endpoint declares a `response_model`; the exported OpenAPI is the Model 1 API-documentation deliverable, so it must be true. A stored shape or endpoint changes only with `docs/api.md` in the same commit.
- **Credentials never leave the process** (root rule 1): no URL with a credential is stored, logged, returned or placed in `argv`. Stream URLs in responses are templates or backend-relayed paths.
- **Persist before you notify** (root §4): sighting row committed before matching; alert row committed before broadcast. The SSE stream **tails the database** (alerts *and* high-severity zone events, with `Last-Event-ID`), because alerts fire in the worker process — never an in-process bus.
- **Alert ids come from an AUTOINCREMENT sequence**, never `COUNT(*)+1` (`docs/api.md` B7).
- **One time base**: canonicalise every timestamp at the boundary to the stored `+00:00` form; never compare ISO strings of mixed shape; route reconstruction never crosses clock domains (`docs/api.md` B6).
- **Auth on every endpoint** (`X-API-Key`, roles viewer/admin), `/crops` included; `TrustedHostMiddleware`; CORS only to the dev origin. **Audit** every mutation and every plate/route query (`docs/api.md` B12).
- **Input hygiene** (`docs/api.md` B11): `camera_id` matches `^[A-Za-z0-9_-]{1,64}$`; the relay fetches only inside the configured CDN origin and only playlist-listed names; report HTML escapes inputs; CSV cells starting `= + - @` are prefixed; pagination `total` reuses the row query's WHERE.
- **SQLite**: `busy_timeout=30 s`, `synchronous=NORMAL` under WAL, `foreign_keys=ON`; short transactions only — the health checker probes first and writes after, never holds a write across network calls. Indexes on `events(occurred_at)` and `events(camera_id, occurred_at)`; `plate_canonical` indexed on sightings and watchlist.
- **Health of active RTSP cameras is judged by local tee freshness**, never by probing the CDN (`docs/decisions.md` C14).
- The relay caches upstream playlists (~10 min) and retries with backoff plus one re-login; the CDN rate-limits bursts for minutes.
- **Every process writes a rotating log file under `data/logs/`**; the launcher polls the port and fails loudly if the API never binds; `python-multipart` is a pinned dependency (the CSV `Form` endpoint imports it).
- Migrations: a `schema_version` table and ordered migration scripts from the first schema.

## What the previous build did here (read-only reference)

`D:\projects\Sentinel_Repo\src\api\` (`main.py`, `routes_cameras.py`, `routes_analytics.py`, `routes_hls.py`, `routes_reports.py`, `routes_meta.py`, `schemas.py`), `src\db.py`, `src\config.py`, `src\alerting\`, `src\analytics\route.py`, `src\tools\report.py`, `src\tools\export_openapi.py`, `launch.py`. Its defects are listed in `docs/reference/old-build/P7-enhancements.md` §0 (D2, D4–D9, D12–D15 touch this layer).
