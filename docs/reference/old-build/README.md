<div align="center">

# SENTINEL

**Integrated Video Management and Analytics Platform**

One platform over 26 departments' CCTV systems. Hand it a registration number, get back that vehicle's complete timestamped route across the whole camera network.

Built for the [Gujarat Police Innovation Challenge 2026](https://sentinel.gujarat.gov.in/). Home Department and State Crime Records Bureau.

[![Python](https://img.shields.io/badge/Python-3.10%20to%203.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/UI-React%2018%20%2B%20Vite-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![ONNX Runtime](https://img.shields.io/badge/Inference-ONNX%20Runtime-005CED?logo=onnx&logoColor=white)](https://onnxruntime.ai/)
[![License](https://img.shields.io/badge/License-Apache%202.0-D22128?logo=apache&logoColor=white)](LICENSE)
[![Model licensing](https://img.shields.io/badge/Model%20stack-Apache%2FMIT%2FBSD%20only-39A56A)](#licensing-is-a-procurement-decision)

</div>

---

## What this is

Gujarat runs CCTV across 26 government departments on systems that do not talk to each other: analog and IP cameras mixed together, different vendors, different VMS platforms, storage in different places under different retention rules, and sites as much as 1,000 km apart. Tracing one vehicle today means asking each department separately, by hand.

Sentinel puts one platform over those systems without changing any of them. It keeps a single camera registry with a GIS view, runs analytics continuously, checks every plate read against a watchlist, raises alerts automatically, and reconstructs a vehicle's movement across department boundaries from a single registration number.

It is a working system running against the live sandbox camera grid, not a mock-up. Everything below has been run end to end on one laptop with a GTX 1650.

| | |
|---|---|
| **Reference models** | Model 1 (Centralised CCTV Registry and GIS, mandatory) plus Model 2 (Unified Viewing and Metadata Analytics), plus event-triggered evidence capture. Model 3 federation is documented as the integration path. |
| **Cameras onboarded** | 30 across 5 departments, 14 live |
| **Analytics** | ANPR, object detection, within-camera tracking, intrusion zones, directional line crossing |
| **Detector** | YOLOX-S on ONNX Runtime. OCR by PaddleOCR |
| **Hardware it runs on** | One laptop, 4 GB VRAM, 8 GB RAM |

---

## The governing rule

**Video becomes permanent only where a specific, logged, auditable watchlist match justifies it.**

Three pipelines run off one stream pull per camera, and each one has a different answer to the question "what does this keep?"

| Pipeline | What it does | What it persists | What it discards |
|---|---|---|---|
| **1. Live view** | Relays video to the control room | nothing | every frame that passes through |
| **2. Analytics** | Motion gate, detect, track, crop, OCR, watchlist match | a text sighting row and a plate crop of about 2 KB | frames, full-frame JPEGs |
| **3. Evidence** | Fixed-size rolling buffer per camera | the promoted clip, its SHA-256 and an audit row | the buffer, which overwrites itself |

Pipeline 3 only ever writes a clip when pipeline 2 raises a watchlist match, and it writes 30 seconds either side of the event. Nothing else is kept. This is a civil-liberties position before it is a storage optimisation, and it is also what makes the design affordable at 80,000 cameras.

---

## Architecture

![Sentinel workflow and integration diagram](deliverables/Sentinel-Workflow-Integration-Diagram.png)

The camera registry is the control plane. It holds every camera's id, department, location and geometry, stream URL, codec, resolution, ROI, ownership and health, and every other component asks it what to connect to. Nothing downstream hard-codes a camera id or a stream URL.

At statewide scale the same design splits across three tiers. Analytics runs at the **edge**, near the cameras, so only text metadata and 2 KB crops cross the wide-area network. The **regional** tier aggregates, indexes and holds evidence. The **central** tier does statewide search, cross-region route correlation and enrichment against VAHAN, SARTHI, eGujCop, AFIS and NAFIS.

The full reasoning, the capacity arithmetic and the failure-mode analysis are in **[deliverables/HLD.md](deliverables/HLD.md)**.

### Integrating heterogeneous departments

Every camera enters the same registry, whichever way it arrives. The connector ladder covers what real departments actually expose:

| What the source exposes | Connector | Why |
|---|---|---|
| RTSP or ONVIF | Direct pull, RTSP over TCP | The common case. TCP only, because UDP does not survive NAT or government firewalls |
| HLS or WebRTC gateway | Direct pull over the CDN | Traverses any network. This is what the sandbox exposes |
| Vendor VMS with an API or SDK | Per-vendor adapter | Translates the vendor API into the registry contract |
| Vendor SDK only, Windows-only, or behind NAT with no inbound route | Department-side collector | A small agent inside the department network speaks the SDK locally and pushes outbound |
| Analog cameras | DVR or encoder, then RTSP | Only the first hop differs |
| Private CCTV | View-only tier with a consent record | `ownership = private`, never treated as a government asset |

**Sentinel is consume-only.** It pulls streams read-only. It never publishes to a gateway, never calls a control API, never downloads stored footage, and never writes to a departmental system. A department's VMS, its storage and its retention policy are unchanged by onboarding.

---

## Screens

The Command view is one screen carrying the live wall, the GIS map, the live alert feed, the latest plate reads, object counts and worker health.

![Command view](deliverables/deck/img/dashboard.png)

| | |
|---|---|
| ![GIS](deliverables/deck/img/map.png) | ![Route](deliverables/deck/img/route.png) |
| **Map.** 30 cameras coloured by department, health shown by opacity, click through to the record. | **Route.** Numbered stops in time order, the polyline dashed across coverage gaps, a timeline with crops. |
| ![Alerts](deliverables/deck/img/alerts.png) | ![Zones](deliverables/deck/img/zones.png) |
| **Alerts.** Plate, crop, camera, department, severity, match type, acknowledge. Server-sent events, about 2 seconds end to end. | **Zones.** Draw an intrusion polygon or a directional crossing line on a live still. Stored in normalised coordinates. |

Real detections on real sandbox footage, cam08 at Majevadi Gate, Junagadh:

![Detections](deliverables/deck/img/detection.jpg)

---

## Quickstart

One command brings up the whole platform. On first run it fetches a portable ffmpeg if one is not on PATH, creates the virtualenv, installs dependencies, downloads YOLOX-S, probes the camera grid, seeds the registry and opens the dashboard.

```bat
git clone https://github.com/adityashroff06-code/sentinel-gujarat.git
cd sentinel-gujarat

copy .env.example .env      :: then fill in SENTINEL_EMAIL and SENTINEL_PASSWORD

python launch.py check      :: report what is present and what is missing, change nothing
python launch.py            :: bring everything up, then open http://localhost:8000
```

Any Python from 3.10 to 3.13 works, Anaconda's included. Later starts skip everything already done.

| Command | What it does |
|---|---|
| `python launch.py` | Full bring-up, then open the dashboard |
| `python launch.py check` | Report the state of the environment without changing it |
| `python launch.py status` | What the running platform has done: workers, frames and fps per camera, sightings, top plates |
| `python launch.py demo` | Inject the demo vehicle through the real pipeline, for a guaranteed end-to-end walkthrough |
| `python launch.py demo-clear` | Remove only the demo rows, leaving live reads untouched |
| `python launch.py harvest` | Sweep the recordings for plates and seed the watchlist from what was observed |
| `python launch.py stop` | Stop the API and the workers |

The `.bat` files in the repository root wrap the same commands for double-clicking.

### Running the parts separately

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m src.tools.fetch_models            :: YOLOX-S, Apache-2.0

python -m src.tools.probe                   :: catalogue into the registry, detect transports
python -m src.tools.seed_registry           :: departments, coordinates, tiers

cd ui && npm install && npm run build && cd ..

uvicorn src.api.main:app --port 8000        :: API, HLS relay, alert SSE, health checker, built UI
python -m src.ingest.worker                 :: live ANPR workers, tracker, zones, matcher, alerts
```

For UI development, `cd ui && npm run dev` serves on port 5173 and proxies `/api` to port 8000.

On an NVIDIA GPU, `pip install onnxruntime-directml` puts the detector on the card and makes it roughly ten times faster. Without it everything still runs on CPU.

### The demo vehicle

Live ANPR reads real plates off the daytime cameras, but a route that crosses several cameras needs the same vehicle to appear on several cameras, and the CDN rate-limits a busy address. `python launch.py demo` injects one watchlisted vehicle, `GJ01AB1234`, through the **real** pipeline, using the same `record_sighting` and `match_sighting` calls the live workers use. That produces a genuine three-camera, three-department route with live alerts, crops and report rows. It sits alongside the live reads and `demo-clear` removes it.

---

## Configuration

Everything is set in `.env`, which is gitignored and must never be committed. `.env.example` is the template.

| Variable | Default | Meaning |
|---|---|---|
| `SENTINEL_EMAIL` | | Portal account, raw value. The code percent-encodes it |
| `SENTINEL_PASSWORD` | | Portal password. Held server-side only and never logged, persisted or returned by the API |
| `SENTINEL_CDN` | `https://cctv.corp8.cloud` | Sandbox CDN base |
| `SENTINEL_STREAM_IP` | `103.250.160.189` | Stream host |
| `SENTINEL_RTSP_PORT` | `8554` | RTSP port |
| `SENTINEL_WHEP_PORT` | `8889` | WebRTC over WHEP port |
| `SENTINEL_DB` | `data/sentinel.db` | SQLite file for the demo. A real deployment substitutes Postgres |
| `SENTINEL_ACTIVE_CAMERAS` | `5` | Cameras under continuous inference, matching the active tier in `data/camera_seed.csv` |
| `SENTINEL_INFER_FPS` | `3` | Frames per second sampled per active camera |
| `SENTINEL_API_PORT` | `8000` | API port |
| `SENTINEL_PLAYBACK_OFFSET_S` | `0` | Shifts the shared playback window. The sandbox recordings loop over about 12 hours starting around 21:00, so set this to about `34000` to put the live edge in daylight |
| `SENTINEL_HEALTH_INTERVAL_S` | `300` | Camera health-check cadence. Set to 0 to disable |
| `SENTINEL_LOG_LEVEL` | `INFO` | Log level |

The whole platform advances on one shared timeline, in `src/ingest/timeline.py`. The relay, the workers and the harvest all read the same offset, which is what keeps the live wall, the plate reads and the route in sync. Restart the API and the workers after changing it.

---

## API

The OpenAPI document that FastAPI generates **is** the registry API documentation deliverable. It is served live at `/docs` and `/openapi.json`, and exported to [`deliverables/registry-api.json`](deliverables/registry-api.json) by `python -m src.tools.export_openapi`.

### Registry (Model 1)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/cameras` | List cameras, filterable by department, tier, health and ownership |
| `POST` | `/api/cameras` | Register one camera programmatically |
| `POST` | `/api/cameras/import` | Bulk CSV import, validated row by row with a reason given for every rejection |
| `GET` | `/api/cameras/{camera_id}` | One camera record |
| `PATCH` | `/api/cameras/{camera_id}` | Update a camera, including its ROI and zones |
| `GET` | `/api/cameras/{camera_id}/stream` | Resolve a playable stream URL. Never returns a URL containing a credential |
| `GET` | `/api/cameras/{camera_id}/snapshot.jpg` | Current still, used by the zone editor |
| `GET` | `/api/cameras/gap-analysis` | Offline and degraded cameras, plus isolated coverage by nearest-neighbour Haversine |

### Analytics and investigation (Model 2)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/sightings` | Deduplicated plate reads, filterable by plate, camera and time window |
| `GET` | `/api/plates/{plate}/route` | **The scored capability.** Ordered stops with camera, department, coordinates, timestamp, crop and match type; elapsed time and implied speed between stops; total distance and duration; departments crossed; coverage gaps |
| `GET` | `/api/events` | Zone events: intrusion entries and directional line crossings |
| `GET` | `/api/events/summary` | Object counts per camera per class |
| `GET` | `/api/workers` | Per-camera sustained fps, motion-skip rate and detections per minute |

### Watchlist and alerting

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/watchlist` | Current watchlist |
| `POST` | `/api/watchlist` | Add an entry with category and severity |
| `DELETE` | `/api/watchlist/{watchlist_id}` | Remove an entry |
| `GET` | `/api/alerts` | Alert history |
| `GET` | `/api/alerts/stream` | Live alert feed over Server-Sent Events |
| `POST` | `/api/alerts/{alert_id}/ack` | Acknowledge an alert. The acknowledgement is persisted |

### Relay, reports and service

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/hls/{camera_id}/live.m3u8` | HLS playlist for the live wall, relayed through the backend |
| `GET` | `/api/hls/{camera_id}/key` | AES-128 key for the relayed segments |
| `GET` | `/api/hls/{camera_id}/seg/{name}` | One relayed segment |
| `GET` | `/api/reports/detections` | Timestamped detection report, CSV and printable |
| `GET` | `/api/reports/gap-analysis` | Coverage gap report |
| `GET` | `/api/health` | Liveness |
| `GET` | `/api/stats` | Counts across the registry, sightings, alerts and events |

---

## How the analytics work

### ANPR

```
frame  ->  motion gate (MOG2)  ->  vehicle detect (YOLOX-S, ONNX)  ->  crop
       ->  plate region  ->  upscale and contrast  ->  OCR (PaddleOCR)
       ->  normalise  ->  dedupe  ->  sighting row + 2 KB crop
```

The motion gate skips inference on static frames, which on the sandbox cameras saves between 0 and 83% of the work depending on the camera. OCR only ever sees the vehicle crop, never a full frame, and the plate region is upscaled before OCR because plates in wide overview footage are small. Reads are normalised to the Indian plate format and deduplicated at 60 seconds per plate per camera, with the raw OCR output kept alongside the normalised value so a normalisation change can be replayed.

### Watchlist matching

Matching happens locally against a cached copy of the watchlist. It is never a per-detection call to a central system, because at 80,000 cameras and one detection per camera per minute that would be about 1,333 queries per second and 115 million per day against VAHAN and eGujCop. Only confirmed matches call a central system, and then only to enrich the record.

Matching runs in three steps:

1. Exact.
2. OCR-ambiguity map: `O/0`, `I/1`, `S/5`, `B/8`, `Z/2`, `G/6`, `Q/0`.
3. Levenshtein distance of 1 or less, for reads of 8 characters or more.

Reads shorter than 8 characters are partial. They are stored as low-confidence route candidates and they never raise an alert. Every alert records its match type and edit distance.

### The alert path

The ordering here is deliberate and it is the part most worth reading in the source:

1. The sighting is written to durable storage **before** any alerting logic runs.
2. The matcher runs against the cached watchlist, with a five-minute cooldown per plate per camera so one vehicle cannot flood the operator's feed.
3. On a match the alert row is persisted **and then** broadcast, so a detection never exists only in the memory of a process that is about to crash.
4. The operator sees it in about two seconds with the plate crop attached, which is what makes an alert worth acting on.
5. The acknowledgement is persisted and one click leads to the route.

In this build step 3 is an in-process queue with Server-Sent Events. In production it is a durable queue such as Kafka or NATS. That difference is stated rather than glossed over.

### Zones and objects

Intrusion zones and crossing lines are stored per camera in normalised coordinates from 0 to 1, so a zone survives a change of camera resolution. A tracked object whose foot point enters a polygon fires once, on entry. Line crossing honours direction. High-severity zones broadcast on the alert stream. Object presence events per camera per class are throttled and aggregated for the dashboard and the detection report.

---

## Repository layout

```
.
+- launch.py                 one-command bring-up, health checks and demo control
+- src/
|  +- api/                   FastAPI app; the OpenAPI it generates is the API deliverable
|  |  +- main.py             app, CORS, health checker thread, SPA fallback
|  |  +- routes_cameras.py   registry, import, gap analysis, stream resolution
|  |  +- routes_analytics.py sightings, route reconstruction, watchlist, alerts, events
|  |  +- routes_hls.py       authenticated HLS relay, key and segment proxy
|  |  +- routes_reports.py   detection report, gap-analysis report
|  +- ingest/
|  |  +- frame_source.py     stream pull, PTS timing, backoff, scene-cut recovery
|  |  +- worker.py           per-camera worker loop
|  |  +- timeline.py         the one shared playback clock
|  |  +- health.py           per-camera health scoring
|  +- anpr/
|  |  +- pipeline.py         the cascade, end to end
|  |  +- motion.py           MOG2 gate
|  |  +- detect.py           YOLOX on ONNX Runtime
|  |  +- track.py            IoU and centre tracker fed PTS deltas
|  |  +- ocr.py              PaddleOCR on the vehicle crop
|  |  +- plates.py           normalisation and the Indian plate format
|  |  +- sightings.py        dedupe and persistence
|  +- alerting/
|  |  +- matcher.py          the three-step match against the cached watchlist
|  |  +- alerts.py           persist, then broadcast
|  +- analytics/
|  |  +- route.py            route reconstruction, dwell collapse, implied speed
|  |  +- zones.py            intrusion polygons and directional line crossing
|  +- tools/                 probe, seed, harvest, measure, report, export_openapi
+- ui/                       React 18, Vite, Leaflet, hls.js
|  +- src/pages/             Dashboard, Map, LiveWall, Search, Route, Alerts, Zones, Reports
+- deliverables/
|  +- HLD.md / HLD.pdf       technical proposal, ten dimensions
|  +- Sentinel-Solution-Presentation.pptx / .pdf
|  +- Sentinel-Workflow-Integration-Diagram.svg / .png / .pdf
|  +- registry-api.json      exported OpenAPI
|  +- detection-report.csv / .html
|  +- gap-analysis-report.html
|  +- deck/build_deck.js     the deck is generated, not hand-edited
+- data/camera_seed.csv      the onboarded sample dataset, committed and disclosed
+- 00-mission.md .. 06-submission-checklist.md    the design record
+- PRD.md / PLAN.md / RUN.md / STATUS.md
```

---

## Design decisions worth knowing about

These are summarised here and argued properly in [the HLD](deliverables/HLD.md).

**Timing comes from PTS, never from frame arrival.** On connect the gateway replays a buffered GOP, so early frames arrive faster than real time. Anything timed by arrival computes impossible vehicle speeds, and the bug then looks like a model problem and gets debugged in the wrong place.

**RTSP over TCP, always.** UDP fails across NAT and firewalls and delivers corrupt frames. Where RTSP is blocked, HLS is the fallback, and the transport actually used is recorded per camera in the registry.

**Reconnect with jittered backoff**, `base 2 s * 2^n * random(0.5, 1.5)` capped at 30 s. Without jitter, a regional power event turns every recovering client into a synchronised reconnect storm against departmental NVRs.

**Store crops, not frames.** A full-frame snapshot per detection is about 30 KB and comes to 3.46 TB a day statewide. A plate crop is about 2 KB and comes to 0.23 TB. Full frames are kept only for confirmed hits, where the evidence clip exists anyway.

**Decode usually binds before inference.** Every stream has to be H.264 or H.265 decoded before any model sees it, and a GPU's decode engines cap at roughly 20 to 40 concurrent 1080p30 sessions. Tuning inference to 200 streams per GPU while NVDEC caps at 30 leaves the tensor cores about 85% idle and sizes the fleet on the wrong number.

**Measured and modelled are labelled separately.** Every capacity number in the HLD carries `[measured]` or `[model]`. The two that anchor everything, sustained inference fps per camera and real detection rate per camera, were measured on this system.

### Licensing is a procurement decision

At 80,000 cameras a licence at 500 rupees per camera per year is 4 crore rupees a year. The stack here is deliberately Apache-2.0, MIT and BSD throughout, which removes per-camera licensing entirely.

That means **not** Ultralytics YOLO, which is AGPL-3.0 and, linked into an application the State would own, can pull the whole codebase under AGPL. It also means not Elasticsearch or Redis under their current licences; OpenSearch and Valkey are the production substitutes. The distinction that matters in practice is that AGPL is hazardous as a linked library and generally acceptable in a separate service you merely run.

---

## What this does not do

Stated here so nobody has to discover it.

- **No arbitrary rewind and no central recording of all video.** Both the privacy posture and the bandwidth arithmetic rule it out. Video is captured on justified cause only.
- **No live facial recognition.** The approach and its privacy controls are described in section 5.4 of the HLD. It is not built and is not claimed as built.
- **No Model 3 federation demonstration.** The sandbox exposes bare stream endpoints, so there are no departmental VMS platforms inside it to federate. Model 3 is documented as the integration path for real departments.
- **Plate recall on these feeds is limited, and reported as such.** The sandbox cameras are wide traffic-overview PTZ units rather than ANPR lane cameras, so plates sit at 10 to 25 px even on close vehicles. The pipeline upscales the plate region, the demo concentrates on the cameras that read, and the real recall is reported rather than rounded up.
- **Geography was assigned, and it is disclosed.** The sandbox catalogue carries only id and name. Departments and coordinates were assigned once in `data/camera_seed.csv`, using real named locations and approximate coordinates.
- **The 30 versus 50 camera discrepancy is recorded, not resolved silently.** The public problem statement refers to about 50 cameras; the catalogue after login lists `cam01` through `cam30`. The system is built against the catalogue.

---

## Security

- Credentials live only in the environment. They are never hard-coded, logged, persisted or displayed unmasked, and no URL containing a credential is written to storage or returned by the API.
- `.env`, the database, crops, evidence and every log are gitignored. No credential appears in this repository, in its history, in any video frame or in any screenshot.
- Every evidence promotion writes an audit row carrying the event id, the trigger reason and the SHA-256 of the clip. Watchlist changes, acknowledgements and cross-department access are logged.
- Production adds a secrets vault with per-department rotation, department-scoped RBAC, TLS on every hop, encryption at rest, and network segmentation with edge nodes in department DMZs.

---

## Submission deliverables

| Deliverable | Location |
|---|---|
| Technical proposal and HLD | [`deliverables/HLD.md`](deliverables/HLD.md), [`HLD.pdf`](deliverables/HLD.pdf) |
| Solution presentation | [`deliverables/Sentinel-Solution-Presentation.pdf`](deliverables/Sentinel-Solution-Presentation.pdf) |
| Workflow and integration diagram | [`deliverables/Sentinel-Workflow-Integration-Diagram.png`](deliverables/Sentinel-Workflow-Integration-Diagram.png) |
| Registry API documentation | [`deliverables/registry-api.json`](deliverables/registry-api.json), live at `/docs` |
| Sample onboarded dataset | [`data/camera_seed.csv`](data/camera_seed.csv) |
| Gap-analysis report | [`deliverables/gap-analysis-report.html`](deliverables/gap-analysis-report.html) |
| Timestamped detection report | [`deliverables/detection-report.csv`](deliverables/detection-report.csv), [`.html`](deliverables/detection-report.html) |
| Operating guide | [`RUN.md`](RUN.md) |
| Design record | [`00-mission.md`](00-mission.md) through [`06-submission-checklist.md`](06-submission-checklist.md) |

---

## Licence

Apache License 2.0. See [LICENSE](LICENSE).

The third-party model and library stack is Apache-2.0, MIT and BSD throughout, which is what makes deployment at 80,000 cameras free of per-camera licensing.
