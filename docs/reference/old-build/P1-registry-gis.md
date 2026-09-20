# P1 — Registry + API + GIS + live wall  (budget: 4 hours)

**Why first:** Model 1 is mandatory and carries **zero ML risk**. Finished, it is a demoable system on its own — the insurance policy if everything downstream struggles. It also produces three named Model 1 deliverables almost for free.

---

## P1.1 — FastAPI service

**Do:** implement `src/api/main.py` plus `routes_cameras.py`, exactly the paths in `docs/03-data-contracts.md` §7 for cameras, health and stats. CORS open to the Vite dev server. Pydantic models mirroring `src/models.py`.

**Acceptance:** `uvicorn src.api.main:app` starts; `GET /api/cameras` returns every registry row; `GET /api/health` reports DB status and camera counts.

---

## P1.2 — Onboarding endpoints (Model 1 deliverable: bulk + manual + API)

**Do:** `POST /api/cameras` (manual, one record), `POST /api/cameras/import` (CSV bulk, returning per-row accepted/rejected with reasons), `PATCH /api/cameras/{id}`. Validate: `camera_id` unique, lat/lon in range, department from the known set or `Unknown`.

**Acceptance:** import a 3-row CSV including one deliberately invalid row; the valid two are created, the invalid one is rejected with a readable reason, and nothing partially committed.

---

## P1.3 — Registry API documentation (Model 1 deliverable — free)

**Do:** confirm FastAPI's `/docs` and `/openapi.json` render correctly with descriptions on every endpoint and field. Export `openapi.json` to `deliverables/registry-api.json`.

**Acceptance:** the exported spec opens in a viewer and every endpoint has a description. This closes a named deliverable at essentially zero cost — do not skip it.

---

## P1.4 — GIS map

**Do:** React + Vite + Leaflet. Every camera as a pin. **Colour by department** — this is the visual proof of multi-departmental integration and costs nothing. Marker shape or opacity by health. Layer toggles for department and status. Click a pin → side panel with the full record: id, department, location, codec, resolution, measured fps, bitrate, transport, last seen.

**Acceptance:** every registry camera appears at its coordinates, colour-coded by department, and filters actually filter.

---

## P1.5 — Live wall

**Do:** a grid view using **hls.js**. Configurable 1/4/9 tiles. **Only visible tiles open a player** — mount on view, unmount and destroy on hide. Each tile shows camera id, department and a live indicator.

Non-negotiable: destroying a tile must fully tear down the hls.js instance. A leaked player is a leaked stream pull, which costs bandwidth and violates the pacing rule.

**Acceptance:** a 4-tile grid plays four different cameras simultaneously; switching pages stops the previous four — verified by watching the network panel, not by assuming.

---

## P1.6 — Camera health

**Do:** a lightweight periodic check updating `health` and `last_seen` — a HEAD or short probe per camera on a slow interval (minutes, not seconds). Statuses: `online`, `degraded` (reachable but stale), `offline`.

**Acceptance:** stopping a camera's playback or pointing one row at a bad URL flips it to `offline` within one cycle.

---

## P1.7 — Gap-analysis report (Model 1 deliverable)

**Do:** `GET /api/cameras/gap-analysis` returning:
- cameras currently `offline` or `degraded`, with how long
- clusters of coverage vs gaps — for each camera, nearest-neighbour distance via Haversine; flag areas with no camera within a configurable radius
- department-wise camera counts and coverage summary

Render it as a page and export to PDF or a clean printable HTML into `deliverables/gap-analysis-report.pdf`.

**Acceptance:** the report generates from live registry data and names at least one real gap or ageing/offline camera.

---

## P1.8 — Dashboard shell

**Do:** the frame everything else plugs into — header with live counts (cameras online, sightings today, active alerts), left nav (Map · Live Wall · Search · Alerts · Reports), and an alert panel region that P3 will fill.

**Acceptance:** all sections navigable; counts come from `/api/stats`, not hard-coded.

---

**Exit P1 when:** the map, live wall and gap-analysis report all work against real feeds, and `deliverables/registry-api.json` is exported.

**Record a screen capture now.** This is a complete, submittable Model 1 demonstration and it is worth having on disk before touching the ML.
