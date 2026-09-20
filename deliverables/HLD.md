# Sentinel: Technical Proposal (High-Level Design)

**Integrated Video Management and Analytics Platform**
Gujarat Police Innovation Challenge 2026. Home Department / State Crime Records Bureau.

**Proposed model:** a hybrid of Reference **Model 1** (Centralised CCTV Registry and GIS, mandatory) and **Model 2** (Unified Viewing and Metadata Analytics), plus an **event-triggered evidence-capture pipeline**. **Model 3** (VMS federation) is documented as the integration path for departments whose systems cannot be pulled directly.

**How to read the numbers.** Figures marked **[measured]** were observed on the running system. Figures marked **[model]** are arithmetic from assumptions that are stated wherever they are used, and they must be replaced with measurement before procurement. Nothing in this document is presented as a result unless it was measured.

---

## 0. Executive summary

Gujarat runs CCTV across 26 departments on systems that do not interoperate: a mix of analog and IP cameras, different VMS platforms, storage held in different places under different retention rules, and sites as much as 1,000 km apart. Tracing one vehicle today means asking each department separately, by hand.

Sentinel puts a single platform over those systems without changing any of them. It maintains one camera registry with a GIS view, runs video analytics continuously (ANPR first, with object detection, tracking and intrusion detection alongside it), checks every plate read against a watchlist, raises alerts automatically, and reconstructs a vehicle's complete timestamped route across the whole network from a single registration number.

The design runs analytics where the cameras are. Only text metadata and small evidence crops cross the wide-area network. At 80,000 cameras, carrying raw video to one place needs roughly 240 Gbps of sustained inbound capacity [model]; processing at the edge reduces that to roughly 2.1 Mbps of metadata [model], a factor of about 3,750. The same split sets the privacy posture: live video is relayed to the control room and never written to disk, analytics keeps only text rows and a plate crop of about 2 KB, and full video is promoted to permanent storage only when a specific watchlist match, logged and auditable, justifies it.

The working system runs on a single laptop with 4 GB of GPU memory against the sandbox feeds. Section 7 covers what changes between that and a statewide deployment.

---

## 1. Overall architecture (Dimension 1)

### 1.1 In one paragraph

One stream pull per camera feeds three concurrent pipelines. **Pipeline 1** relays live video to the control room and stores nothing. **Pipeline 2** runs analytics and stores only text metadata plus a small plate crop. **Pipeline 3** keeps a fixed-size rolling buffer of compressed video and promotes a 60-second clip, 30 seconds either side of the event, to permanent storage only when a watchlist match fires. Beneath all three sits the **Model 1 registry**: the camera inventory and GIS layer that tells every component which cameras exist, where they are, and how to reach them.

### 1.2 Component diagram

```
          +------------------------------------------+
          |  MODEL 1: CAMERA REGISTRY + GIS          |
          |  the control plane for everything below  |
          |  - id, department, location, geometry    |
          |  - stream URLs, codec, resolution, ROI   |
          |  - health, last_seen, fps_tier           |
          +---------------------+--------------------+
                                | tells workers what to connect to
                                v
CAMERA GRID ---- ONE pull per camera (HLS or RTSP/TCP) ----> INGEST WORKER
                                                                  |
        +---------------------------+----------------------------+
   PIPELINE 1                   PIPELINE 2                   PIPELINE 3
   LIVE VIEW (relay)            AI ANALYTICS                 EVIDENCE CAPTURE
        |                            |                            |
   hls.js in browser        motion gate > detect >         ring buffer, HLS
   NOTHING SAVED            crop > plate > OCR             segments, fixed N
        |                   match vs LOCAL watchlist  <--- promote(t +/- 30s)
        v                            |                     on match only
   CONTROL ROOM WALL        sighting row + crop (~2 KB)         |
                                     |                          v
                                     v                   CLIP + SHA-256 + audit
                        SEARCH / GIS ROUTE / ALERTS
                        "where has GJ01AB1234 been?"
```

### 1.3 What is stored, and what is not

| Pipeline | Persists | Does **not** persist |
|---|---|---|
| 1, Live view | nothing | all video passing through |
| 2, Analytics | sighting rows (text) plus plate crop, about 2 KB | frames, full-frame JPEGs |
| 3, Evidence | promoted clip plus audit row | the rolling buffer, which overwrites itself |

**Governing rule:** video becomes permanent only where a specific, logged, auditable watchlist match justifies it. This is a civil-liberties position as much as a capacity one, and it maps onto the bonus criteria for privacy protection and auditability.

### 1.4 Data contracts

Every component reads and writes fixed shapes, defined in `docs/03-data-contracts.md`: the `cameras` registry, `sightings` (the spine of the system, one row per plate read, deduplicated at 60 seconds per plate per camera), `watchlist`, `alerts`, and zone `events`. All timestamps are stored as timezone-aware UTC in ISO-8601. Plates are stored normalised alongside the raw OCR output, so a normalisation change can be replayed. No URL containing a credential is ever written to storage.

---

## 2. Integration strategy: heterogeneous cameras, NVRs and VMS (Dimension 2)

The hard part on day one is heterogeneity, not scale. Twenty-six departments run twenty-six different arrangements. Sentinel integrates through a layered connector model, and the departments' own systems keep running untouched: read-only pull, no writes, no configuration changes, no control-API calls.

### 2.1 Onboarding: three routes, one registry

Every camera enters the same `cameras` table by one of three routes, all working in the delivered platform:

- **Bulk import.** A CSV of camera metadata, validated row by row, with each row accepted or rejected and a reason given.
- **Manual entry.** A single-camera onboarding form and the equivalent API call.
- **API onboarding.** `POST /api/cameras`, for programmatic registration from a department's own inventory system.

The registry is the single source of truth. Nothing downstream hard-codes a camera id or a stream URL.

### 2.2 The connector ladder (Model 3 federation)

| Source exposes | Connector | Notes |
|---|---|---|
| RTSP or ONVIF | Direct pull, RTSP over TCP | The common case. TCP only, because UDP does not survive NAT or government firewalls. |
| HLS or WebRTC gateway | Direct pull over the CDN | Traverses any network. This is what the sandbox exposes. |
| Vendor VMS with an API or SDK | **Per-vendor adapter** | The adapter translates the vendor's API into the registry's contract. |
| Vendor SDK only, Windows-only, or behind NAT with no inbound route | **Department-side collector** | A small agent inside the department network speaks the vendor SDK locally and pushes **outbound** to Sentinel. Outbound connections traverse NAT without firewall changes. |

Across 26 departments, expect three to six to expose neither RTSP nor ONVIF. That is potentially thousands of cameras a design without a collector simply cannot reach, and the failure would be discovered during rollout rather than during design. The department-side collector is the structural answer.

The **metadata-exchange bus** and **cross-system event correlation** of Model 3 sit above this ladder. Adapters and collectors normalise camera and event metadata into one schema, so downstream applications, dashboards and analytics see a single interface regardless of the source vendor. Model 3 is the answer to heterogeneity, which is a day-one problem in a real deployment, rather than to scale, which arrives later.

### 2.3 Analog cameras

An analog camera reaches the platform as analog camera, then DVR or encoder, then RTSP. Everything downstream of the encoder is identical to the IP case. No special handling is required.

### 2.4 Private CCTV

The registry carries an `ownership` field, set to `government` or `private`. Public-facing private cameras, in housing societies, malls and commercial premises, are onboarded into a **view-only tier** with an explicit consent record attached. They are viewable and analysable where that is feasible and permitted, and they are never treated as government assets.

### 2.5 The guarantee to departments

Sentinel is consume-only. It pulls streams read-only. It never publishes to a gateway, never calls a control API, never downloads stored footage, and never writes to a departmental system. A department's VMS, its storage and its retention policy are unchanged by onboarding. This is enforced at the architecture level and can be checked against the source.

---

## 3. Ingesting geographically dispersed streams (Dimension 5, deployment)

### 3.1 Three tiers

| Tier | Runs | Responsibility |
|---|---|---|
| **Edge** (district or department) | Near the cameras | Stream pull, decode, motion gate, detection, OCR, **local watchlist match**, ring buffer. Emits text and crops. |
| **Regional** | District cluster | Aggregation, regional search index, evidence store, model rollout, health scoring. |
| **Central** (SCRB or state data centre) | State | Statewide search, cross-region route correlation, watchlist master, dashboards, and integration to VAHAN, SARTHI, eGujCop, AFIS and NAFIS. |

Only text metadata and evidence crops cross the WAN. A route query is answered centrally by joining sightings that arrived as metadata from every region.

### 3.2 Transport rules, validated against the sandbox

- **RTSP over TCP, always.** UDP fails across NAT and firewalls and delivers corrupt frames, which then look like model bugs and get debugged in the wrong place. Where RTSP is blocked, **HLS** is the fallback, and the transport actually used is recorded per camera in the registry. WebRTC over WHEP is the low-latency control-room path where it is reachable.
- **All timing from PTS**, never from frame arrival time and never from the reported frame rate. On connect, the gateway replays a buffered GOP, so the first frames arrive faster than real time. Anything timed by arrival computes impossible vehicle speeds.
- **Reconnect with jittered exponential backoff:** `base 2 s * 2^n * random(0.5, 1.5)`, capped at 30 s. Without the jitter, a regional event produces a synchronised reconnect storm (section 7.4).
- **Loop and scene-discontinuity recovery.** Background models, trackers and re-identification galleries reset cleanly across a hard scene cut.

These rules come from the sandbox's own pre-submission checklist. The delivered `frame_source.py` implements every one of them, and each was verified against the live feeds. See the Feed Compliance section of the submission.

---

## 4. Watchlist integration and real-time alerting (Dimension 3 in part, plus the alert workflow)

### 4.1 Matching at the edge against a cached watchlist

Matching happens at the edge against a locally cached copy of the watchlist. It is never a per-detection call to a central system.

The reason is arithmetic. At 80,000 cameras and one detection per camera per minute, central matching would generate about **1,333 queries per second and 115 million per day** [model] against VAHAN and eGujCop. That load would take down the state's own systems of record. The watchlist itself is small, in the hundreds of thousands of records and tens of megabytes, so it can be synced out to every edge node every few minutes. Only confirmed matches call a central system, and then only to enrich the record, which turns 1,333 queries per second into a handful.

Edge matching also keeps working when the WAN or the central tier is down. Edge nodes match against their cached list and queue the results.

### 4.2 Matching logic

Plates are normalised by uppercasing and stripping non-alphanumeric characters, then matched in three steps:

1. Exact match.
2. OCR-ambiguity map: `O/0, I/1, S/5, B/8, Z/2, G/6, Q/0`.
3. Levenshtein distance of 1 or less, for reads of 8 characters or more.

Reads shorter than 8 characters are treated as partial. They are stored as low-confidence route candidates and they never fire an alert. Every alert records its `match_type`, exact or fuzzy, and the edit distance.

### 4.3 Alert workflow: prioritisation, visualisation, interaction

1. A detection produces a **sighting written to durable storage** before any alerting logic runs.
2. The matcher runs against the cached watchlist. A **five-minute cooldown per plate per camera** stops one vehicle from flooding the operator's feed.
3. On a match, an **alert row is written, then broadcast**. Persisting before broadcasting means a detection never exists only in the memory of a process that is about to crash. In the demonstrated system this is an in-process queue with Server-Sent Events; in production it is a durable queue such as Kafka or NATS. The difference is stated rather than glossed over.
4. The operator sees the alert on the dashboard within about two seconds: plate, **plate crop**, camera, department, timestamp, category, severity and match type. The crop is what makes an alert worth acting on rather than worth ignoring.
5. The operator acknowledges it, the acknowledgement is persisted, and one click leads to the vehicle's **route**.

### 4.4 Route reconstruction

`GET /api/plates/{plate}/route` returns the vehicle's complete, ordered, timestamped movement: each stop with its camera, department, coordinates, timestamp and crop; elapsed time and implied speed between consecutive stops; total distance and duration; the list of **departments crossed**; and any **coverage gaps**, shown rather than hidden.

Implied speed is a sanity check, not a claim about the vehicle. An implausible speed flags a stop as suspect instead of drawing a confident line between two points that may not be the same vehicle.

A route that crosses Police, GSRTC and Municipal cameras is direct evidence that systems belonging to different departments have been integrated into one platform.

---

## 5. Video analytics (Dimension 3)

### 5.1 ANPR, primary and demonstrated

The pipeline is a cascade. A motion gate using MOG2 background subtraction skips inference on static frames. Vehicle detection runs YOLOX or RT-DETR, both Apache-2.0, on ONNX Runtime. The vehicle crop, never the full frame, goes to plate-region detection and OCR with PaddleOCR, also Apache-2.0. Plate crops are upscaled and contrast-adjusted before OCR, because plates in wide overview footage are small. Reads are normalised and written as deduplicated sightings.

**Licensing is a procurement decision at 80,000 cameras.** The stack is deliberately Apache-2.0, MIT and BSD throughout. It does not use Ultralytics YOLO, which is AGPL-3.0: linked into an application the State would own, that licence can pull the whole codebase under AGPL. It does not use Elasticsearch or Redis under their post-2021 and post-2024 licences; OpenSearch and Valkey are the production substitutes. The distinction that matters is that AGPL is hazardous as a linked library and generally acceptable in a separate service you merely run.

### 5.2 Object and intrusion detection, demonstrated

The detector already classifies person, car, truck, bus, motorcycle and bag, so three of the four analytics named in Evaluation Area 5 come with ANPR at no extra cost. Object counts per class per camera appear in the dashboard and in the detection report.

Intrusion detection uses zone polygons and crossing lines stored per camera in normalised coordinates from 0 to 1, so a zone survives a change of camera resolution. A tracked object whose foot point enters an intrusion zone, or a track that crosses a line in the configured direction, writes a zone `event` and raises an alert for high-severity zones.

### 5.3 Person and vehicle tracking

Track continuity within a camera uses ByteTrack (MIT), fed PTS deltas rather than arrival times. Cross-camera correlation for vehicles is done by plate identity, which is what produces the route. At statewide scale, appearance-based re-identification is the documented extension for vehicles whose plate cannot be read, under the same edge-first, metadata-only posture.

### 5.4 Facial recognition: approach and privacy controls (described, not built)

Facial recognition is described here because the problem statement requires it. It is not implemented and is not claimed to be.

The approach would be face detection at the edge, then embedding, then matching against a watchlist gallery of missing and wanted persons held centrally, with the same edge-cached posture as plate matching.

The privacy controls are not optional and are stated here as part of the design. Facial recognition runs only against a specific authorised gallery. No general-population face database is built. Every match is logged and auditable. Embeddings for non-matches are not retained. Use is governed by a documented authorisation and retention policy. The rule that video is kept only on cause applies more strictly to faces than to plates.

---

## 6. Cybersecurity architecture (Dimension 4)

| Control | Design |
|---|---|
| **Credential handling** | Credentials live only in the environment or a secret store. They are never hard-coded, logged, persisted or displayed unmasked, and no URL containing a credential is written to storage. Production uses a secrets vault such as HashiCorp Vault, with per-department credentials and scheduled rotation. |
| **RBAC** | Department-scoped roles. A department sees its own cameras by default; cross-department access is explicit and audited. Operator, investigator and administrator tiers. The demonstrated system ships a single role; production RBAC is designed but not built. |
| **Encryption** | TLS in transit on every hop: stream pull, API and inter-tier traffic. Encryption at rest for the evidence store and the databases. |
| **Network segmentation** | Edge nodes sit in department DMZs, central services in a segmented state data-centre network, with least-privilege firewall rules between tiers. Because Sentinel is consume-only, there is no inbound path from it into a departmental control plane. |
| **Auditability** | Every evidence promotion writes an audit row carrying the event id, the trigger reason and the SHA-256 of the clip. Every watchlist change, every acknowledgement and every cross-department access is logged. Chain of custody is a deliverable of the system, not a report produced afterwards. |
| **Credential-rotation resilience** | A per-department credential health check with a documented escalation path. A department changing a password without telling anyone is an organisational problem that presents as a technical outage, and it is budgeted for. |

---

## 7. Scaling to roughly 80,000 cameras (Dimensions 6 and 9)

> Every capacity figure in this section is a **[model]** from stated assumptions until it is replaced by measurement. The two figures that anchor everything, **sustained inference frames per second per camera** and **real detection rate per camera**, were measured on the delivered system and are carried in as **[measured]**. See the measurements table in the submission.

### 7.1 Why not centralise, and why not Model 4

| Per-camera bitrate | Aggregate at 80,000 cameras |
|---|---|
| 1 Mbps (720p) | **80 Gbps** |
| 3 Mbps (1080p) | **240 Gbps** |
| 8 Mbps (4K) | **640 Gbps** |

Sustaining 240 Gbps into one facility is mid-size-ISP backbone territory. It is a procurement and physical-plant problem before it is a budget line. Running analytics at the edge changes what has to cross the WAN at all:

| What crosses the WAN | Volume [model] |
|---|---|
| Raw video, centralised | 240 Gbps |
| One full-frame JPEG per detection | 3.46 TB/day |
| One vehicle crop per detection | 0.69 TB/day |
| **Plate crop and text metadata only** | **about 2.1 Mbps** |

That is a reduction of roughly 3,750 times in WAN load, and it is why Model 4, fully centralised, is not proposed for statewide use.

### 7.2 Compute, and the ceiling that is usually missed

| Optimisation level | Streams per GPU [model] | GPUs for 80,000 |
|---|---|---|
| Naive: every frame, full-frame ANPR | 30 | 2,667 |
| 5 fps sampling | 50 | 1,600 |
| plus motion gating | 100 | 800 |
| plus cascade detector and INT8 | 150 | 533 |
| plus ROI cropping and tuning | 200 | **400** |

The gap between the naive and the tuned figure is 6.7 times, or about 2,200 GPUs. Fleet size is a consequence of engineering choices rather than a fixed cost.

**Decode usually binds before inference does.** Every stream has to be H.264 or H.265 decoded before any model sees it, and a GPU's decode engines cap out at roughly 20 to 40 concurrent 1080p30 sessions:

| Decode sessions per GPU | GPUs for **decode alone** |
|---|---|
| 20 | 4,000 |
| 30 | 2,667 |
| 40 | 2,000 |

If inference tuning reaches 200 streams per GPU but NVDEC caps at 30, the fleet is sized by decode at 2,667 GPUs and the tensor cores sit roughly 85% idle. Mitigations: decode only the frames you will run inference on, which is the largest single saving; prefer H.265 sources; use CPU decode for low-frame-rate streams; and provision against whichever ceiling actually binds, measured independently rather than assumed.

### 7.3 Storage: hot, warm and cold, and the class that gets forgotten

| Data | Volume [model] | Tiering |
|---|---|---|
| Evidence clips at 10,000 hits per day | 220 GB/day | Warm, then cold archive. Promoted clips are replicated to a second region; at roughly 22 MB each this is cheap. |
| **Detection snapshots**, if stored as full frames | **3.46 TB/day** | Store plate crops of about 2 KB instead of full frames of about 30 KB. That is a 15-fold reduction, to 0.23 TB/day. Full frames only for confirmed hits. |
| Sighting records | 115 M/day, about 42 billion per year, about 21 TB/year indexed | Hot for 7 days, warm for 90, then cold or frozen. Decide the shard and tier strategy on day one; retrofitting it after the index is built is a migration with no good window. |

Retention honours each department's own policy, which varies from 7 days to more than 15. The platform deliberately keeps metadata for longer than it keeps video.

### 7.4 Availability, high availability and disaster recovery

- **Reconnect storms.** Jittered backoff, per-edge connection admission control using a token bucket, staggered cold start, and a circuit breaker per department. A regional power event must not let 80,000 recovering clients take down departmental NVRs with GOP-replay bursts.
- **Split-brain camera ownership.** Distributed leases held in etcd or Consul. A node holds a renewable, time-bounded lease per camera, so there are never two owners, never double pulls and never duplicate alerts.
- **The alert path is the real single point of failure.** Detections hit a durable queue before any alerting logic runs, so if alerting is down, events queue and replay. End-to-end synthetic testing injects a known plate on a schedule and alarms if no alert comes back.
- **Evidence-loss window.** Waiting 30 seconds after the event to close the promoted clip means a recovery point objective of about 30 seconds on node failure. This is mitigated by writing the pre-event portion immediately and by replicating promoted clips across regions. The RPO is stated rather than left implicit.
- **Loss of a regional data centre.** Cross-region replication for the search index and the databases. Edge nodes keep detecting and buffer their metadata for the duration of the outage.

### 7.5 Day-2 operations

At a 2% failure rate, about 1,600 cameras are broken at any given moment, permanently. There is no all-green state to aim for, so the system has to rank faults rather than report them.

What this requires is a continuously computed quality score per camera covering no signal, frozen frame, too dark or blown out, out of focus, lens obstruction, **camera drift or rotation** detected by comparing a periodic scene hash against a reference, and clock skew. The output is a ranked maintenance worklist, not a dashboard.

Camera drift is the one that does damage quietly. A camera nudged 15 degrees over several months still produces good-looking video while its ROI and calibration are silently wrong, and nothing alarms.

**Model rollout** across roughly 1,600 edge nodes goes shadow, then canary at 1%, 10%, 50% and 100%, with automatic rollback on regression. **Configuration** is declarative and version-controlled through GitOps, because configuration drift across 1,600 nodes cannot be unwound once it starts.

### 7.6 Monitoring, logging, health and load balancing

Central observability for metrics, logs and traces at each tier. Health checks per camera and per node. Horizontal scaling of stateless workers behind the registry. Dynamic assignment of streams to GPUs, which consolidates load in quiet hours and allows idle GPUs to be powered down, and which is also what makes lease mobility in section 7.4 possible.

---

## 8. Cost and benefit analysis (Dimension 7)

- **Bandwidth.** Edge processing turns a 240 Gbps centralised backbone requirement into about 2.1 Mbps of metadata. That is the difference between a network the State cannot buy and one it already has.
- **Compute.** The 6.7-fold tuning gap is roughly 2,200 GPUs of avoidable spend. The NVDEC ceiling means that sizing on inference alone under-provisions the fleet by five to eight times. Provision against the binding ceiling.
- **Storage.** Storing crops instead of frames is a 15-fold reduction on the largest data class, from 3.46 TB/day to 0.23 TB/day.
- **Licensing.** A licence at 500 rupees per camera per year is 4 crore rupees per year at 80,000 cameras. An Apache, MIT and BSD stack removes per-camera licensing altogether, so the hackathon's open-source requirement is also the cheapest option available.
- **Cloud egress.** Even after optimisation, roughly 0.69 TB/day of snapshots leaving a public cloud is a recurring egress bill with no end date. The recommendation is on-premise deployment in a state data centre, and the egress arithmetic is shown so the choice can be checked.
- **Idle GPU time.** Consolidating streams onto fewer GPUs overnight avoids paying peak rates around the clock on a 1,600-GPU fleet.

---

## 9. Information required from each department (Dimension 8)

Assessing integration feasibility needs a structured set of information from each participating department. This questionnaire is a submission artefact in its own right.

| # | Item | Why it is needed |
|---|---|---|
| 1 | Camera inventory: count, make and model, analog or IP, resolution, codec | Sizes ingest and decode, and selects the connector type |
| 2 | VMS or NVR platform, vendor, version, AMC status | Determines adapter versus direct pull versus collector |
| 3 | Feed-sharing capability: RTSP, ONVIF, vendor SDK, API, or none | Picks the rung on the connector ladder (section 2.2) |
| 4 | Network topology: public IP, NAT, private WAN, or air-gapped | Determines reachability and whether a department-side collector is needed |
| 5 | Storage: local or cloud, and retention period in days | Sets the retention policy honoured for that department and sizes evidence tiering |
| 6 | Camera geolocation, and bearing or field of view where known | Populates the GIS registry and the route geography |
| 7 | Credentials, a named technical contact, and the change process | Credential rotation is the most common cause of silent camera loss (section 6) |
| 8 | Bandwidth available at each site | Determines whether processing sits at the edge or the regional tier |
| 9 | Legal and consent status for any private cameras | Governs the view-only private tier (section 2.4) |
| 10 | Existing integrations already in use, such as VAHAN or eGujCop | Avoids duplicate integration work and informs enrichment |

---

## 10. Roadmap (Dimension 10)

| Phase | Scope | What it proves |
|---|---|---|
| **0, Sandbox (now)** | 30 to 50 cameras, 5 departments, one node | ANPR, watchlist, alerts, route and the registry with GIS all work against real feeds |
| **1, Pilot district** | One district, one department's real cameras, one edge node plus central | Real-world integration, day-2 health, measured streams per GPU and detection rate |
| **2, Multi-district** | 3 to 5 districts, 3 to 5 departments, regional tier introduced | Federation adapters and the department-side collector, cross-region route correlation, model rollout pipeline |
| **3, Statewide** | Towards 80,000 cameras across all 26 departments | Full edge, regional and central fleet; HA and DR; GitOps configuration; dynamic GPU consolidation; VAHAN, SARTHI, eGujCop, AFIS and NAFIS enrichment |

Facial recognition, appearance-based cross-camera re-identification and predictive analytics are roadmap items. Each is introduced only after the ANPR, route and watchlist core is proven at the preceding scale, and each under the same rules: process at the edge, keep metadata rather than video, and measure before claiming.

---

## Appendix A: the 30 versus 50 camera discrepancy

The public problem statement refers to about 50 cameras. The catalogue available after login lists `cam01` through `cam30`. The system is built against the catalogue, which the organisers describe as the contract. The discrepancy is recorded here rather than resolved silently in either direction.

## Appendix B: what this system does not do

- **No arbitrary rewind and no central recording of all video.** Both the privacy posture and the 240 Gbps arithmetic rule it out. Video is captured on justified cause only.
- **No live facial recognition demonstration.** The approach and its privacy controls are described in section 5.4. It is not built and is not claimed as built.
- **No Model 3 federation demonstration.** The sandbox exposes bare stream endpoints. There are no departmental VMS platforms inside it to federate, so a federation demo would be demonstrating something that is not there. Model 3 is documented in section 2.2 as the integration path for real departments.

Every figure in this document is labelled as measured or modelled. A single invented measurement would make the rest of them worthless, so none of them are invented.
