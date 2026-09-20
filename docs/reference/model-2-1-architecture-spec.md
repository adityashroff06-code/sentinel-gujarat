# Model 2.1 — Consolidated Architecture Specification

**Decision:** LOCKED, 10 Sep 2026 — Model 1 (mandatory registry/GIS) + Model 2 (unified viewing & metadata analytics) + Pipeline 3 (event-triggered evidence capture).
**Submitted as:** a Hybrid Architecture under the source's permitted approach — *"a hybrid architecture combining features from two or more reference solution models."*
**Status:** Pipeline 3 validated end-to-end 10 Sep (see `claude/model-02-1-event-triggered-evidence.md`). Everything else is designed, not yet built.

> **⚠ Compliance audit result: 36 mandatory items checked → 20 OK, 13 GAPS, 3 PARTIAL.**
> Section 7 lists every gap and its closure. Most are documentation, not code. **Do not skip §7.**

---

## 1. What Model 2.1 is, in one paragraph

One RTSP pull per camera feeds three concurrent pipelines. **Pipeline 1** relays live video to the control room and stores nothing. **Pipeline 2** runs AI analytics and stores only text metadata plus a small crop. **Pipeline 3** keeps a fixed-size rolling buffer of compressed video and promotes a ±30 s clip to permanent storage *only* when a watchlist match fires. Underneath all three sits the **Model 1 registry** — the mandatory camera inventory and GIS layer that tells every other component which cameras exist, where they are, and how to reach them.

---

## 2. Architecture

```
                    ┌──────────────────────────────────────────┐
                    │  MODEL 1 — CAMERA REGISTRY + GIS         │
                    │  the control plane for everything below  │
                    │  · camera metadata, ownership, dept      │
                    │  · geometry (point, bearing, FOV, range) │
                    │  · stream URLs, codec, protocol          │
                    │  · health, AMC, retention                │
                    │  · ROI mask + fps tier per camera        │
                    └────────────────┬─────────────────────────┘
                                     │ tells workers what to connect to
                                     ▼
CAMERA / DEPT VMS ──── ONE RTSP pull (TCP) ────► EDGE GATEWAY
                                                      │
                    ┌─────────────────────────────────┼─────────────────────────────────┐
                    │                                 │                                 │
              PIPELINE 1                        PIPELINE 2                        PIPELINE 3
           LIVE VIEW (relay)                 AI ANALYTICS                    EVIDENCE CAPTURE
                    │                                 │                                 │
       WebRTC/WHEP + HLS(tmpfs)        decode @ 5 fps (fps tier)         ring buffer, HLS segments
       memory only, NOTHING SAVED      motion gate → skip empty          fixed N, self-overwriting
                    │                  detector → crop → OCR                         │
                    │                  tracker → cross-camera Re-ID       ◄── promote(t±30s)
                    │                  match vs EDGE-CACHED watchlist         on match only
                    │                                 │                                 │
                    ▼                                 ▼                                 ▼
            CONTROL ROOM WALL              durable queue → alerts          CLIP ~22 MB + SHA-256
            multi-camera grid              sighting record (text)          + audit row
                                           + plate crop (~2 KB)                        │
                                                      │                                │
                                                      ▼                                ▼
                                          SEARCH INDEX + GIS ROUTE          EVIDENCE STORE
                                          "where has GJ01AB1234 been?"      the ONLY permanent video
```

### Design invariants (do not violate these)
1. **One pull per camera.** Never open a second connection to a source — the Resources page states each client gets its own stream copy.
2. **Watchlist matching happens at the edge**, against a locally cached list. Never per-detection round-trips to VAHAN/eGujCop.
3. **All timing from PTS**, never arrival time.
4. **RTSP over TCP**, always.
5. **Detections enter a durable queue before any alerting logic.** Never let a detection exist only in the memory of the service about to crash.
6. **The registry is the single source of truth** for what cameras exist. Populated from `/api/ingest`, which the organisers call "the contract."

---

## 3. Full technology stack

Every component open source. Licence column is load-bearing — see §4.

| Layer | Component | Choice | Licence | Why |
|---|---|---|---|---|
| **Ingest** | Stream client | **FFmpeg / GStreamer** | LGPL-2.1+ | RTSP/ONVIF, hardware decode, `-c copy` |
| | Stream server / relay | **MediaMTX** | MIT | Serves RTSP + WHEP + HLS from one publish. Validated 10 Sep |
| | Protocol adapters | ONVIF-py, vendor SDKs | Apache-2.0 / varies | Per-vendor onboarding |
| **Pipeline 1** | Low-latency view | **WebRTC / WHEP** via MediaMTX | MIT | Sub-second control-room view |
| | Fallback view | **HLS** on `tmpfs` | — | Any phone, any restricted network, never touches disk |
| | Browser player | **hls.js** | Apache-2.0 | HLS in browser |
| **Pipeline 2** | Vehicle/person detector | **YOLOX** or **RT-DETR (PaddlePaddle)** | Apache-2.0 | ⚠ NOT Ultralytics — see §4 |
| | Plate OCR | **PaddleOCR** | Apache-2.0 | Strong on Indian plates, permissive licence |
| | Tracker | **ByteTrack** | MIT | Multi-object tracking within a camera |
| | Motion gate | OpenCV MOG2 | Apache-2.0 | Skips inference on empty frames — biggest compute saving |
| | Inference runtime | **ONNX Runtime** / TensorRT | MIT / NVIDIA EULA | INT8 quantisation, hardware acceleration |
| | Multi-stream orchestration | **DeepStream** (optional) | NVIDIA EULA | Only if NVIDIA hardware; else plain GStreamer |
| **Pipeline 3** | Ring buffer | **FFmpeg HLS segmenter** | LGPL-2.1+ | Keyframe-aligned, `delete_segments`, `program_date_time`. **Validated** |
| | Clip assembly | FFmpeg concat `-c copy` | LGPL-2.1+ | No re-encode. Measured 0.54% CPU |
| **Data** | Registry + relational | **PostgreSQL** | PostgreSQL Licence | Camera registry, watchlist, audit |
| | Geospatial | **PostGIS** | GPL-2.0 | Geometry, coverage polygons, gap analysis |
| | Time-series sightings | **TimescaleDB** (Apache edition) | Apache-2.0 | Sighting records at volume |
| | Search | **OpenSearch** | Apache-2.0 | ⚠ NOT Elasticsearch — see §4 |
| | Event bus | **NATS** or **Apache Kafka** | Apache-2.0 | Durable queue between detection and alerting |
| | Cache / edge watchlist | **Valkey** | BSD-3 | ⚠ NOT Redis — see §4 |
| | Object storage | **SeaweedFS** or filesystem | Apache-2.0 | Evidence clips. MinIO is AGPL |
| **Backend** | API services | **FastAPI** (Python) | MIT | Auto-generates OpenAPI docs — closes GAP #1 free |
| | Auth / RBAC | **Keycloak** | Apache-2.0 | Department-wise role-based access control |
| **Frontend** | UI | **React** | MIT | |
| | GIS map | **Leaflet** | BSD-2 | Camera map, coverage layers, vehicle route |
| **Ops** | Containers | **Docker Compose** → **Kubernetes** | Apache-2.0 | Compose for hackathon, K8s for the scaling story |
| | Metrics | **Prometheus** | Apache-2.0 | Camera health, pipeline health |
| | Dashboards | **Grafana** | AGPL-3.0 | Separate tool, not linked — acceptable (§4) |

---

## 4. Licensing audit — three traps to avoid

The hackathon states **"All solutions should use open-source technologies."** For a *government procurement*, the licence matters as much as the availability. Three popular defaults would create real problems:

| Trap | Problem | Use instead |
|---|---|---|
| **Ultralytics YOLO** (v5/v8/v11) | **AGPL-3.0.** Linked into your application, it can force your *entire* codebase to be AGPL. For a system the State would own and operate, that is a genuine procurement blocker | **YOLOX** or **RT-DETR (PaddlePaddle)** — Apache-2.0 |
| **Elasticsearch** | Left OSI-approved open source in 2021 (SSPL/Elastic Licence); AGPL added later. Messy provenance to defend | **OpenSearch** — clean Apache-2.0, drop-in |
| **Redis** | Relicensed to RSALv2/SSPL in 2024 | **Valkey** — the Linux Foundation Apache-2.0 fork |

**The distinction that matters:** AGPL is dangerous when the component is a *library linked into your code* (Ultralytics). It is generally acceptable when it is a *separate service you merely run* (Grafana, MinIO). State this distinction in the HLD — it demonstrates procurement literacy, which is rare and quietly persuasive to a government jury.

> **Verify current licences before submission.** These changed recently and may change again.

---

## 5. Resource utilisation audit — are we using everything they gave us?

| Resource provided | Used? | How |
|---|---|---|
| **RTSP** `rtsp://<host>:8554/stream/<id>` | ✅ | Pipeline 2 inference + Pipeline 3 buffer |
| **WebRTC/WHEP** `:8889/.../whep` | ✅ | Pipeline 1 low-latency control-room view |
| **HLS** `/live/stream/<id>/index.m3u8` | ✅ | Pipeline 1 fallback + Pipeline 3 buffer format |
| **`/api/ingest` catalogue** | ✅ | **Populates the Model 1 registry.** The organisers call it "the contract" — we treat it as such |
| **~50 cameras, 5 departments** (Health, Police, GSRTC, Panchayat, Municipal) | ⚠️ **Under-used** | See below |
| **12 hrs footage per camera** | ✅ | Long-run soak testing, loop-boundary handling |
| **Own feeds permitted** (demo 3) | ✅ | Also closes GAP #3 — the "two different systems" requirement |
| **Own watchlist DB permitted** | ✅ | Edge-cached representative watchlist |
| **Knowledge Partners** (NFSU, DA-IICT) — mentoring | ❌ **Unused** | They explicitly offer technical guidance. Worth a query on ANPR for Indian plates |

**The under-used resource worth exploiting:** the feeds span **five named departments**. Most teams will treat them as fifty anonymous streams. We should **group the GIS map by department, colour-code it, and explicitly demonstrate a vehicle tracked across cameras belonging to different departments.** That turns a dataset property into direct evidence for the core claim — *"we integrate diverse departmental systems"* — at essentially zero cost. Put it in the demo script.

---

## 6. Mandatory compliance — the 20 items already covered

| Requirement | Covered by |
|---|---|
| Model 1: registry portal + GIS map | Registry service + Leaflet |
| Model 1: bulk **and** manual onboarding | CSV import + form + API |
| Model 1: sample camera-metadata dataset | Export of `/api/ingest` ingestion |
| Model 2: ANPR demo on live/recorded feeds | Pipeline 2 |
| Model 2: searchable metadata dashboard | Search UI + OpenSearch |
| Test: onboard ~50 cameras, one platform | Registry + ingest workers |
| Test: centralised monitoring | Pipeline 1 live wall |
| Test: trace vehicle from registration number | Cross-camera Re-ID |
| Test: complete timestamped, location-wise route | GIS route + sighting log |
| Test: working watchlist, continuous cross-reference | Edge-cached watchlist |
| Test: automated real-time alerts | Alert service via durable queue |
| Eval 5: ANPR quality, vehicle/person detection, timestamped reports | Pipeline 2 + report generator |
| HLD: heterogeneous camera/NVR/VMS integration | Adapter layer |
| Step 6: all seven scalability items | `claude/architecture-review-80k.md` |
| Submission: PPT, both demo videos, links | Day 5 |

---

## 7. THE 13 GAPS — and how each closes

**None of these are hard. All of them are forgettable, which is why they are dangerous.**

| # | Gap | Source | Closure | Effort |
|---|---|---|---|---|
| 1 | **Registry API documentation** | Model 1 deliverable | FastAPI auto-generates OpenAPI/Swagger. Export it | **Free** |
| 2 | **Sample gap-analysis report** | Model 1 deliverable | PostGIS query: wards with no camera within 500 m + cameras with expiring AMC → PDF | 1 hr |
| 3 | **Viewer on ≥2 *different* systems** | Model 2 deliverable | Sandbox is **one** system. Add a second source — local ONVIF camera, webcam, or an independent MediaMTX instance — and show both in one viewer | 30 min |
| 4 | **Architecture note: departmental systems unaffected** | Model 2 deliverable | One page: read-only pull, no writes, no config changes, no control-API calls | 30 min |
| 5 | **Intrusion detection** | **Eval area 5** | Line-crossing / zone-entry on the existing detector. Zones stored per camera in the registry | 2 hrs |
| 6 | **Object detection surfaced** | **Eval area 5** | The detector already classifies person/vehicle/bag — expose those classes in the UI and reports, don't hide them behind ANPR | 1 hr |
| 7 | **FRS approach described** | HLD requirement | Describe the approach and the privacy controls. Implementation optional; **description is not** | 30 min |
| 8 | **Department technical prerequisites** | HLD + Dimension 8 | A structured questionnaire: what we need from each department to assess integration feasibility | 1 hr |
| 9 | **Cybersecurity Architecture** | Dimension 4 | Explicit section: RBAC, network segmentation, encryption in transit/at rest, credential vaulting, audit, least privilege | 1 hr |
| 10 | **Department-wise Information Requirements** | Dimension 8 | Same artefact as #8 | — |
| 11 | **Future Roadmap** | Dimension 10 | Phased: pilot district → multi-district → statewide; analytics roadmap beyond ANPR | 30 min |
| 12 | **Private CCTV viewing support** | Background | Registry supports `ownership = private` + a view-only access tier. Design and describe; consent/permission model noted | 30 min |
| 13 | **Analog camera support** | Background | Analog → DVR/encoder → RTSP. One diagram; the path is identical downstream | 15 min |

**Totals: ~3 hours of code (#5, #6, #3), ~5 hours of writing.** The writing is needed for the HLD regardless, so the true marginal cost is small.

### The three partials
- **Cost-Benefit Analysis** — numbers exist in `architecture-review-80k.md`; formalise into a section.
- **VAHAN/SARTHI/eGujCop/AFIS/NAFIS** — the test permits our own watchlist. The HLD must still describe *integration readiness*: adapter interface, sync cadence, the edge-cache design.
- **Open-source compliance** — resolved by §4, but verify licences before submitting.

### Two gaps that matter more than their size suggests
**#5 and #6 are named in Evaluation Area 5 itself:** *"Quality and usefulness of ANPR, vehicle or person detection, intrusion detection, object detection, timestamps, and output reports."* An ANPR-only submission is scored against a rubric that explicitly lists four analytics. Three hours of work moves us from partial to complete on a named scoring area.

---

## 8. Explicitly out of scope — and why that is defensible

State these in the deck. A team that names its boundaries reads as senior; a team that presents no trade-offs reads as inexperienced.

| Not doing | Why it's defensible |
|---|---|
| **Arbitrary rewind of any camera at any past time** | Requires Model 4's total archive: ~1.6 TB/day for 50 cameras, ~240 Gbps statewide. We deliver targeted evidence at ~0.1% of the cost |
| **Middleware/federation layer (Model 3)** | The sandbox exposes bare RTSP with no departmental VMS to federate. We would be demonstrating something that isn't there |
| **Live FRS at scale** | Described in the HLD, not implemented. Face recognition on public feeds carries privacy obligations we would rather address deliberately than casually |
| **Connector sprawl solved** | Acknowledged as Model 2's structural weakness. Named, with the department-side collector as the mitigation path |

---

## 9. Build order

| Priority | Work | Gate |
|---|---|---|
| **P0** | Register → `/api/ingest` → populate registry → measure streams-per-GPU and detection rate | **Today** |
| **P0** | ANPR on sandbox feeds; sighting records; search | 11 Sep |
| **P0** | Cross-camera route reconstruction + watchlist + alerts | **12 Sep — the gate** |
| **P0** | Model 1 GIS map, onboarding demo, gap-analysis report (#1, #2) | 12 Sep |
| **P1** | Intrusion + object detection (#5, #6); second system (#3) | 13 Sep |
| **P1** | Pipeline 3 — **only if the 12 Sep gate passed** | 13 Sep |
| **P0** | All documentation gaps (#4, #7–#13) + PPT + HLD + both videos | 14 Sep |
| — | Buffer and submit | 15 Sep |

> **Gate, 12 September:** if we cannot trace a vehicle across ≥3 sandbox cameras and produce a timestamped route, **Pipeline 3 is cut** and that day goes to the core path. No debate.

---

*Compliance audit run 10 Sep 2026 against the scraped problem statement. Re-run after registration — post-login resources may add requirements not visible on the public site.*
