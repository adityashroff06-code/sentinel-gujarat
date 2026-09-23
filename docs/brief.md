# Brief — why Sentinel exists and what must be delivered

**Editor's note (20 Sep 2026).** This is the requirements document for the fresh build. Every section marked *verbatim* is copied unchanged from its source — the previous build's `PRD.md` (dated 13 Sep, requirements frozen for the 15 Sep submission) or the portal scrape `docs/reference/hackathon-brief.md`. The only new facts are in §0. Where a verbatim block mentions "15 September", read the date in §0.

---

## 0. Dates and status (the only new section)

| | |
|---|---|
| Previous submission | 15 September 2026 — documents plus demo material, from `D:\projects\Sentinel_Repo` |
| **Submission deadline** | **28 September 2026** — confirmed on the portal 22 Sep (date-extension announcement and Schedule page): "Last Date to Apply and Upload Your Submission", shortlisting announced the same day. An upload, not a live evaluation |
| On-site hackathon | **12–13 October 2026** at i-Hub Gujarat, results 13 Oct. "A designated vehicle number is provided to participants on the hackathon day" (FAQ 27) — the scored plate test happens there, two weeks after this plan ends |
| Hosted demo | Required by us, not by the portal (Step 5 lists it as optional): a URL with **test login credentials for the screening committee**, live from Thu 24 (tasks S3.0, S3.5; decisions F41, F42). Evaluation area 07 counts "documents, videos, reports, links, credentials" for completeness |
| Build window | Mon 21 – Thu 24 Sep: the application · Fri 25: every deliverable in §7 (GATE D 09:00, code freeze at end of day) · Sat 26: soak and rehearsal · Sun 27: submit · Mon 28: buffer · nothing built in the last 48 h is demoed (`docs/tasks.md` calendar) |
| Entry category | **Category 1** — registered as students (Adi, 23 Sep; task S0.3, closes O8) |
| Sandbox | `https://cctv.corp8.cloud` — 30 cameras in the catalogue, 5 departments (see `docs/sandbox-findings.md`) |

---

## 1. Problem statement *(verbatim, PRD §1)*

26 Gujarat government departments operate independent, standalone CCTV systems — mixed analog/IP cameras, different vendors and VMS platforms, fragmented storage (cloud and local, 7–15+ day retention), sites up to ~1,000 km apart. No single view exists across them. When police need to trace a vehicle across the state, footage must be requested department by department, manually.

The hackathon sandbox simulates this: live feeds from cameras spanning five departments (Health, Police, GSRTC, Panchayat, Municipal Corporation), heterogeneous in codec, resolution, frame rate and bitrate, reachable over HLS/RTSP/WHEP.

**The core job to be done:** given a vehicle registration number handed over live on evaluation day, return that vehicle's complete, timestamped, location-wise route across the camera network — and continuously cross-reference all feeds against a watchlist with automated real-time alerts.

---

## 2. The live test case — how you are scored *(verbatim, hackathon brief §6)*

**Scenario:** After registration, teams access details, resources and **live camera feeds from ~50 geographically distributed cameras** via the Resources page. Cameras span departments and differ in technology, format, VMS platform and storage.

**What you must do:**
- Onboard the available cameras onto **one integrated platform**.
- Enable centralised monitoring and AI-powered video analytics.
- **On evaluation day you are handed a vehicle registration number.** Your system must identify, trace and present that vehicle's movement across the integrated CCTV network — across camera locations and times.
- Demonstrate continuous cross-referencing of live feeds against a representative watchlist database with automated real-time alerts on match. (Your own watchlist DB is fine.)

**Expected output:**
- Identification and tracing of the designated vehicle from the registration number given at evaluation.
- **Complete route traversed**, with timestamped, location-wise movement history.
- Working watchlist DB integrated and continuously cross-referencing, with automated real-time alert generation.
- Evidence of successful CCTV integration, AI analytics, interoperability, scalability and end-to-end performance.

---

## 3. Users *(verbatim, PRD §2)*

| User | Needs |
|---|---|
| **Evaluation jury** (primary) | See the test case succeed live; judge the documentation on the ten dimensions; verify claims against the working system |
| **Control-room operator** | Live multi-camera wall, trustworthy alerts (with plate crops), plate search, route view, acknowledgement workflow |
| **Department admin / planner** | Camera registry with health status, GIS coverage view, gap-analysis reports, onboarding (manual/bulk/API) |
| **Investigating officer** | Plate → route query, timestamped detection reports (CSV/PDF), evidence with chain of custody |

---

## 4. Goals and success criteria *(verbatim, PRD §3)*

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

> Fresh-build note: G4's date is now §0's. The non-goal "authentication beyond a single demo role" is **withdrawn** — the previous build's review rated zero auth its second-worst defect; the fresh build ships an API key with viewer/admin roles from day one (`docs/decisions.md`).

---

## 5. Functional requirements *(verbatim, PRD §4)*

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
- FR-3.2 Tiered processing: ~6–8 active cameras under continuous inference at configured fps; all others registered/viewable/health-monitored. Tier is registry metadata. Every camera gets a connection check; the best-working ones it picks go active — never a fixed list (decision F49).
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

> Fresh-build note: `03-data-contracts.md` and `04-feed-rules.md` above are now `docs/api.md` (Part A) and `docs/feed-rules.md`. Two requirements the previous build left open are now in scope: a **watchlist screen** and **onboarding screens (form + CSV upload)** — the APIs existed, the UI did not, and Model 1 requires onboarding to be *demonstrated*.

---

## 6. Non-functional requirements *(verbatim, PRD §5)*

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

> Fresh-build note: `plan/STATUS.md` is now `docs/progress.md`.

---

## 7. Deliverables — exact submission checklist *(verbatim, hackathon brief §7)*

### 1. Solution Presentation (PPT/PDF)
- Proposed model (Reference Model 1–5, Hybrid, or Customised) **with justification**
- Solution overview, objectives, key innovations
- High-level system architecture and end-to-end workflow
- AI video analytics approach — detection, recognition, event analytics
- Methodology for correlating live feeds with watchlist DBs and generating real-time alerts
- Key technologies, frameworks, tools
- Scalability, interoperability, security, deployment considerations
- Expected operational benefits and impact on policing/public safety

### 2. Technical Proposal — High-Level Design (HLD)
- Overall solution architecture with high-level diagrams and component interactions
- Approach for integrating heterogeneous cameras, NVRs and VMS into a unified platform
- Architecture for ingesting/processing/managing live streams from geographically dispersed locations
- Approach for integrating live feeds with watchlist databases and continuously correlating analytics results into real-time alerts
- AI analytics approach: **ANPR, Facial Recognition (FRS), object detection, person and vehicle tracking**, plus anything else proposed
- Alert generation and notification workflow — prioritisation, visualisation, user interaction
- Scalability, interoperability, security, performance for statewide deployment to **~80,000 cameras**
- Technical prerequisites, assumptions, and **information required from participating departments** to assess integration feasibility

### 3. Demonstration on Your Own Feed
Screen recording, **max 2–3 minutes**, showing:
- Onboarding and processing of live or recorded CCTV feeds
- AI detection and analytics (ANPR, FRS, or other)
- Correlation of detected entities against a representative watchlist DB
- Automatic real-time alert generation and visualisation on match

> Must be a **fully functional working solution.** Mock-ups, animations, simulated interfaces or concept videos without an operational backend **will not be considered.**

### 4. Live Demonstration on Government-Provided Feed
- Onboard the Government-provided feed(s)
- Demonstrate successful onboarding and live/recorded viewing
- Demonstrate video-analytics output on that feed
- Submit screen recording **plus an output report showing detected vehicles/number plates with timestamps**

### How to submit
- Unlisted YouTube link (visibility: Unlisted), **or** Google Drive / OneDrive link set to "Anyone with the link — Viewer"
- Optionally: URL to hosted platform **with test login credentials** for the screening committee
- Optionally: GitHub / GitLab repository link with source code

### Model 1 and Model 2 deliverables *(verbatim, hackathon brief §4)*

**Model 1 deliverables:** working registry portal with GIS map view · bulk + manual onboarding demo · sample onboarded camera-metadata dataset · registry API documentation · sample gap-analysis report.

**Model 2 deliverables:** unified viewer connected to sample feeds from **at least two different systems** · ANPR demo on live or recorded feeds · searchable metadata dashboard · architecture note proving departmental systems remain unaffected.

> The full tick-list, including the ten dimensions and the scalability section, is `docs/submission-checklist.md`. The compliance audit that found 13 forgettable gaps is `docs/reference/model-2-1-architecture-spec.md` §7.

---

## 8. Scalability requirement *(verbatim, hackathon brief §8)*

Participants must explain:
- Central, regional and **edge** compute requirements
- GPU / accelerator requirements for video analytics
- Expected network bandwidth and **low-bandwidth strategies**
- Hot / warm / cold storage assumptions based on retention periods
- Load balancing, horizontal scaling, monitoring, logging, health checks
- High availability, backup, disaster recovery, cybersecurity controls
- **Estimated implementation and operational costs**
- Phased statewide rollout plan

---

## 9. Evaluation framework *(verbatim, hackathon brief §9)*

Qualitative assessment across common areas first, then bonus consideration.

### A. Common evaluation areas
| # | Area | What's judged |
|---|---|---|
| 1 | **Successful Test Case** | Onboarding and operation on the Government-provided feed, incl. live/recorded viewing and required analytics output |
| 2 | **Solution Presentation** | Clarity/completeness of PPT/PDF — problem understanding, model chosen, justification, overview, key features |
| 3 | **Solution Architecture** | Technical soundness, feasibility, security, interoperability, clarity of HLD and diagrams |
| 4 | **Working Platform & Demonstration** | Maturity of the actual working platform on own feed + Government feed |
| 5 | **Video Analytics Output** | Quality/usefulness of ANPR, vehicle/person detection, intrusion detection, object detection, timestamps, output reports |
| 6 | **Scalability & PoC Readiness** | Readiness to scale to ~80,000 cameras; preparedness for on-site PoC |
| 7 | **Submission Completeness** | All documents, videos, reports, links, credentials, supporting info complete, accessible, consistent |

### B. Bonus consideration
Bonus will **not** compensate for failing a mandatory requirement. Awarded for capabilities that are relevant, functional and demonstrated in the working solution:
- Innovative hybrid/customised architecture with clear operational value
- Advanced cross-camera vehicle movement tracking or multi-camera correlation
- Additional reliable analytics beyond mandatory ANPR
- Strong edge processing, bandwidth optimisation, low-connectivity operation
- Enhanced cybersecurity, privacy protection, auditability, RBAC
- Operational dashboards, automated alerts, health monitoring, integration-ready APIs

**Three of seven areas are documentation.** Do not let the code eat all the time. Evaluation Area 5 names **four** analytics, not one — an ANPR-only submission is scored against a rubric listing intrusion detection and object detection explicitly.

### The ten dimensions every submission must cover *(verbatim, hackathon brief §5)*
1. Overall Architecture
2. Integration Strategy
3. AI & Video Analytics
4. Cybersecurity Architecture
5. Deployment Architecture
6. Infrastructure Sizing
7. Cost-Benefit Analysis
8. Department-wise Information Requirements
9. Scalability Strategy
10. Future Roadmap

---

## 10. Assumptions, dependencies, discrepancies *(verbatim, PRD §7, plus the mission note)*

- **A1:** Sandbox catalogue and feeds remain reachable through 15 Sep. Mitigation: fallback footage of every component recorded as soon as it works.
- **A2:** HLS is reachable from the dev network; RTSP/WHEP reachability unknown until the P0 probe. Transport is decided per camera by GATE A, recorded in the registry.
- **A3:** Catalogue may or may not carry department/coordinates (GATE A inspection). If absent, seeded and disclosed.
- **A4:** Public statement says ~50 cameras; the guide lists cam01–cam30. Build against the catalogue; note the discrepancy in the submission.
- **A5:** Watchlist is self-created, as the rules explicitly permit; observation-seeded entries recorded in STATUS.md.

**Known discrepancy** *(verbatim, 00-mission.md)*: The public problem statement references ~50 cameras; the post-login guide lists `cam01` … `cam30`. Build against the catalogue (`cameras.json`), which the organisers call the contract. Note the discrepancy in the submission rather than assuming either number.

> Fresh-build note: A2 and A3 are now answered — see `docs/sandbox-findings.md` (RTSP works from the laptop for 27/30 cameras; the catalogue carries id and name only, so `data/camera_seed.csv` assigns department, coordinates and tier, disclosed). A1's mitigation still stands: record fallback footage the moment each component works.

---

## 11. Risks *(verbatim, PRD §8)*

| Risk | Impact | Mitigation |
|---|---|---|
| OCR quality poor on sandbox footage | Route sparse | GATE B: don't tune models; concentrate on best cameras, accept lower recall |
| Route fails end-to-end | Loses the scored moment | GATE C: cut P5/Pipeline 3 without debate; all time to P4 then P6 |
| Feeds down on demo day | No live material | Record fallback footage of each working component immediately |
| Thermal throttling invalidates measurements | Scaling claims wrong | Measure after 10 sustained minutes only |
| Documentation squeezed by code | 3 of 7 evaluation areas are documentation | P6 is mandatory in the plan and must not be compressed |
| Credential leak in repo/video/screenshot | Disqualifying | Rule 1 of CLAUDE.md; pre-submission sweep of frames, logs, history |

---

## 12. Traceability — evaluation area → requirement *(verbatim, PRD §9; phase column dropped)*

| Evaluation area | Requirements |
|---|---|
| 1. Test case on government feed | FR-1, FR-3, FR-5, FR-6 |
| 2. Solution presentation | §7 deliverable 1 |
| 3. Solution architecture (HLD) | §7 deliverable 2, non-goals described |
| 4. Working platform & demo | FR-1–FR-6 |
| 5. Analytics output (ANPR + intrusion + object + reports) | FR-3, FR-6, FR-7 |
| 6. Scalability & PoC readiness (~80k) | NFR measurements → HLD model |
| 7. Submission completeness | `docs/submission-checklist.md` |

Bonus criteria addressed: hybrid architecture with operational value (locked design), cross-camera tracking (FR-5), analytics beyond ANPR (FR-7), privacy/auditability (NFR + Pipeline 3), dashboards/alerts/health/APIs (FR-1, FR-4, FR-8).
