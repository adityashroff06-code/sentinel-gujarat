# Constraints — hardware, licensing, sandbox rules (MUST)

**Editor's note (20 Sep 2026).** The body below is the previous build's `02-hard-constraints.md`, **copied verbatim** — it is the budget every design decision is made against and none of it has changed. Three things to read with the date in mind:

- **"Time"** (last section) describes the 13–15 Sep sprint. The current clock is in `docs/brief.md` §0: deadline 28 Sep, application Mon 21 – Thu 24 Sep, deliverables Fri 25.
- **"Stack — locked"** lists the previous build's choices. They were all validated on this laptop and are the fresh build's defaults, but they are *decisions*, not constraints — the plan may confirm or change any of them in `docs/decisions.md`. The **licensing traps** table, however, is a hard constraint: the hackathon states *"All solutions should use open-source technologies"* and the traps are procurement blockers.
- **"Python 3.11"**: the laptop runs Python 3.13.9 (Anaconda) and every dependency ships a cp313 wheel (validated 14 Sep — `docs/reference/old-build/STATUS.md`, "LAUNCHER FIX 2").

The organisers' feed rules (the other half of the MUST set) are in `docs/feed-rules.md`; what the sandbox actually does is in `docs/sandbox-findings.md`.

---

# 02 — Hard constraints

## Hardware — the ceiling that shapes every decision

| | |
|---|---|
| CPU | AMD Ryzen 5 3550H — 4 cores / 8 threads, 2.10 GHz |
| RAM | **8 GB** |
| GPU | NVIDIA GTX 1650, **4 GB VRAM** (+ Radeon Vega 8 integrated) |
| Storage | 477 GB SSD |
| OS | Windows 10/11 |

### What this permits

**It does not permit continuous inference on 30 cameras.** No amount of tuning changes that. The demo must therefore be tiered, by design and stated openly:

| Tier | Cameras | Treatment |
|---|---|---|
| **Active** | ~6–8 (`SENTINEL_ACTIVE_CAMERAS`) | Continuous decode at `SENTINEL_INFER_FPS` (start 3), motion-gated, full ANPR |
| **Registered** | all others | In the registry, on the GIS map, live-viewable on demand, health-monitored, not continuously inferred |

Tiering is not an apology. It is exactly the argument the scalability section needs: **capacity is a consequence of engineering choices, not a fixed cost.** The fps tier lives in the registry as camera metadata, which is precisely how it would work at 80,000 cameras. Say so.

### Budget discipline

- **VRAM:** detector + OCR together must stay under ~3 GB, leaving headroom for decode. Prefer small input sizes. Run OCR on CPU if VRAM is tight — plate crops are small and CPU OCR is viable at this volume.
- **RAM:** the browser running the live wall will take 1–2 GB. Do not run Postgres, Elasticsearch, Kafka or Docker alongside inference. SQLite only.
- **Live wall:** open only the tiles actually visible. Every open HLS player is a separate pull.
- **Thermals:** a laptop under sustained GPU load throttles. Measure throughput after 10 minutes of running, not after 30 seconds.

### Measure, do not assume

Two numbers must come from code that actually ran, because every scaling claim rests on them:

1. **Frames per second per camera your pipeline actually sustains**, with N cameras active.
2. **The real detection rate per camera** (vehicles per minute). The 80k review's storage and query arithmetic all rest on an assumed one per minute, which could be off by 10× either way.

Record both in `plan/STATUS.md` and carry them into the HLD as measurements. Everything else in the scaling section is explicitly labelled a model.

---

## Stack — locked. Do not substitute without recording why.

| Layer | Choice | Note |
|---|---|---|
| Language | Python 3.11 | |
| API | **FastAPI** + uvicorn | Auto-generates OpenAPI — this *is* the Model 1 "registry API documentation" deliverable, free |
| Database | **SQLite** (WAL mode) | Postgres/PostGIS described in the HLD as the production shape |
| Geospatial | Haversine in Python | PostGIS is the production answer; do not install it here |
| Frames | **FFmpeg / ffprobe** + OpenCV | ffmpeg must be on PATH |
| Detector | **YOLOX** or **RT-DETR (PaddlePaddle)** — Apache-2.0 | ⚠ NOT Ultralytics |
| Plate OCR | **PaddleOCR** — Apache-2.0 | Strong on Indian plates |
| Tracking | **ByteTrack** — MIT | Within-camera track continuity |
| Motion gate | OpenCV MOG2 | The biggest compute saving available |
| Frontend | **React + Vite**, **Leaflet** (BSD-2), **hls.js** (Apache-2.0) | |
| Live video | **HLS via hls.js**; WHEP only if the probe proves port 8889 reachable | HLS traverses any network |

### Licensing traps — these are procurement blockers, not preferences

| Trap | Problem | Use instead |
|---|---|---|
| **Ultralytics YOLO** (v5/v8/v11) | AGPL-3.0. Linked into the application it can force the entire codebase to AGPL — a genuine blocker for a system the State would own and operate | **YOLOX** / **RT-DETR** (Apache-2.0) |
| **Elasticsearch** | Left OSI-approved open source in 2021; messy provenance to defend | **OpenSearch** (Apache-2.0) in the HLD; SQLite FTS5 for the demo |
| **Redis** | Relicensed RSALv2/SSPL in 2024 | **Valkey** (Apache-2.0) in the HLD; not needed in the demo |

The distinction to state in the HLD: AGPL is dangerous when the component is a **library linked into your code**; it is generally acceptable when it is a **separate service you merely run**. Demonstrating that distinction reads as procurement literacy and is quietly persuasive to a government jury.

The hackathon states *"All solutions should use open-source technologies."* **Verify current licences before submitting** — several changed recently.

---

## Time

| | |
|---|---|
| Now | 13 September 2026 |
| Submission closes | **15 September 2026** |
| Usable working time | ~2 days |

The build order in `plan/PLAN.md` is sequenced so that stopping at any phase boundary still yields a submittable system. Phases are not equal: P1–P4 are the submission, P5 is bonus, P6 is mandatory and must not be squeezed.
