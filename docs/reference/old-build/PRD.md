# Sentinel — Product Requirements Document (PRD)

**Product:** Sentinel — Integrated Video Management & Analytics Platform
**Context:** Gujarat Police Innovation Challenge 2026 (SCRB, Home Department, Govt. of Gujarat)
**Author:** Adi · **Date:** 13 September 2026 · **Submission deadline: 15 September 2026**
**Status:** Approved — requirements frozen. Changes require editing this file in the same commit as the change.

This PRD is the *what and why*. The *how* is in `docs/01-architecture.md` (locked), the binding shapes in `docs/03-data-contracts.md`, the execution order in `plan/PLAN.md` (P0–P6), and the non-negotiables in `CLAUDE.md`.

---

## 1. Problem statement

26 Gujarat government departments operate independent, standalone CCTV systems — mixed analog/IP cameras, different vendors and VMS platforms, fragmented storage (cloud and local, 7–15+ day retention), sites up to ~1,000 km apart. No single view exists across them. When police need to trace a vehicle across the state, footage must be requested department by department, manually.

The hackathon sandbox simulates this: live feeds from cameras spanning five departments (Health, Police, GSRTC, Panchayat, Municipal Corporation), heterogeneous in codec, resolution, frame rate and bitrate, reachable over HLS/RTSP/WHEP.

**The core job to be done:** given a vehicle registration number handed over live on evaluation day, return that vehicle's complete, timestamped, location-wise route across the camera network — and continuously cross-reference all feeds against a watchlist with automated real-time alerts.

## 2. Users

| User | Needs |
|---|---|
| **Evaluation jury** (primary) | See the test case succeed live; judge the documentation on the ten dimensions; verify claims against the working system |
| **Control-room operator** | Live multi-camera wall, trustworthy alerts (with plate crops), plate search, route view, acknowledgement workflow |
| **Department admin / planner** | Camera registry with health status, GIS coverage view, gap-analysis reports, onboarding (manual/bulk/API) |
| **Investigating officer** | Plate → route query, timestamped detection reports (CSV/PDF), evidence with chain of custody |

## 3. Goals and success criteria

**G1 — Pass the live test case.** A plate typed into the UI returns an ordered, timestamped, location-wise route across ≥3 cameras spanning ≥2 departments, with gaps flagged honestly. *(This is the single overriding goal — CLAUDE.md §2.)*

**G2 — Watchlist alerting works live.** A watchlisted plate passing an active camera raises a dashboard alert within ~2 seconds, with plate crop, camera, department, timestamp.

**G3 — Model 1 complete.** Registry + GIS map + onboarding (manual, bulk CSV, API) + health monitoring + gap-analysis report + exported API documentation — every named Model 1 deliverable closed.

**G4 — Submission complete on all seven evaluation areas and ten dimensions**, submitted before 15 September, every link verified from a private window.

**Non-goals (explicitly out of scope for the demo — described in HLD only):**
- Model 3 federation layer (no departmental VMS platforms exist in the sandbox to federate)
- Facial recognition (approach + privacy controls described; not built)
- VAHAN / SARTHI / eGujCop / AFIS / NAFIS live integration (adapter design described)
- Production infrastructure: Postgres/PostGIS, Kafka, Kubernetes, Docker, Redis/Valkey, OpenSearch
- Model training of any kind; authentication beyond a single demo role (unless P1–P4 complete)
- Statewide scale (80,000 cameras) — modelled and costed in the HLD, grounded in measured demo numbers

## 4. Functional requirements

Priorities: **P0 = submission fails without it · P1 = scored, expected · P2 = bonus.**

### FR-1 Camera registry & GIS (Model 1 — mandatory) — P0
- FR-1.1 Registry populated from the sandbox catalogue (`cameras.json`); the catalogue is the contract; nothing hard-codes camera ids or URLs.
- FR-1.2 Every camera carries: id, department, location name, lat/lon, codec, resolution, declared + measured fps, bitrate, transport, health, last_seen, fps_tier (schema: `03-data-contracts.md` §1). Where the catalogue lacks department/coordinates, they are assigned in a committed seed file and **disclosed in the submission**.
- FR-1.3 Onboarding: manual (`POST /api/cameras`), bulk CSV with per-row accept/reject reasons, PATCH for edits.
- FR-1.4 Interactive GIS map (Leaflet): every camera as a pin, **colour-coded by department**, health-coded, filterable; pin click → full record panel.
- FR-1.5 Periodic health checks updating `health`/`last_seen` (online / degraded / offline).
- FR-1.6 Gap-analysis report: offline/degraded cameras with durations, coverage gaps by nearest-neighbour distance, department-wise counts — rendered and exported to `deliverables/`.
- FR-1.7 Registry API documentation exported from OpenAPI to `deliverables/registry-api.json`.

### FR-2 Unified live viewing (Model 2) — P0
- FR-2.1 Live wall (hls.js), 1/4/9-tile grid; **only visible tiles hold an open stream**; tile teardown fully destroys the player (verified in the network panel).
- FR-2.2 Tiles labelled with camera id and department. Feeds from ≥2 departments viewable simultaneously (Model 2 deliverable: "at least two different systems").
- FR-2.3 Pipeline 1 stores nothing — live view is relay only.

### FR-3 ANPR & sightings — P0
- FR-3.1 One stream pull per camera; frame acquisition per the nine required behaviours of `frame_source.py` (`04-feed-rules.md`): PTS-driven timing, TCP-only RTSP, HLS fallback, jittered backoff, loop-discontinuity recovery, credential masking.
- FR-3.2 Tiered processing: ~6–8 active cameras under continuous inference at configured fps; all others registered/viewable/health-monitored. Tier is registry metadata.
- FR-3.3 Motion gate (MOG2) skips inference on static frames; skip rate measured and recorded.
- FR-3.4 Vehicle detection (YOLOX or RT-DETR, Apache-2.0) → plate region → OCR (PaddleOCR) on the plate crop only, never a full frame.
- FR-3.5 Sightings stored per contract §2: normalised + raw plate, confidence, camera, PTS-derived UTC timestamp, bbox, vehicle class, ~2 KB plate crop. 60-second per-plate-per-camera dedupe.
- FR-3.6 Search UI: filter sightings by plate (partial), camera, time range, min confidence; results show crop thumbnails.

### FR-4 Watchlist & real-time alerts — P0
- FR-4.1 Watchlist CRUD (contract §3), seeded with 5–10 plates observed in the feeds plus 20–30 representative invented entries; provenance recorded.
- FR-4.2 Matching is local against a cached list: exact → ambiguity-map → Levenshtein ≤1 (contract §6). Partial reads (<8 chars) never alert.
- FR-4.3 Sighting persisted **before** matching runs; alert persisted **before** SSE broadcast. 5-minute per-plate-per-camera alert cooldown.
- FR-4.4 Live alert panel via SSE within ~2 s, newest first, severity-coded, showing plate, **crop**, camera, department, timestamp, match type; acknowledge persists; links to the route view.

### FR-5 Route reconstruction — P0 (the scored moment)
- FR-5.1 `GET /api/plates/{plate}/route` returns exactly the contract §7 response: ordered stops with camera/department/coordinates/timestamps/crops, elapsed times, implied speed (sanity flag, not claim), distance, duration, `departments_crossed`, and flagged `gaps`.
- FR-5.2 Fuzzy matches surface as visibly-marked candidates, never silently merged.
- FR-5.3 Route UI: numbered pins in time order, polyline dashed across gaps, timeline panel with crops, header with first/last seen, duration, distance, cameras, **departments crossed prominent**.

### FR-6 Reports — P0 (named deliverable)
- FR-6.1 `GET /api/reports/detections`: detected vehicles and plates with timestamps, filterable by camera/time/plate, exported as CSV and printable PDF/HTML; per-route export for a single vehicle. Samples saved to `deliverables/`.

### FR-7 Bonus analytics — P2 (only if GATE C passes)
- FR-7.1 Object detection surfaced: per-class counts per camera over time, in UI and report (exposes work the detector already does).
- FR-7.2 Intrusion detection: zone editor (normalised polygons/lines on the camera record), zone-entry and line-cross events, alerts for high-severity zones.
- FR-7.3 Pipeline 3 evidence capture (only if genuinely ahead): fixed-size ring buffer per active camera; on watchlist match, promote a ±30 s clip with SHA-256 and audit row, linked from the alert.

### FR-8 Platform APIs — P1
- FR-8.1 Full API surface per contract §7 under `/api`, OpenAPI-documented, with `/health` and `/stats` backing the dashboard header.

## 5. Non-functional requirements

| NFR | Requirement |
|---|---|
| **Hardware budget** | Runs on Ryzen 5 3550H / 8 GB RAM / GTX 1650 4 GB VRAM. Detector + OCR < ~3 GB VRAM; SQLite only; no Postgres/Kafka/Docker in the demo. Sustained (10-min, post-thermal) throughput measured, not assumed. |
| **Feed compliance** | Every item on the official pre-submission checklist observed, not intended: TCP-only RTSP, PTS timing, gap tolerance, tested reconnect, non-fatal decoder warnings, catalogue-driven config, mixed codec/resolution handling, loop-cut recovery. |
| **Security** | Credentials from environment only; never committed, logged, stored or shown unmasked. No URL with a credential persists anywhere. Consume-only against the gateway. |
| **Privacy & auditability** | Watching ≠ storing: live view persists nothing; analytics persists text + ~2 KB crops; full video persists only on a logged watchlist match (Pipeline 3), with hash and audit row. Stated as a design position in the deck. |
| **Licensing** | Open-source, procurement-safe: Apache-2.0/MIT/BSD components only. No Ultralytics (AGPL), no Elasticsearch, no Redis. Licences re-verified before submission. |
| **Honesty of claims** | Every number labelled measured vs modelled. Measured numbers come from code that ran (fps/camera sustained, vehicles/camera/minute, VRAM/RAM peaks, motion-skip rate, plate-read rate) and are recorded in `plan/STATUS.md`. |
| **Timestamps** | Timezone-aware UTC ISO 8601 in storage; local time at display only. |
| **Resilience** | Worker supervisor restarts dead per-camera workers; graceful shutdown closes every capture; no RAM growth over a 10-minute run. |

## 6. Deliverables (due 15 September 2026)

1. **Solution presentation** (PPT/PDF) — model choice + justification (Hybrid: Model 1 + Model 2 + Pipeline 3), architecture, analytics approach, watchlist methodology, technologies, scalability/interoperability/security, operational benefits.
2. **Technical proposal (HLD)** — all eight required elements incl. AI approach (ANPR, FRS, object detection, tracking), alert workflow, 80,000-camera scaling, and department-wise information requirements. Covers the ten dimensions.
3. **Demo video, own feed** — 2–3 min: onboarding, detection, watchlist correlation, automatic alert (run sheet: `docs/05-demo-script.md`).
4. **Live demo, government feed** — onboarding, viewing, analytics output, **timestamped detection report**.
Optional: hosted URL + test credentials; source repository link.

## 7. Assumptions, dependencies, open questions

- **A1:** Sandbox catalogue and feeds remain reachable through 15 Sep. Mitigation: fallback footage of every component recorded as soon as it works.
- **A2:** HLS is reachable from the dev network; RTSP/WHEP reachability unknown until the P0 probe. Transport is decided per camera by GATE A, recorded in the registry.
- **A3:** Catalogue may or may not carry department/coordinates (GATE A inspection). If absent, seeded and disclosed.
- **A4:** Public statement says ~50 cameras; the guide lists cam01–cam30. Build against the catalogue; note the discrepancy in the submission.
- **A5:** Watchlist is self-created, as the rules explicitly permit; observation-seeded entries recorded in STATUS.md.

## 8. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| OCR quality poor on sandbox footage | Route sparse | GATE B: don't tune models; concentrate on best cameras, accept lower recall |
| Route fails end-to-end | Loses the scored moment | GATE C: cut P5/Pipeline 3 without debate; all time to P4 then P6 |
| Feeds down on demo day | No live material | Record fallback footage of each working component immediately |
| Thermal throttling invalidates measurements | Scaling claims wrong | Measure after 10 sustained minutes only |
| Documentation squeezed by code | 3 of 7 evaluation areas are documentation | P6 is mandatory in the plan and must not be compressed |
| Credential leak in repo/video/screenshot | Disqualifying | Rule 1 of CLAUDE.md; pre-submission sweep of frames, logs, history |

## 9. Traceability — evaluation area → requirement → phase

| Evaluation area | Requirements | Phase |
|---|---|---|
| 1. Test case on government feed | FR-1, FR-3, FR-5, FR-6 | P0–P2, P4 |
| 2. Solution presentation | §6 deliverable 1 | P6 |
| 3. Solution architecture (HLD) | §6 deliverable 2, non-goals described | P6 |
| 4. Working platform & demo | FR-1–FR-6 | P1–P4 |
| 5. Analytics output (ANPR + intrusion + object + reports) | FR-3, FR-6, FR-7 | P2, P5 |
| 6. Scalability & PoC readiness (~80k) | NFR measurements → HLD model | P0/P2 gates, P6 |
| 7. Submission completeness | `docs/06-submission-checklist.md` | P6 |

Bonus criteria addressed: hybrid architecture with operational value (locked design), cross-camera tracking (FR-5), analytics beyond ANPR (FR-7), privacy/auditability (NFR + Pipeline 3), dashboards/alerts/health/APIs (FR-1, FR-4, FR-8).
