# Gujarat Police Innovation Challenge 2026 — Complete Scrape

**Source:** https://sentinel.gujarat.gov.in (all public pages: `/`, `/about`, `/phases`, `/resource`, `/problems`, `/schedule`, `/faqs`, `/contact`, `/register`)
**Scraped:** 9 September 2026
**Also called:** Gujarat CCTV Hackathon 2026 / Sentinel / CCTV Integration Hackathon
**Organiser:** Home Department, Government of Gujarat — State Crime Records Bureau (SCRB)

> ⚠️ **Deadline: 15 September 2026** — six days out. Registration and submission close together.

---

## 1. The Ask, in One Paragraph

Build a **deployment-ready Integrated Video Management & Analytics Platform** that (a) onboards heterogeneous CCTV cameras from many government departments into one platform, (b) runs continuous AI video analytics (ANPR primarily, plus face/person/object detection) on those live feeds, (c) cross-references detections against a **searchable watchlist database** (stolen vehicles, wanted persons, missing persons, blacklisted vehicles), and (d) fires **automated real-time alerts** on a match, with GIS visualisation and searchable movement history. It must be architected to scale to **~80,000 cameras statewide**.

Explicitly *not* a proof of concept: "Mock-ups, animations, simulated interfaces, or concept videos without an operational backend will not be considered."

---

## 2. Key Dates & Logistics

| Milestone | Date |
|---|---|
| Registration opens | 4 August 2026 |
| **Last date to apply + upload submission** | **15 September 2026** |
| Shortlisting announcement | 15 September 2026 (evening) |
| Hackathon event (Grand Finale) | **22–23 September 2026** (extended from original dates) |
| Results & prize distribution | 23 September 2026 |

- **Venue:** i-Hub Gujarat, Gandhinagar
- **Contact:** sentinel.hackathon@gujarat.gov.in · +91 95370 89982
- **Address:** State Crime Records Bureau (SCRB), next to Police Bhawan, Sector 18, Gandhinagar, Gujarat 382009
- **Helpdesk hours:** Mon–Sat, 10:00–18:00
- **Registration:** free; email-OTP verified; roles = Student/Team/Researcher/Professional · DPIIT Startup · Company/SI. Form fields: name, email, mobile, role, password.

**Partners:** Dhirubhai Ambani University (DA-IICT) and National Forensic Sciences University (NFSU) as Knowledge Partners (technical expertise, mentoring, evaluation support in AI/CV/video analytics/cybersecurity/digital forensics); i-Hub Gujarat as Tech Partner and venue.

---

## 3. Background — The Real Problem

- **26 different Government Departments** operate independent, standalone CCTV systems across Gujarat.
- Mix of **analog and IP cameras**, geographically dispersed — border districts through Valsad, Dahod, Somnath, Jamnagar, Dwarka. Sites up to **~1,000 km apart**.
- Storage is fragmented: some departments cloud-based, others local. **Retention varies: 7 days for some, 15+ days for others.**
- Deployment patterns differ by department:
  - **Home Department** — public domain: traffic monitoring, law & order, crime detection.
  - **Food & Civil Supplies** — godowns, PDS shops.
  - **RTO** — offices, testing tracks, checkpoints.
- The platform should *also* support viewing public-facing private CCTV (societies, malls, commercial establishments) **wherever feasible and permitted**.
- Government already runs critical databases the system must integrate with: **VAHAN, SARTHI, eGujCop (Gujarat Police CCTNS), AFIS, NAFIS** — holding arrested persons, stolen vehicles, wanted criminals, missing persons, unidentified dead bodies, fingerprints.

### Core goal (verbatim intent)
> Propose a secure, scalable, interoperable, technically feasible, and cost-effective approach that uses existing infrastructure to the maximum practical extent.

### The four named key challenges
1. **Heterogeneous infrastructure** — different vendors, VMS platforms, AMC periods, storage architectures, camera types, formats, feed-sharing protocols.
2. **Geographical dispersion** — camera sites up to ~1,000 km apart.
3. **Unified analytics** — analytics and event handling across all onboarded cameras through one framework.
4. **Scalability** — new cameras, departments, systems and future analytics onboarded without major redesign.

---

## 4. The Five Reference Solution Models

> **Model 1 is mandatory.** It is the common CCTV registry and GIS foundation and must be combined with one or more of Models 2/3/4 (or a hybrid).

### Model 1 — Centralised CCTV Registry & GIS Mapping *(MANDATORY)*
*Metadata & asset visibility layer. No centralised live streaming or recording.*

Creates a unified inventory/visibility layer: camera metadata (location, department, camera type, ownership, connectivity status, storage details) on a GIS map, for planning integration, identifying monitoring gaps, infrastructure assessment and decision support.

**Key features:** bulk import + manual entry + API onboarding · interactive GIS map with department/type/status/coverage layers · camera health and maintenance-status monitoring · gap-analysis reports for uncovered zones and ageing infrastructure · role-based search, filtering, export, metadata audit trails.

**Suggested stack:** Leaflet / OpenLayers / PostGIS · Node.js or Python (Django/FastAPI) · PostgreSQL + PostGIS · React.js · department-wise RBAC.

**Deliverables:** working registry portal with GIS map view · bulk + manual onboarding demo · sample onboarded camera-metadata dataset · registry API documentation · sample gap-analysis report.

**Flow:** Department CCTV assets → onboarding & validation (bulk/manual/API) → central registry (standardised metadata) → PostgreSQL + PostGIS → GIS dashboard & APIs.

---

### Model 2 — Unified Viewing & Metadata Analytics
*Direct connection to each departmental CCTV/VMS. **No** middleware layer.*

A single viewing interface that connects **directly** to each departmental system via RTSP, ONVIF, vendor SDKs or APIs. Existing departmental VMS/storage keep operating independently and untouched. Focus is centralised viewing plus selective metadata/analytics — ANPR metadata, event tagging, camera-wise indexing, searchable vehicle movement records — **without** centralised storage of all video.

**Key features:** feed aggregation (RTSP/ONVIF/vendor APIs) · ANPR metadata generation · event tagging and camera-wise indexing · searchable vehicle-movement records · configurable video walls and multi-camera grids · alerts for tagged events and vehicles of interest.

**Suggested stack:** WebRTC / HLS relay · ONVIF / RTSP libraries / vendor SDKs · ANPR (open-source or custom) · Node.js or Python microservices · Kafka, Elasticsearch, PostgreSQL.

**Deliverables:** unified viewer connected to sample feeds from **at least two different systems** · ANPR demo on live or recorded feeds · searchable metadata dashboard · architecture note proving departmental systems remain unaffected.

---

### Model 3 — VMS Federation & Middleware Integration
*A middleware/federation layer sits between the platform and departmental VMSs. This is the difference from Model 2.*

Middleware integrates multiple departmental VMS platforms via APIs, SDKs, metadata exchange, event-sharing or standard protocols. Departments retain infrastructure and operational control; the federation layer exposes **one unified interface** to downstream apps, dashboards and AI services.

**Key features:** adapter/plugin architecture per VMS vendor · metadata exchange bus for camera and event info · cross-system event-correlation engine · unified workflow and alert dashboard · extensible connector framework for future vendors.

**Suggested stack:** Node.js / Java (Spring Boot) · Kafka / RabbitMQ · Kong / NGINX API gateway · PostgreSQL + Redis · React.js.

**Deliverables:** working middleware federating **at least two different systems** · unified event-correlation dashboard · adapter/plugin architecture documentation · sample federated analytics report.

---

### Model 4 — Central VMS & AI Platform
*Fully centralised monitoring, recording, storage, playback and advanced analytics.*

One consolidated statewide Central VMS. Heaviest infrastructure ask: scalable storage, high-bandwidth connectivity, centralised compute, redundancy, cybersecurity controls, large-scale ingestion and real-time processing.

**Key features:** centralised feed ingestion · tiered hot/warm/cold storage · ANPR, face recognition, crowd/vehicle counting, anomaly detection · statewide vehicle tracking and route reconstruction · integration readiness for VAHAN, SARTHI, eGujCop, AFIS, NAFIS · redundancy, DR, encryption, network segmentation, RBAC.

**Suggested stack:** custom or extended open-source VMS · S3-compatible distributed object storage / Ceph · Kafka + GPU-based analytics · PostgreSQL / TimescaleDB · Kubernetes · high-bandwidth backbone with regional edge.

**Deliverables:** working centralised VMS prototype on sample multi-department feeds · ANPR + multi-location vehicle-tracking demo · **scalability and load-test report for ~80,000 cameras** · disaster-recovery and redundancy design · security architecture document.

---

### Model 5 — Hybrid / Innovative Architecture
The four models are *indicative reference models*. Teams may combine elements of two or more, or submit a fully innovative customised architecture — provided it addresses the stated functional, interoperability, security, scalability, analytics and implementation requirements.

---

## 5. Expected Solution Approach (Step 3)

Build a deployment-ready solution that **continuously processes the CCTV feeds provided through the hackathon portal**, integrating live video streams with a **searchable watchlist database** (stolen vehicles, wanted persons, missing persons, blacklisted vehicles, suspect watchlists, or other entities of interest) for continuous AI analysis and automated alerting on match.

You must design the complete workflow: **database structure, matching logic, alerting mechanism, and user interface.** Teams create and use their own representative datasets.

### Architecture principles (mandatory posture)
Open, modular, scalable, secure, standards-based, **vendor-neutral**. No vendor lock-in. Seamless integration/replacement/upgrade/expansion of cameras, VMS, analytics engines, storage, AI modules via documented standard APIs, open protocols, SDKs and modular adapter-based frameworks. Technology-agnostic, heterogeneous multi-vendor support, future enhancement without significant redesign.

### The ten dimensions every submission must cover
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

## 6. The Live Test Case (Step 4) — How You Actually Get Scored

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

## 7. Deliverables — Exact Submission Checklist (Step 5)

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

---

## 8. Scalability Requirement (Step 6) — Scaling to ~80,000 Cameras

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

## 9. Evaluation Framework (Step 7)

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

---

## 10. The Sandbox — Dataset & Streaming Infrastructure

**Dataset:** ~12 hours of real CCTV footage from each of **30+ cameras** across **five departments — Health, Police, GSRTC, Panchayat, Municipal Corporation.** Recorded footage is ingested by a **Python-based streaming middleware**, synchronised on a common timeline, and served as **simulated live video** on a dedicated endpoint per camera. (Simulated rather than production-live to protect production CCTV security and give every team an identical, repeatable, fair test.)

At technical evaluation, ~50 geographically distributed cameras are available via the Resources page.

### Endpoints

| Protocol | Endpoint | Intended for |
|---|---|---|
| RTSP | `rtsp://<host>:8554/stream/<id>` | AI inference (OpenCV, GStreamer, FFmpeg, DeepStream) |
| WebRTC (WHEP) | `http://<host>:8889/stream/<id>/whep` | Low-latency browser preview |
| HLS | `http://<host>/live/stream/<id>/index.m3u8` | Dashboards, mobile, restricted networks |

**Always start from the catalogue, never hard-coded endpoints:**
```
curl -s http://<host>/api/ingest
```
Returns every camera with id, location, codec, live status, stream properties and all three URLs. *"Camera ids and the set of available cameras can change; the catalogue is the contract, the URL pattern is not."*

Every camera is a live RTP/RTSP stream: one second of video takes one second to arrive, frames carry monotonic PTS, **no seeking, no byte-range fetching, no running ahead of real time.**

### Connection snippets from the official guide

**OpenCV (Python)**
```python
import os
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
import cv2
cap = cv2.VideoCapture("rtsp://<host>:8554/stream/1", cv2.CAP_FFMPEG)
while True:
    ok, frame = cap.read()
    if not ok:
        break   # reconnect with backoff
    pts_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
```

**GStreamer**
```bash
gst-launch-1.0 rtspsrc location=rtsp://<host>:8554/stream/1 protocols=tcp latency=200 \
  ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! fakesink
# H.265 streams: use rtph265depay and h265parse
```

**FFmpeg / ffprobe**
```bash
ffplay  -rtsp_transport tcp rtsp://<host>:8554/stream/1
ffprobe -rtsp_transport tcp rtsp://<host>:8554/stream/1
```

**NVIDIA DeepStream** — use `nvurisrcbin` / `uridecodebin` with the RTSP URI and set `select-rtp-protocol=4` (TCP). Streams are H.264 or H.265; both decode on `nvv4l2decoder` without CPU demuxing.

### Do's and don'ts (verbatim from the Resources page — these are traps)

**DO — Force RTSP over TCP.** UDP is accepted but fails across NAT and most corporate firewalls; partial UDP delivery produces corrupt frames that look like model bugs. If port 8554 is blocked, use HLS.

**DON'T — Trust the reported frame rate.** `CAP_PROP_FPS` often doesn't match actual delivery rate. Using it to convert pixels-per-frame into speed, dwell time or any time-derived metric produces incorrect results.

**DO — Drive all timing from PTS, never arrival time.** Use `CAP_PROP_POS_MSEC` (OpenCV), buffer PTS (GStreamer) or RTP timestamps. On connect, the gateway replays its buffered GOP so the decoder starts at a keyframe — the first second or two arrives **faster than real time**. A tracker timestamping by arrival will compute impossible velocities after every connection. **Kalman filters and multi-object trackers must be fed PTS deltas.**

**DON'T — Assume a constant frame rate.** Frame intervals aren't uniform. Tolerate inter-frame gaps without treating them as disconnects; motion models must use actual elapsed PTS.

**DO — Reconnect automatically with backoff.** Feeds are supervised and may restart. Exponential backoff starting ~2s, capped ~30s. No tight loops.

**DON'T — Treat join-time decode warnings as fatal.** Mixed H.264/H.265 grid; attaching mid-stream produces messages like `Error constructing the frame RPS` or `Could not find ref with POC` until the first IDR arrives. Normal, self-corrects. Pipelines that abort on first decoder error will bounce.

**DON'T — Assume a uniform grid.** Cameras differ in resolution, codec, frame rate, bitrate. Read per-camera properties from `/api/ingest` and size batching, buffers and decoders accordingly. A fixed-shape inference batch across every camera will not work unscaled.

**DO — Expect a scene discontinuity.** Each feed is a continuous recording that **loops**. At the loop point the scene cuts abruptly, like a camera reboot. Background models, re-ID galleries and track IDs must recover from a hard cut.

**DON'T — Plan around obtaining copies of the footage.** No file download. `/stream/<id>` is a browser playback fallback answering range requests — pulling it with curl/wget yields a partial file that *looks* complete. **Build against a live capture from the start.**

**DON'T — Publish to the gateway.** Consume only. Don't push streams to any path, don't call the gateway's control API.

**DO — Pace your load.** Each connected client gets its own copy of the stream. Open only cameras you're actively processing; close captures you're done with.

### Pre-submission checklist (official)
- [ ] Every client forces RTSP over TCP
- [ ] No timing logic depends on `CAP_PROP_FPS` or frame arrival time
- [ ] Inter-frame gaps don't crash or stall the pipeline
- [ ] Reconnect with backoff implemented **and tested by restarting a feed**
- [ ] Decoder warnings on join are logged, not fatal
- [ ] Camera list and per-camera properties read from `/api/ingest`
- [ ] Pipeline handles mixed H.264/H.265 and mixed resolutions
- [ ] Behaviour is sane across a scene discontinuity

**Support:** report feed problems with camera id, exact URL, client + version, UTC timestamp, and client-side error log. Confirm the camera's live status in `/api/ingest` before reporting it down.

---

## 11. Format, Phases & Prize Money — ₹51,00,000 Total

### Phase 1 — Sandbox Round (₹18,00,000)
Teams integrate with the provided test feeds, competing within their category. **Top 3 from each category** take Phase 1 prizes and advance as the six finalists. Phase 1 prize money **doubles as a grant** to fund building the Phase 2 solution.

| Position | Category 1 (students, small/medium startups) | Category 2 (large startups & companies) |
|---|---|---|
| 1st | ₹4,00,000 | ₹5,00,000 |
| 2nd | ₹2,00,000 | ₹3,00,000 |
| 3rd | ₹1,00,000 | ₹2,00,000 |
| **Total** | **₹7,00,000** | **₹10,00,000** |

Plus **4 consolation awards of ₹25,000 each** (₹1,00,000) to the next four best teams across both categories.

### Phase 2 — Production Round / Grand Finale (₹31,00,000)
The 6 top-performing teams overall integrate with **real CCTV feeds at scale**, irrespective of category, evaluated directly by Gujarat Police leadership and a technical jury.

| Position | Prize |
|---|---|
| 1st (Grand Winner) | ₹16,00,000 |
| 2nd (1st Runner Up) | ₹8,00,000 |
| 3rd (2nd Runner Up) | ₹7,00,000 |

### Additional awards (₹2,00,000)
- **Consolation:** ₹50,000 each to the 3 finalists outside the top three = ₹1,50,000
- **Special Jury Award:** ₹50,000 at jury discretion for outstanding innovation, technical excellence, originality or impact

**Grand total: ₹18,00,000 + ₹31,00,000 + ₹2,00,000 = ₹51,00,000**

---

## 12. Eligibility

**Category 1 (Academic / Research / Startup):** students, graduates, postgraduates, doctoral scholars, academic or research teams, and **DPIIT-recognised startups** (valid DPIIT Startup Recognition Certificate required at registration or verification).

**Category 2 (Industry / Enterprise):** companies, industry partners, system integrators, technology solution providers, LLPs, partnerships and other established enterprises — essentially any business entity not eligible under Category 1.

Individual and team participation both allowed. Registration is free.

**Open-source expectation:** "All solutions should use open-source technologies." Recommended stacks across problem statements: React, Python, Node.js, PostgreSQL, PostGIS, WebRTC, RTSP, Kafka, RabbitMQ, TensorFlow, PyTorch, FFmpeg, GStreamer, Leaflet, OpenLayers. Suggested stacks are references, not restrictions.

---

## 13. What's Behind Login (Not Captured)

The following require a registered account and were **not** accessed:
- `/login` → the **Sentinel Gujarat Live Portal** ("Login to Access Live Camera") — the actual sandbox host, camera catalogue at `<host>/api/ingest`, and the ~50 live feeds
- Per-model "Login to Apply" flows on the Problem Statements page
- Any datasets, APIs and reference materials distributed post-registration

`/api/ingest` on the main domain returns 404 — the catalogue lives on the separate sandbox host revealed after login. **Registering is the gate to everything operational**, and with the 15 September deadline that's the first action item.

---

## 14. Reading Between the Lines — What Wins This

A few things the site states or strongly implies that shape strategy:

1. **Model 1 is mandatory and cheap to nail.** A GIS registry with bulk/API onboarding, health monitoring and gap-analysis reports is well-scoped, fully specified, and a guaranteed scoring component. Build it properly and completely.
2. **ANPR is the only truly mandatory analytic.** Evaluation says "additional reliable analytics beyond the mandatory ANPR requirement" earns bonus — so ANPR accuracy on the actual sandbox footage is the floor, not the ceiling.
3. **The vehicle-tracking test is the make-or-break.** A registration number handed over live, and you must produce a complete timestamped, location-wise route across ~50 cameras. This needs cross-camera correlation working under real conditions — plan for plate-read noise, partial reads, and fuzzy matching.
4. **The streaming guide's warnings are a scoring rubric in disguise.** PTS-based timing, TCP transport, reconnect with backoff, loop-point recovery, mixed codecs — these read like the exact failure modes the organisers watched teams hit. Every one is a cheap defensive fix and an expensive bug on demo day.
5. **"Deployment-ready, not a prototype" is stated four separate ways.** Working backend, hosted URL with test credentials, source repo, load-test report to 80,000 cameras. The paperwork (HLD, sizing, cost-benefit, DR, rollout plan) is worth as much as the code — three of seven evaluation areas are documentation quality.
6. **Category matters for prize odds.** As a student/small-startup entry you compete in Category 1 for the top-3 slots, then all six finalists compete flat in Phase 2.

---

*Compiled from the public pages of sentinel.gujarat.gov.in on 9 September 2026. Content behind registration was not accessed.*
