# Sentinel: Technical Proposal (High-Level Design)

**Integrated Video Management and Analytics Platform**\
Gujarat Police Innovation Challenge 2026. Home Department / State Crime Records Bureau.\
Revised 25 September 2026 (supersedes the version of 15 September).

**Proposed model: Model 1 + Model 2 + Pipeline 3 (hybrid).** Under the brief's reference models this is a **Model 5 — Hybrid / Innovative Architecture** built from **Model 1 — Centralised CCTV Registry & GIS Mapping** (mandatory) and **Model 2 — Unified Viewing & Metadata Analytics**, plus an **event-triggered evidence-capture pipeline (Pipeline 3)**. **Model 3 — VMS Federation & Middleware Integration** is documented as the integration path for departments whose systems cannot be pulled directly. **Model 4 — Central VMS & AI Platform** is argued against for statewide use in section 7.2.

**How to read the numbers.** Three labels are used, always in square brackets after the figure. *measured*: one of the six figures produced by the formal 10-minute measurement run on the demonstrated system on 25 September 2026 (section 7.1); no other figure in this document carries that label. *model*: arithmetic from assumptions that are stated where they are used, to be replaced by measurement in the pilot before anything is procured. *estimate*: a size or a judgement that no code has measured. Three kinds of number carry no label: counts of events observed in a named run (for example the line-crossing events of section 5.2), which say what happened rather than what the system can carry; design settings such as a 60-second dedupe window or a 5-minute alert cooldown, which are parameters rather than results; and inputs taken from the problem statement (26 departments, about 80,000 cameras).

**Where the ten dimensions are answered**

| # | Dimension | Section |
|---|---|---|
| 1 | Overall Architecture | 1 |
| 2 | Integration Strategy | 2 |
| 3 | AI & Video Analytics | 4, 5 |
| 4 | Cybersecurity Architecture | 6 |
| 5 | Deployment Architecture | 3 |
| 6 | Infrastructure Sizing | 7, 8.1 |
| 7 | Cost-Benefit Analysis | 8 |
| 8 | Department-wise Information Requirements | 9 |
| 9 | Scalability Strategy | 7 |
| 10 | Future Roadmap | 10 |

---

## 0. Executive summary

Gujarat runs CCTV across 26 departments on systems that do not interoperate: a mix of analog and IP cameras, different VMS platforms, storage held in different places under different retention rules, and sites as much as 1,000 km apart. Tracing one vehicle today means asking each department separately, by hand.

Sentinel puts a single platform over those systems without changing any of them. It maintains one camera registry with a GIS console, runs video analytics continuously (ANPR first, with vehicle and person detection, tracking, intrusion zones and line crossing alongside it), checks every plate read against a watchlist, raises alerts automatically, and reconstructs a vehicle's timestamped, location-wise route across the network from a single registration number.

The design runs analytics where the cameras are. Only a text row and a small plate crop per read cross the wide-area network. At 80,000 cameras, carrying raw video to one place needs roughly 240 Gbps of sustained inbound capacity [model]; analysing at the edge reduces that to roughly 23 Mbps [model], about 10,000 times less [model]. The same split sets the privacy posture. Live video is relayed to the control room, not recorded: the only video the platform writes to disk is a self-overwriting 20-second relay window per analysed camera. Analytics keeps only text rows and a plate crop of about 2 KB [estimate]. Full video would become permanent only through Pipeline 3, on a specific, logged, auditable watchlist match; Pipeline 3 is designed and validated separately and is **not built** in the demonstrated system.

The demonstrated system runs on a single laptop with a 4 GB GPU. It registers the organisers' 30 sandbox cameras and 28 local sample-footage feeds (58 cameras), pulls five sandbox cameras live over RTSP for continuous analytics, and shows every registered camera on its Live Wall through the relay. Six figures were measured in a formal 10-minute run on 25 September (section 7.1), and the ANPR viability gate passed on the live sandbox. Section 7 covers what changes between that and a statewide deployment, and section 8 what it costs.

---

## 1. Overall architecture (Dimension 1)

### 1.1 In one paragraph

One upstream pull per camera feeds three concurrent pipelines. **Pipeline 1** relays live video to the control room and records nothing. **Pipeline 2** runs AI analytics at the node and stores only text metadata plus a small plate crop. **Pipeline 3** keeps a fixed-size rolling buffer of compressed video and promotes a 60-second clip, 30 seconds either side of the event, to permanent storage only when a watchlist match fires; it is **designed and validated separately, not built in the demonstrated system**. Beneath all three sits the **Model 1 registry**: the camera inventory and GIS layer that tells every component which cameras exist, where they are, and how to reach them.

### 1.2 Component diagram

```
          +----------------------------------------------------+
          |  MODEL 1: CAMERA REGISTRY + GIS                    |
          |  the control plane for everything below            |
          |  - id, department, location, bearing, FOV, range   |
          |  - stream URLs (never credentials), codec, tier    |
          |  - health, last_seen, ROI, zones                   |
          +--------------------------+-------------------------+
                                     | tells the node what to pull
                                     v
CAMERA GRID -- ONE pull per camera (RTSP over TCP) --> NODE (ingest worker)
                                                                |
        +-------------------------------+-----------------------+
   PIPELINE 1                      PIPELINE 2                      PIPELINE 3
   LIVE VIEW (relay)               AI ANALYTICS                    EVIDENCE CAPTURE
        |                               |                          designed and validated
   self-overwriting 20 s           motion gate > detect >          separately; NOT BUILT
   relay window, hls.js            track > crop > OCR              in the demo
   RELAYED, NOT RECORDED           sighting row + crop                  |
        |                          written BEFORE matching         ring buffer, fixed N
        v                               |                          segments, overwrites
   COMMAND + LIVE WALL             match vs LOCAL watchlist ---->  promote(t +/- 30 s)
                                        |                          on a match only
                                        v                               |
                                   alert row, then SSE                  v
                                   (API tails the table)           CLIP + SHA-256 + audit
                                        |
                                        v
                            SEARCH / GIS ROUTE / ALERTS
                            "where has GJ01AB1234 been?"
```

### 1.3 The names used in this document

The models are the brief's; the pipelines are this design's. Each name means the same thing in the HLD, the deck and the videos.

| Name | What it is | Stores |
|---|---|---|
| **Model 1 — Centralised CCTV Registry & GIS Mapping** | The camera inventory, GIS console, onboarding, health and gap analysis (mandatory) | camera metadata |
| **Model 2 — Unified Viewing & Metadata Analytics** | Unified viewing **and** metadata analytics, connecting directly to each system. Live viewing belongs here | text metadata and small crops |
| **Model 3 — VMS Federation & Middleware Integration** | A middleware layer between the platform and departmental VMS platforms. It is **not** live streams | described only |
| **Pipeline 1** | Live view relayed to the control room (the Command screen and the Live Wall) | nothing: a self-overwriting 20-second relay window |
| **Pipeline 2** | AI analytics at the node: detect, track, OCR, sighting, watchlist match, alert | sighting rows and plate crops |
| **Pipeline 3** | Event-triggered evidence capture: a clip of plus or minus 30 seconds promoted on a watchlist hit | the promoted clip and its audit row; the only pipeline that stores video |

"Live views on a central command, nothing saved" is **Pipeline 1**. Live streams are part of **Model 2**, never Model 3.

### 1.4 What is stored, and what is not

| Pipeline | Persists | Does **not** persist |
|---|---|---|
| 1, Live view | nothing permanent. Relayed, not recorded: for each analysed camera, a self-overwriting 20-second relay window (ten 2-second segments; segment eleven deletes segment one) | all video passing through |
| 2, Analytics | sighting rows (text) plus a plate crop capped at 160 px wide, about 2 KB [estimate] | frames, full-frame JPEGs |
| 3, Evidence *(designed and validated separately, not built in the demo)* | the promoted clip plus an audit row | the rolling buffer, which overwrites itself |

**Governing rule:** watching is not storing. Video becomes permanent only where a specific, logged, auditable watchlist match justifies it. This is a civil-liberties position as much as a capacity one, and it maps onto the bonus criteria for privacy protection and auditability. In the demonstrated system, where Pipeline 3 is not built, no video is ever kept beyond the 20-second relay window.

### 1.5 What the demonstrated system builds, and what it describes

| Part of the design | In the demonstrated system |
|---|---|
| **Model 1**: registry and GIS console, onboarding by form, CSV and API, health, gap analysis, API documentation | **Built.** 58 cameras registered: the organisers' 30 and 28 local sample feeds. Departments and coordinates of the sandbox cameras and of the sample feeds are **seeded and disclosed** (Appendix C) |
| **Model 2**: a unified viewer over at least two different systems | **Built.** System A is the organisers' sandbox gateway; system B is a local mediamtx server publishing the sample feeds (section 2.7) |
| **Model 2**: metadata analytics at the node | **Built.** One worker (the *node*) turns frames into sighting rows and crops written before any alerting, matches a cached watchlist locally and writes alert rows; the API streams alerts over Server-Sent Events by tailing the table. In the demo a node is a worker process on one laptop; at statewide scale it is an edge box (section 3.1) |
| **Pipeline 1**: live view | **Built.** Relayed, not recorded: a self-overwriting 20-second relay window. Every registered camera can be opened on the Live Wall (section 3.3) |
| **Pipeline 2**: analytics | **Built.** ANPR, vehicle and person detection, object counts, intrusion zones and line crossing (section 5) |
| **Pipeline 3**: evidence clips on a watchlist hit | **Designed and validated separately (`docs/reference/model-02-1-event-triggered-evidence.md`), not built in the demo.** The alert table's clip columns stay empty |
| Search, route and reports | **Built.** ANPR-tolerant search (section 4.5). The multi-camera route shown is a demonstration vehicle labelled `demo` everywhere (section 4.4) |
| Login, roles, sessions and audit | **Built** (section 6) |
| Cross-camera route on the sandbox feeds | **Not built.** No real vehicle has been read on two sandbox cameras, and the harvest of the organisers' recordings was cut. The HLS path exists for viewing only |
| **Model 3** federation | Described only (section 2.3) |
| Facial recognition | Described only, with its privacy controls (section 5.4) |

### 1.6 One time base, and a label on every row

A route is only as good as its clock. The organisers' feeds reach the platform on two different clocks: a live RTSP pull runs in real time from the moment of connection, while the HLS copy is a 12-hour recording on a shared timeline whose position the reader chooses. A route that mixes the two computes impossible speeds. The design therefore fixes the time base before anything else:

- Every sighting, event and alert stores `seen_at` (the stream-time instant), `wall_time` (when this system observed it) and `clock_source`, the clock that produced `seen_at`:

| `clock_source` | Produced by | `seen_at` is |
|---|---|---|
| `rtsp-live` | a live RTSP pull: the sandbox gateway, or the local sample-feed server | pull start plus the stream's presentation timestamp (PTS), never arrival time |
| `hls-vod` | the organisers' HLS recording | a declared recording epoch plus the position on the shared timeline. The epoch is a stated constant, never presented as a measurement |
| `harvest` | reads taken from those recordings after the fact (designed; not run in the demo) | as `hls-vod` |
| `demo` | the demonstration vehicle, injected through the real write path | the injected instant |
| `replay` | a looped local file, in tests only | pull start plus frame index over frame rate, continuous across loops |

- Every row also carries its **provenance**: `live`, `harvest`, `demo` or `test`. Test rows live in a separate test database and never reach the working one.
- Route reconstruction groups stops by `clock_source` and computes elapsed time and implied speed only within a group; where a route crosses groups it returns a warning instead of a speed. Dedupe, cooldowns and throttles key on stream time within one clock, and derive from stored rows, never from process memory.
- **A demo row never passes as a live one.** Provenance is stored, shown as a badge wherever rows are displayed, and carried in every export (the detection report and the route export have a provenance column). The first screen after login says which data is demonstration data. Demo rows can be removed by provenance alone.

### 1.7 Data contracts

Every component reads and writes fixed shapes, defined in `docs/api.md`: the `cameras` registry, `sightings` (the spine of the system, one row per plate read, deduplicated within 60 seconds per plate per camera per clock), `watchlist`, `alerts` (watchlist and zone alerts in one table, with a monotonic sequence used as the alert stream's cursor), zone `events`, and the `users`, `sessions` and `audit` tables. All timestamps are stored as timezone-aware UTC in ISO 8601 and converted to IST only for display. Each read keeps three forms of the plate (section 4.2), so a change to normalisation can be replayed. No URL containing a credential is ever written to storage.

---

## 2. Integration strategy: heterogeneous cameras, NVRs and VMS (Dimension 2)

The hard part on day one is heterogeneity, not scale. Twenty-six departments run twenty-six different arrangements. Sentinel integrates through a layered connector model, and the departments' own systems keep running untouched: read-only pull, no writes, no configuration changes, no control-API calls.

### 2.1 Onboarding: every route leads into one registry

Every camera enters the same `cameras` table. All of these routes work in the demonstrated system:

- **Manual entry.** An add-camera form in the Cameras screen (evaluator or admin role), and the equivalent `POST /api/cameras`. Edits go through the same screen or `PATCH`.
- **Bulk import.** A CSV upload screen (admin role), validated row by row: each row is accepted or rejected with a reason, and the file is limited to 2 MB and 5,000 rows.
- **API onboarding.** `POST /api/cameras`, for programmatic registration from a department's own inventory system, documented in the exported OpenAPI file (`deliverables/registry-api.json`).
- **Catalogue adapter.** The organisers' catalogue is read in either of the shapes they publish: the sandbox's `cameras.json` (id and name) or the Integrator's Guide `GET /api/ingest` (id, location, codec, status, stream properties and URLs). What the catalogue supplies is used verbatim; a committed seed file fills only what it lacks, and says so.

The 28 local sample feeds were registered from a committed CSV (`data/local_feeds.csv`) through the same path. Every onboarding action is written to the audit trail with the username (section 6).

The registry is the single source of truth. Nothing downstream hard-codes a camera id or a stream URL.

### 2.2 The GIS console (Model 1)

The Map screen is the registry's GIS console. It shows every camera as a pin coloured by department and marked by health, over a choice of basemaps (street, light and satellite imagery), with:

- **department layers** that can be switched on and off;
- **field-of-view coverage sectors**, drawn for each camera from the bearing, field-of-view angle and range held in its registry record;
- **activity** per camera, from its recent reads and detections;
- **cluster hulls** drawn around each geographic cluster of cameras;
- **coverage gaps**: cameras whose nearest neighbour lies beyond the gap threshold, from the same service that produces the gap-analysis report.

A pin opens the camera's full record. The Leaflet styles are bundled with the application, so pins, sectors and routes still render when no basemap tiles can be fetched.

**Map tiles are a licensing question as well as a technical one.** For the demonstration, the basemaps come from OpenStreetMap's public tile server and Esri's keyless Canvas (dark and light grey) and World Imagery services, each used under its provider's terms with attribution shown on the map; OpenStreetMap's public tiles in particular are for light use and may not be bulk-downloaded or pre-seeded. None of them is a production dependency. Production serves tiles from a self-hosted tile server in the state data centre (OpenStreetMap data under the ODbL, rendered in-house) or from ISRO's Bhuvan, so the map works without the public internet and no camera location leaves the State's network inside a tile request.

### 2.3 The connector ladder: direct pull (Model 2) and federation (Model 3)

| Source exposes | Connector | Model | Notes |
|---|---|---|---|
| RTSP or ONVIF | Direct pull, RTSP over TCP | Model 2 | The common case, and what the demonstrated system does. TCP only, because UDP does not survive NAT or government firewalls. |
| HLS or WebRTC gateway | Direct pull over the gateway or CDN | Model 2 | Traverses any network. The sandbox exposes this; the demonstrated system uses it for viewing only. |
| Vendor VMS with an API or SDK | **Per-vendor adapter** | Model 3 | The adapter translates the vendor's API into the registry's contract. |
| Vendor SDK only, Windows-only, or behind NAT with no inbound route | **Department-side collector** | Model 3 | A small agent inside the department network speaks the vendor SDK locally and pushes **outbound** to Sentinel. Outbound connections traverse NAT without firewall changes. |

Across 26 departments, expect three to six to expose neither RTSP nor ONVIF [estimate]. That is potentially thousands of cameras that a design without a collector cannot reach, and the failure would be discovered during rollout rather than during design. The department-side collector is the structural answer, and the demonstrated system is itself deployed in that shape (section 3.4).

The **metadata-exchange bus** and **cross-system event correlation** of Model 3 sit above the adapter and collector rungs. They normalise camera and event metadata into one schema, so downstream applications, dashboards and analytics see a single interface regardless of the source vendor. Model 3 is the answer to heterogeneity, which is a day-one problem in a real deployment, rather than to scale, which arrives later. It is described here and not built: the sandbox contains no departmental VMS to federate.

### 2.4 Analog cameras

An analog camera reaches the platform as analog camera, then DVR or encoder, then RTSP. Everything downstream of the encoder is identical to the IP case. No special handling is required.

### 2.5 Private CCTV

The registry carries an `ownership` field, set to `government` or `private`. Public-facing private cameras, in housing societies, malls and commercial premises, are onboarded into a **view-only tier** with an explicit consent record attached. They are viewable and analysable where that is feasible and permitted, and they are never treated as government assets. The demonstrated system carries the ownership field; the consent record is part of the production design.

### 2.6 The guarantee to departments

Sentinel is consume-only. It pulls streams read-only. It never publishes to a gateway, never calls a control API, never downloads stored footage, and never writes to a departmental system. A department's VMS, its storage and its retention policy are unchanged by onboarding. The demonstrated system holds to this against the organisers' sandbox, and it can be checked against the source.

### 2.7 Two different systems in one viewer (the Model 2 deliverable)

- **System A: the organisers' sandbox.** All 30 catalogue cameras across five departments. Five are pulled live over RTSP from the organisers' gateway, one pull each, and analysed continuously (cam06, cam09, cam26, cam27 and cam28 in the measured run); they loop on the organisers' side and are never recorded or replayed locally. The other 25 are registered, health-monitored and viewable through the relay.
- **System B: a local camera server.** A mediamtx server on the laptop publishes 28 feeds (`local01` to `local28`) from stock traffic footage: sample clips, not sandbox footage and not filmed by the team. Each camera record says so in its location name and carries seeded coordinates. The clips loop, so on the platform database all 28 are view-only relay feeds: an analysed loop would store the same plates again on every pass as live reads. The live path was verified on four of them in separate runs on a test database (24 Sep: 21 sightings and 3 real watchlist alerts, one through the OCR-ambiguity fold), and the platform database keeps the reads of one earlier walkthrough on `local01`, disclosed as stock footage by the camera's name. Analysing a stock clip is a test-database activity; the team's own filmed footage, published once with its real gaps, is what takes an analysed slot.

Both systems appear side by side on the same map, Live Wall, search, alert stream and reports.

---

## 3. Ingesting geographically dispersed streams (Dimension 5, deployment)

### 3.1 Three tiers

| Tier | Runs | Responsibility |
|---|---|---|
| **Edge** (district or department) | Near the cameras | Stream pull, decode, motion gate, detection, tracking, OCR, **local watchlist match**, the Pipeline 3 ring buffer. Emits text and crops. |
| **Regional** | District cluster | Aggregation, regional search index, evidence store, model rollout, health scoring. |
| **Central** (SCRB or state data centre) | State | Statewide search, cross-region route correlation, watchlist master, dashboards, and integration with VAHAN, SARTHI, eGujCop, AFIS and NAFIS. |

Only text metadata and plate crops cross the WAN. A route query is answered centrally by joining sightings that arrived as metadata from every region.

**Which is which in the demonstration.** The demonstrated *node* is one worker process on one laptop: one thread per analysed camera, a supervisor that restarts a dead camera thread, and a single database writer. The API process on the same laptop plays the regional and central roles, and SQLite in WAL mode stands in for the regional and central stores. At statewide scale the node is an edge box (section 8.1) and the stores are the production services named in section 7.

### 3.2 Transport rules, validated against the sandbox

- **RTSP over TCP, always.** UDP fails across NAT and firewalls and delivers corrupt frames, which then look like model bugs and get debugged in the wrong place. Where RTSP is blocked, **HLS** is the fallback, and the transport used is recorded per camera in the registry. In the demonstrated system the HLS path is used **for viewing only**: analytics runs on RTSP pulls, and the harvest of the organisers' recordings for analytics was cut. WebRTC over WHEP is the low-latency control-room option where it is reachable; it is not built in the demo.
- **All timing from PTS**, never from frame arrival time and never from the reported frame rate. On connect, the gateway replays a buffered group of pictures, so the first frames arrive faster than real time. Anything timed by arrival computes impossible vehicle speeds.
- **Reconnect with jittered exponential backoff:** `base 2 s * 2^n * random(0.5, 1.5)`, capped at 30 s. Without the jitter, a regional event produces a synchronised reconnect storm (section 7.5). Every pull has a stall watchdog armed when the decoder process starts, so a connection that never delivers a frame is killed and retried rather than left hanging.
- **Decoder warnings on join are never fatal.** Mixed H.264 and H.265 feeds produce reference-frame warnings until the first keyframe arrives; they are logged and the pull continues.
- **Resets on restart.** The motion gate's background model, the tracker and zone state reset cleanly on every reconnect. On a live RTSP pull, the organisers' in-stream loop cut is not detected by content: measured on a live camera, ordinary traffic overlaps any frame-difference threshold, so a detector would fire on normal frames and break tracking. The cut heals itself, and occurs about twice per 12-hour loop [estimate].

These rules come from the sandbox's own pre-submission checklist. They are implemented in the node's ingest module (`ml/ingest/`) and tested against a local RTSP server and a live sandbox camera.

### 3.3 Pipeline 1 in practice: every camera on the Live Wall, relayed, not recorded

Every registered camera can be opened on the Live Wall. The browser cannot carry the organisers' CDN session cookie, so every tile plays through the API's relay, and each camera has exactly one upstream source:

| Camera | Upstream the relay serves | What touches disk |
|---|---|---|
| Analysed by the node (the five live sandbox cameras; sample feeds when analysed) | The node's own pull. Its decoder process stream-copies a local HLS window as it reads, so the wall shows exactly what the detector sees and viewing never opens a second connection to the camera | a self-overwriting 20-second relay window (ten 2-second segments) |
| Sandbox camera not analysed | The organisers' own HLS recording from their CDN, relayed segment by segment at the current position on the shared timeline, whenever the CDN is reachable (it rate-limits bursts). The live gateway is not touched | nothing: segments stream straight through |
| Sample feed not analysed | The local mediamtx server's own HLS output on 127.0.0.1 | nothing on disk: mediamtx keeps its short, self-overwriting window in memory by default |

Only the tiles on screen hold a stream, and closing a tile destroys its player. The relay proxies only segment names present in the playlist it fetched and only from the configured upstream origins, it is behind the login like everything else, and it is rate-limited. Relayed, not recorded — a self-overwriting 20-second relay window is the only video this system writes to disk.

### 3.4 How the demonstrated system is deployed

The demonstrated platform is one node, deployed the way a department-side node would be:

- **One laptop** (Ryzen 5 3550H, 8 GB RAM, GTX 1650 with 4 GB) runs two processes: the **API** (FastAPI and uvicorn, serving the built web interface, the relay, the alert stream and the reports) and the **node** (the worker described in section 3.1). SQLite in WAL mode is the only channel between them. The local mediamtx server publishes the sample feeds on 127.0.0.1.
- **Outbound-only publication.** To reach the screening committee, the laptop dials *out* to a tunnel relay (Tailscale Funnel). Nothing is opened inbound on the network the laptop sits on. **TLS terminates on the laptop**, with a certificate for its own name, so the relay forwards traffic it cannot read. Only the API port is published; mediamtx and the development server stay bound to 127.0.0.1.
- **Hardened for exposure.** With a public host name configured, the API switches on host-name checking, `Secure` session cookies and HSTS. Everything except the login page, `/api/health` and static assets requires a signed-in session (section 6).
- **The same shape as the department-side collector** of section 2.3: an agent inside a network with no inbound route, reaching the platform over an outbound connection.

A hosted URL and test credentials appear on the submission form only if the tunnel is live when the submission is made. The go-live procedure, the restart tasks and the daily check are in `docs/runbook-hosting.md`. If the sandbox is unreachable, the sample feeds keep the platform demonstrable.

---

## 4. Watchlist integration and real-time alerting (Dimension 3 in part, plus the alert workflow)

### 4.1 Matching at the edge against a cached watchlist

Matching happens at the edge against a locally cached copy of the watchlist. It is never a per-detection call to a central system.

The reason is arithmetic. At 80,000 cameras and one read per camera per minute, central matching would generate about **1,333 queries per second and 115 million per day** [model] against VAHAN and eGujCop. That load would take down the state's own systems of record. The watchlist itself is small, in the hundreds of thousands of records and tens of megabytes [estimate], so it can be synced out to every edge node every few minutes. Only confirmed matches call a central system, and then only to enrich the record, which turns 1,333 queries per second into a handful.

Edge matching also keeps working when the WAN or the central tier is down: edge nodes match against their cached list and queue the results. In the demonstrated system the node refreshes its cached list on every supervisor poll, and an entry past its expiry date never matches.

### 4.2 Plate forms and matching logic

Each read keeps three forms of the plate:

- `plate_raw`: exactly what OCR returned, never overwritten.
- `plate`: for a structurally full read, the **coerced structural form**. Where the Indian format expects a letter, `0/1/5/8/2/6` read as `O/I/S/B/Z/G`, and the reverse where it expects a digit. So an OCR read of `6J23H1548` is stored as `GJ23H1548` and `GJ1157924` as `GJ11S7924`, each with the OCR text kept beside it.
- `plate_canonical`: every ambiguity class folded to one form (`O/0, I/1, S/5, B/8, Z/2, G/6, Q/0`), indexed, and used for matching, dedupe and search.

A read is **full** when its coerced form matches the standard format (two-letter state code from a whitelist, two-digit district, one to three series letters, four digits) or the national BH series. Anything else is **partial**: stored with its confidence, shown on a route as a clearly labelled low-confidence candidate, and never alerted on or fuzzy-matched. A read that is full as it stands wins over one that is full only after coercion, so coercion salvages OCR confusions and never rewrites a clean truncated read into a different registration. Burned-in captions are rejected by the grammar and by an exclusion band across the top of the frame.

Matching returns one of three **match types**, in order:

1. **exact**: the same plate.
2. **ambiguity**: same length, differing only inside the ambiguity classes above.
3. **fuzzy**: both sides full, and a confusion-weighted edit distance of 1.0 or less, where a substitution inside an ambiguity class costs 0.25 and any other edit costs 1.0.

Alerts fire on **exact** and **ambiguity** matches. Fuzzy matches are shown and flagged, and alert only when a deployment setting enables it, which it does not by default: plain edit distance merges neighbouring registrations (`...1234` against `...1235`), and a false alert on a neighbour's car is worse than a missed fuzzy hit. Every alert records its match type and distance.

### 4.3 Alert workflow: prioritisation, visualisation, interaction

1. A detection produces a **sighting written to durable storage** before any alerting logic runs. In the node every database write goes through one writer thread, and a sighting is an awaited write.
2. The matcher runs against the cached watchlist. A **five-minute cooldown per plate per camera** stops one vehicle from flooding the operator's feed. The cooldown is derived from the last alert row in the database, never from process memory.
3. On a match, an **alert row is written, then broadcast**. Alerts are raised in the node process and shown by the API process, and the database is the only channel between them: **the API tails the `alerts` table**, one background reader polling every 2 seconds past a monotonic sequence number and pushing each new row to every open dashboard over Server-Sent Events. A reconnecting browser resumes from the last sequence it saw. This is the right design across processes, and it means a detection never exists only in the memory of a process that is about to crash. In production the same role is taken by a durable queue such as Kafka or NATS between the tiers.
4. The operator sees the alert within about 2 seconds of its row being written [estimate]: plate, **plate crop**, camera, department, timestamp, category, severity, match type and a provenance badge. The crop is what makes an alert worth acting on rather than worth ignoring. High-severity intrusion-zone events become alert rows on the same stream.
5. An operator with the evaluator or admin role acknowledges it; the acknowledgement is persisted and audited under their username, and one click leads to the vehicle's **route**.

### 4.4 Route reconstruction

`GET /api/plates/{plate}/route` returns the vehicle's ordered, timestamped movement: each stop with its camera, department, coordinates, timestamp, crop and provenance; elapsed time and implied speed between consecutive stops within the same clock (section 1.6); total distance and duration; the list of **departments crossed**; flagged fuzzy candidates; and any **coverage gaps**, shown rather than hidden.

Implied speed is a sanity check, not a claim about the vehicle. An implausible speed flags a stop as suspect instead of drawing a confident line between two points that may not be the same vehicle.

A route that crosses Police, GSRTC and Municipal cameras is direct evidence that systems belonging to different departments have been integrated into one platform. **In the demonstrated system, the multi-camera route shown for `GJ01AB1234` is a demonstration vehicle** injected through the real write path (sighting, match, alert) at three sandbox cameras in three departments, labelled `demo` on every screen and in every export. No real vehicle has been read on two sandbox cameras: the live cameras sit at different positions in the organisers' loop, and the harvest of their recordings was cut. A real multi-camera route needs footage of one vehicle at several places; the scored test on the hackathon day uses the organisers' own designated vehicle.

### 4.5 Search

The Search screen queries sightings by plate, camera, time range, minimum confidence, vehicle class and provenance, with crop thumbnails and a click-through to each vehicle's route. Plate search is **ANPR-tolerant**: it matches against the stored canonical form, so a query finds a plate however the OCR confused its ambiguous characters, and each result is labelled with its match type (exact, OCR-ambiguity or fuzzy) and distance. Demonstration plates are included and carry the `demo` badge. Every plate lookup is written to the audit trail (section 6).

---

## 5. Video analytics (Dimension 3)

### 5.1 ANPR, primary and demonstrated

The pipeline is a cascade, run in the node for each analysed camera:

1. A **motion gate** (OpenCV MOG2 background subtraction) skips inference on static frames.
2. **Vehicle and person detection** with YOLOX-S (Apache-2.0) on ONNX Runtime, on the GPU through DirectML on the laptop, with per-class non-maximum suppression.
3. A within-camera **tracker** (section 5.3) links detections into tracks.
4. The **vehicle crop**, never the full frame, is upscaled to about 400 px wide (at most four times) and contrast-equalised, because plates in wide overview footage are small, then read by **PaddleOCR** PP-OCRv5 mobile text detection and recognition (Apache-2.0). Each track has an OCR budget, and at most two crops are read per frame.
5. Each read passes the **structural plate grammar** (section 4.2), and a track's reads are combined by **consensus voting**, never by latching the first read.
6. The committed read is written as a **sighting**, deduplicated within 60 seconds per plate per camera, with its crop.

In the measured run (section 7.1) the plate-read rate was low. The sandbox cameras are wide overview units that put plates at 10 to 25 pixels [estimate], and every full read in the measured window came from one camera, cam06. Over the same afternoon the live sandbox produced 55 real plate reads with crops on cam06, at OCR confidences of 0.78 to 0.99. On that evidence the ANPR viability gate **passed**, with the decision to continue on the current cameras and not to tune models: every model is inference on pre-trained weights, and none is trained or fine-tuned.

### 5.2 Object and intrusion detection, demonstrated

The detector classifies person, bicycle, car, motorcycle, bus, truck, backpack and handbag, so the object and person detection named in Evaluation Area 5 come with ANPR at no extra cost. Object events are throttled to one per class per camera every 5 seconds of stream time, and per-class counts per camera appear on the Command dashboard and through the events API; the detection report lists every plate read with its vehicle class.

Intrusion detection uses zone polygons and crossing lines stored per camera in normalised coordinates from 0 to 1, so a zone survives a change of camera resolution; they are drawn and edited on the Zones screen. A tracked object's foot point must be inside a zone for two consecutive sampled frames before it fires, so one bad box cannot put a false intrusion on the dashboard, and a line crossing is measured against the last confirmed side. A zone or line event is written as a zone `event`, and a high-severity zone raises an alert on the same stream as watchlist alerts.

On 25 September a crossing line drawn across cam06's carriageway through the API fired **53 line-crossing events** on the live sandbox feed during the measured afternoon run, each stored with provenance `live` on the `rtsp-live` clock: the first zone event on a real feed.

### 5.3 Person and vehicle tracking

Track continuity within a camera uses a **greedy IoU and centre-distance tracker**. It matches detections on superclass, so a car-to-truck label flip keeps one track, and it takes velocity from PTS deltas rather than arrival times. At one to three sampled frames per second a fast vehicle can move past box overlap between samples, so unmatched pairs fall back to a centre-distance bound scaled by box size. Track ids are never reused, so zone state can never attach to the wrong object after a restart.

It is described as what it is: **an IoU tracker, not ByteTrack**. A BYTE-style association with a Kalman filter is the documented upgrade, adopted only once it shows a measured reduction in identity switches, and implemented from the published equations rather than from ByteTrack's reference code, whose Kalman filter comes from GPL-licensed code.

Cross-camera correlation for vehicles is done by plate identity, which is what produces the route. At statewide scale, appearance-based re-identification is the documented extension for vehicles whose plate cannot be read, under the same edge-first, metadata-only posture.

### 5.4 Facial recognition: approach and privacy controls (described, not built)

Facial recognition is described here because the problem statement requires it. It is not implemented and is not claimed to be.

The approach would be face detection at the edge, then embedding, then matching against a watchlist gallery of missing and wanted persons held centrally, with the same edge-cached posture as plate matching.

The privacy controls are not optional and are stated here as part of the design. Facial recognition runs only against a specific authorised gallery. No general-population face database is built. Every match is logged and auditable. Embeddings for non-matches are not retained. Use is governed by a documented authorisation and retention policy. The rule that video is kept only on cause applies more strictly to faces than to plates.

### 5.5 Licensing: a procurement decision at 80,000 cameras

The components linked into the application are Apache-2.0, MIT and BSD: FastAPI and uvicorn, React, Leaflet and hls.js, OpenCV, ONNX Runtime and YOLOX, PaddlePaddle and PaddleOCR, with SQLite in the public domain; mediamtx, which runs as a separate server, is MIT. The stack does not use Ultralytics YOLO, which is AGPL-3.0: linked into an application the State would own, that licence can pull the whole codebase under the AGPL. It does not use Elasticsearch or Redis under their post-2021 and post-2024 licences; OpenSearch and Valkey are the production substitutes.

**One GPL component is disclosed.** Video decoding and the relay window use **ffmpeg**, and the laptop runs BtbN's `win64-gpl` build. ffmpeg is never linked into the application: it is **a GPL binary invoked as a separate process**, reached only through one configuration function. That is the same distinction this document draws for AGPL services: a copyleft licence is hazardous in a library linked into the State's code, and generally acceptable in a separate program the system merely runs. The platform's running path only decodes and stream-copies, so production can equally use an LGPL build of ffmpeg; the GPL x264 encoder was used once, by a preparation tool that transcoded the demonstration's sample footage, and is not part of the platform.

The basemap tiles used by the demonstration are covered in section 2.2.

---

## 6. Cybersecurity architecture (Dimension 4)

### 6.1 Controls

| Control | Design, and what the demonstrated system has built |
|---|---|
| **Credential handling** | Camera credentials live only in the environment or a secret store. They are never hard-coded, logged, persisted or displayed unmasked, and no URL containing a credential is written to storage: the registry holds URL templates with placeholders, filled in memory. Production uses a secrets vault such as HashiCorp Vault, with per-department credentials and scheduled rotation. |
| **Login, sessions and RBAC** *(built)* | People sign in; nobody shares a key. Three roles: **viewer** (read only), **evaluator** (read, acknowledge alerts, add and remove watchlist entries, run reports, onboard a camera by form) and **admin** (everything, including users, bulk import and zones). Passwords exist only as scrypt hashes with a per-user salt, set by an administrator's command-line tool that prompts for them; never in configuration, the repository or a log. A login issues an opaque server-side session in an `HttpOnly`, `SameSite=Strict` cookie (`Secure` when published) that expires after 8 hours and is revoked on logout or password change. Five failed logins for one username or from one address lock further attempts for 15 minutes, and the lock survives a restart. API keys remain for scripts and tools. **Production** adds department scoping: a department sees its own cameras by default, and cross-department access is explicit and audited. |
| **Encryption** | TLS in transit on every hop the platform controls: API, inter-tier traffic and, where the source supports it, the stream pull. In the demonstration TLS terminates on the laptop (section 3.4); the sandbox gateway offers plain RTSP over TCP. Encryption at rest for the evidence store and the databases in production. |
| **Hardening** *(built)* | Nothing is reachable without signing in except the login page, `/api/health` and static assets. Every response carries a Content-Security-Policy, `nosniff`, frame denial and a no-referrer policy, with HSTS and host-name checking when published. Expensive reads (the route query, report exports, the relay) are rate-limited per session. The CSV import is size-limited and rejects bad input with a reason, not a stack trace. |
| **Network segmentation** | Edge nodes sit in department DMZs, central services in a segmented state data-centre network, with least-privilege firewall rules between tiers. Because Sentinel is consume-only, there is no inbound path from it into a departmental control plane. In the demonstration only the API port is published; the local camera server and the development server are bound to 127.0.0.1. |
| **Auditability** *(built)* | An append-only `audit` table names the **user** for every change: every onboarding, edit and import, every watchlist change, every acknowledgement, every zone edit, and every login success, failure, lock and logout (a failure row never contains the attempted password). Every **plate lookup, sightings search and route export** is audited too, because an operator looking up a plate without cause is the documented misuse pattern of ANPR systems. **Production** adds cross-department access records, and Pipeline 3 adds an evidence audit row carrying the event id, trigger reason and SHA-256 of each promoted clip. Chain of custody is a deliverable of the system, not a report produced afterwards. |
| **Credential-rotation resilience** | A per-camera health check shows a camera going dark, and production adds a per-department credential check with a documented escalation path. A department changing a password without telling anyone is an organisational problem that presents as a technical outage, and it is budgeted for. |

### 6.2 Data protection and retention

A plate read that can be linked to a vehicle's owner is personal data under the **Digital Personal Data Protection Act, 2023**. Processing for the prevention, detection or investigation of offences is exempted from much of the Act (section 17), and the exact scope of that exemption is a determination for the Department's legal advisers. Sentinel is designed as though the Act's core duties applied anyway, because that is what makes the system defensible:

- **Purpose limitation.** Reads exist to match a watchlist and reconstruct routes for authorised users; every lookup is attributable to a named user (section 6.1).
- **Storage limitation, by data class.** Retention is a configurable time-to-live per class, purged on a schedule: non-hit plate crops shortest, sighting text longer, and watchlist-hit evidence longest, held under a case reference until the case closes. Proposed defaults, to be set by the Department: non-hit crops 30 days, sighting rows 180 days, hit evidence for the life of the case [estimate]. The relay window (20 seconds) and the Pipeline 3 ring buffer (15 minutes) are fixed by construction, not by policy.
- **Departments' own retention is untouched.** Their recordings stay in their systems under their 7 to 15-day policies; Sentinel keeps metadata, not their video.
- **Security safeguards and breach readiness** follow section 6.1, with the audit trail as the record of who saw what.

The demonstrated system does not yet run the retention purge: its database holds sandbox reads, sample-feed reads and labelled demonstration rows only, and the purge is part of the pilot build.

---

## 7. Scaling to roughly 80,000 cameras (Dimensions 6 and 9)

> Every capacity figure in this section is a **[model]** from stated assumptions until it is replaced by measurement. The six figures measured on the demonstrated system are in section 7.1, and they are the only figures in this document labelled as measured.

### 7.1 What was measured on the demonstrated system

A formal 10-minute measurement window on 25 September 2026, 14:18 to 14:28 IST in daylight, after 10 minutes of warm-up. Five sandbox cameras were pulled live over RTSP and analysed (N = 5); all five were alive at the end, with zero restarts. The detector ran on the laptop's GTX 1650 through DirectML and OCR on the CPU. The evidence is committed as `data/measurements/20260925-084754Z.json` and `.md`.

| Figure | Value | Note |
|---|---|---|
| Sustained inference frames per second, per camera | cam06 0.67 · cam09 1.31 · cam26 0.6 · cam27 0.76 · cam28 1.47 [measured] | Below the configured 3 fps: the bottleneck was CPU OCR behind one shared lock, not the GPU |
| Vehicles per camera per minute (unique vehicle tracks) | cam06 15.6 · cam09 0.1 · cam26 0.0 · cam27 3.3 · cam28 0.5 [measured] | Raw detector boxes per minute were higher; tracks count each vehicle once |
| Peak GPU memory | 119 MiB [measured] | YOLOX-S under DirectML; Windows GPU counters place the allocation on the GTX 1650 |
| Peak RAM, both processes together | 1,749 MB [measured] | Separate peaks, at different moments: API 102 MB, worker 1,672 MB. Windows working set; the OS trimmed it in the final 25 seconds |
| Motion-skip rate (share of sampled frames skipped) | cam06 0.0 · cam09 0.245 · cam26 0.542 · cam27 0.026 · cam28 0.0 [measured] | Busy cameras skipped nothing; the quietest skipped just over half |
| Plate-read rate (full reads over vehicle tracks) | 0.062 overall (12 of 195); cam06 0.077, the other four 0.0 [measured] | Wide overview cameras; small and oblique plates |

**What these figures do and do not support.** They show that the whole pipeline runs on live government feeds within a small GPU budget, and where its limit lies on this hardware: OCR on the CPU, not detection. They are not a guide to streams per accelerator on a production node. The compute model below stays a model until the pilot (section 10, phase 1) measures a production node. The model's traffic assumption of one plate read per camera per minute is of the same order as the busiest measured camera, which produced about 1.2 full reads a minute (its vehicle rate times its read rate) [model]; section 7.2 shows what happens if every camera were much busier.

### 7.2 Why not centralise, and why not Model 4 — Central VMS & AI Platform

| Per-camera bitrate | Aggregate at 80,000 cameras [model] |
|---|---|
| 1 Mbps (720p) | **80 Gbps** |
| 3 Mbps (1080p) | **240 Gbps** |
| 8 Mbps (4K) | **640 Gbps** |

Sustaining 240 Gbps into one facility is mid-size-ISP backbone territory. It is a procurement and physical-plant problem before it is a budget line. Running analytics at the edge changes what has to cross the WAN at all. At one read per camera per minute, 1,333 reads a second statewide:

| What crosses the WAN | Volume [model] |
|---|---|
| Raw video, centralised | 240 Gbps |
| One full-frame JPEG (about 30 KB) per read | 320 Mbps, 3.46 TB/day |
| One vehicle crop (about 6 KB) per read | 64 Mbps, 0.69 TB/day |
| One plate crop (about 2 KB) per read | 21 Mbps, 0.23 TB/day |
| One text row (about 200 bytes) per read | 2.1 Mbps |
| **This design: text row plus plate crop** | **about 23 Mbps** |

That is a reduction of roughly 10,000 times in WAN load [model], and it is why Model 4, fully centralised, is not proposed for statewide use. The figure is sensitive to traffic: if every camera read sixteen plates a minute, about as many as the busiest measured camera's vehicles, the metadata would grow to about 370 Mbps [model], still roughly 650 times below raw video [model].

### 7.3 Compute, and the ceiling that is usually missed

| Optimisation level | Streams per GPU [model] | GPUs for 80,000 [model] |
|---|---|---|
| Naive: every frame, full-frame ANPR | 30 | 2,667 |
| 5 fps sampling | 50 | 1,600 |
| plus motion gating | 100 | 800 |
| plus cascade detector and INT8 | 150 | 533 |
| plus ROI cropping and tuning | 200 | **400** |

The gap between the naive and the tuned figure is 6.7 times, or about 2,270 GPUs [model]. Fleet size is a consequence of engineering choices rather than a fixed cost. The measured run adds one lesson: on the laptop the binding stage was OCR on the CPU, so a production node budgets OCR on the accelerator as well as detection.

**Decode usually binds before inference does.** Every stream has to be H.264 or H.265 decoded before any model sees it, and a GPU's hardware decode engines (NVDEC on NVIDIA accelerators) cap out at roughly 20 to 40 concurrent 1080p30 sessions [estimate]. This is the NVDEC ceiling:

| Decode sessions per GPU | GPUs for **decode alone** [model] |
|---|---|
| 20 | 4,000 |
| 30 | 2,667 |
| 40 | 2,000 |

If inference tuning reaches 200 streams per GPU but hardware decode caps at 30, the fleet is sized by decode at 2,667 GPUs and the tensor cores sit roughly 85% idle [model]; sizing on inference alone under-provisions the fleet by five to ten times [model]. Mitigations: decode only the frames that will be inferred, which is the largest single saving; prefer H.265 sources; use CPU decode for low-frame-rate streams; and provision against whichever ceiling actually binds, measured independently rather than assumed. Section 8.3 costs both cases.

### 7.4 Storage: hot, warm and cold, and the class that gets forgotten

| Data | Volume [model] | Tiering |
|---|---|---|
| Evidence clips (Pipeline 3) at 10,000 hits per day | 220 GB/day | Warm, then cold archive. Promoted clips are replicated to a second region; at roughly 22 MB each [model] this is cheap. |
| **Detection snapshots**, if stored as full frames | **3.46 TB/day** | Store plate crops of about 2 KB instead of full frames of about 30 KB: a 15-fold reduction, to 0.23 TB/day. Full frames only for confirmed hits. |
| Sighting records | 115 million a day, about 42 billion a year, about 21 TB a year indexed | Hot for 7 days, warm for 90, then cold or frozen. Decide the shard and tier strategy on day one; retrofitting it after the index is built is a migration with no good window. |

Retention honours each department's own policy for its video, which varies from 7 days to more than 15, and the platform's own retention by data class (section 6.2). The platform deliberately keeps metadata for longer than it keeps video.

### 7.5 Availability, high availability and disaster recovery

- **Reconnect storms.** Jittered backoff, per-edge connection admission control using a token bucket, staggered cold start, and a circuit breaker per department. A regional power event must not let 80,000 recovering clients take down departmental NVRs with group-of-pictures replay bursts.
- **Split-brain camera ownership.** Distributed leases held in etcd or Consul. A node holds a renewable, time-bounded lease per camera, so there are never two owners, never double pulls and never duplicate alerts.
- **The alert path is the real single point of failure.** Detections are persisted before any alerting logic runs, so if alerting is down, events queue and replay; the demonstrated system already persists before it alerts and broadcasts from the table. End-to-end synthetic testing injects a known plate on a schedule and alarms if no alert comes back.
- **Evidence-loss window.** Waiting 30 seconds after the event to close a promoted clip means a recovery point objective of about 30 seconds on node failure [model]. This is mitigated by writing the pre-event portion immediately and by replicating promoted clips across regions. The RPO is stated rather than left implicit.
- **Loss of a regional data centre.** Cross-region replication for the search index and the databases. Edge nodes keep detecting and buffer their metadata for the duration of the outage.
- **Backup, which replication is not.** Replication copies a bad write or a deletion to every replica within seconds. The registry, the watchlist, the audit log and the sighting databases are therefore also backed up as consistent point-in-time snapshots, kept off-site in the second region under the retention in section 6.2, and a restore is rehearsed on a schedule, because a backup that has never been restored is an assumption.

### 7.6 Day-2 operations

At a 2% failure rate, about 1,600 cameras are broken at any given moment, permanently [model]. There is no all-green state to aim for, so the system has to rank faults rather than report them.

What this requires is a continuously computed quality score per camera covering no signal, frozen frame, too dark or blown out, out of focus, lens obstruction, **camera drift or rotation** detected by comparing a periodic scene hash against a reference, and clock skew. The output is a ranked maintenance worklist, not a dashboard. The demonstrated system's health checker already separates "no traffic" from "feed down" from "pipeline dead" on its feed-status strip, judging analysed cameras by the freshness of their own pull and never by probing the CDN.

Camera drift is the one that does damage quietly. A camera nudged 15 degrees over several months still produces good-looking video while its ROI and calibration are silently wrong, and nothing alarms.

**Model rollout** across roughly 1,600 edge nodes [model] goes shadow, then canary at 1%, 10%, 50% and 100%, with automatic rollback on regression. **Configuration** is declarative and version-controlled through GitOps, because configuration drift across 1,600 nodes cannot be unwound once it starts.

### 7.7 Monitoring, logging, health and load balancing

Central observability for metrics, logs and traces at each tier. Health checks per camera and per node; in the demonstrated system every process writes a rotating log file and the node publishes its per-camera statistics every 10 seconds. Horizontal scaling of stateless workers behind the registry. Dynamic assignment of streams to GPUs, which consolidates load in quiet hours and allows idle GPUs to be powered down, and which is also what makes lease mobility in section 7.5 possible.

---

## 8. Cost and benefit analysis (Dimension 7)

Every figure in this section is **[model]**: arithmetic on indicative market prices and the sizing of section 7, to be replaced by vendor quotations and pilot measurements before procurement. Every number in the tables below is [model]. Cameras are excluded, because departments already own them, and so are the departments' own VMS and storage, which Sentinel leaves untouched. Amounts are in Indian rupees; one crore is 100 lakh.

### 8.1 Bill of materials for one edge node

One node serves about 50 cameras [model], the "5 fps sampling" level of section 7.3.

| Item | Specification | ₹ lakh [model] |
|---|---|---|
| Server | 2U, one 16-core CPU, 64 GB RAM, redundant power supplies, 3-year on-site warranty | 4.5 |
| Accelerator | One data-centre inference GPU, 24 GB, under 75 W, with hardware video decode | 3.0 |
| Local storage | 2 × 1.92 TB NVMe, mirrored: the operating system, the Pipeline 3 ring buffer (50 cameras × 15 minutes × 3 Mbps, about 17 GB) and a 72-hour metadata queue for WAN outages (about 0.5 GB) | 0.6 |
| Network and security | Share of a 10 GbE switch and a site firewall | 0.8 |
| Power | Share of an online UPS and a rack | 0.6 |
| Installation and commissioning | | 0.5 |
| **Per node** | | **10.0** |

That is about ₹20,000 per camera [model] at the edge, and a draw of about 0.4 kW per node [model].

### 8.2 Pilot: one district (roadmap phase 1)

About 200 cameras of one department in one district [model], four edge nodes and a small central stack, run for 12 months.

| Implementation (one-time) | Basis | ₹ lakh [model] |
|---|---|---|
| Edge nodes | 4 × ₹10 lakh | 40 |
| Central pilot stack | 2 servers in a high-availability pair (API, PostgreSQL with PostGIS, search), ₹6 lakh each | 12 |
| Evidence and metadata storage | 20 TB usable, replicated | 5 |
| Operator workstations | 2 × ₹1.5 lakh; existing control-room displays reused | 3 |
| Implementation services | Integration, one department adapter or collector, onboarding and training: 5 engineers × 6 months × ₹1.5 lakh per person-month | 45 |
| **Pilot implementation** | | **105 (₹1.05 crore)** |

| Operation (per year) | Basis | ₹ lakh [model] |
|---|---|---|
| Power | 6 servers × 0.4 kW × 8,760 h × ₹8 per kWh | 1.7 |
| Annual maintenance | 10% of the ₹60 lakh of hardware | 6.0 |
| Operations and support | 2 engineers × ₹12 lakh | 24.0 |
| Connectivity | Links to the central pilot stack, metadata only | 3.0 |
| **Pilot operation** | | **34.7 a year** |

### 8.3 Statewide: about 80,000 cameras

| Implementation (one-time) | Basis | ₹ crore [model] |
|---|---|---|
| Edge nodes | 1,600 nodes × ₹10 lakh, at 50 cameras per node; one accelerator each, the 1,600-GPU fleet of section 7.3 | 160.0 |
| Regional tier | 10 clusters × ₹1.5 crore: regional search index, evidence store, model rollout | 15.0 |
| Central tier and disaster recovery | 2 sites × ₹8 crore: search cluster, PostgreSQL with PostGIS, a durable queue, object storage for clips, crops and indexes, replicated | 16.0 |
| Control rooms | 35 × ₹10 lakh (one per district plus the state room, rounded up; existing video walls reused) | 3.5 |
| Implementation services | Onboarding 80,000 cameras at ₹2,000 each (16.0); adapters and department-side collectors, 26 departments × ₹50 lakh (13.0); programme management, security audit and training (10.0) | 39.0 |
| **Statewide implementation** | about ₹29,000 per camera | **233.5** |

If hardware decode binds at 30 streams per accelerator (section 7.3), the edge line becomes 2,667 nodes, ₹266.7 crore, and the implementation total ₹340.2 crore [model]. The pilot measures which case applies before the fleet is bought.

| Operation (per year) | Basis | ₹ crore [model] |
|---|---|---|
| Edge power | 1,600 nodes × 0.4 kW × 8,760 h × ₹8 per kWh | 4.5 |
| Central and regional power, with cooling | About 100 servers × 0.5 kW × a cooling factor of 1.6, 8,760 h × ₹8 per kWh | 0.6 |
| Annual maintenance | 10% of the ₹194.5 crore of hardware | 19.5 |
| Operations | 60 staff (a 24×7 state operations centre and field engineers) × ₹12 lakh | 7.2 |
| Connectivity | Inter-tier links and disaster-recovery replication; camera links are the departments' existing networks | 1.0 |
| Software licences | Open-source stack | 0.0 |
| **Statewide operation** | about ₹4,100 per camera a year | **32.8 a year** |

Over three years the statewide cost of ownership is about ₹332 crore [model], or about ₹41,500 per camera [model]. The edge line scales with the number of cameras under continuous analysis, not the number registered: if only road-facing cameras run ANPR, it shrinks in proportion, exactly as the demonstrated system's tiering already works.

### 8.4 Where the design saves money

- **Bandwidth.** Edge processing turns a 240 Gbps centralised backbone requirement [model] into about 23 Mbps of metadata [model]. That is the difference between a network the State cannot buy and one it already has.
- **Compute.** The 6.7-fold tuning gap [model] is about 2,270 GPUs [model] of avoidable spend, about ₹68 crore of accelerators alone at ₹3 lakh each [model]. The decode ceiling means that sizing on inference alone under-provisions the fleet by five to ten times [model]; provision against the binding ceiling.
- **Storage.** Storing plate crops instead of frames is a 15-fold reduction [model] on the largest data class, from 3.46 TB/day [model] to 0.23 TB/day [model].
- **Licensing.** A licence at ₹500 per camera per year [model] is ₹4 crore a year [model] at 80,000 cameras, about ₹12 crore over three years [model]. The open-source stack removes per-camera licensing altogether, so the hackathon's open-source requirement is also the cheapest option available.
- **Cloud egress.** Even after optimisation, snapshots leaving a public cloud (0.69 TB/day of vehicle crops [model], or 0.23 TB/day of plate crops [model]) are a recurring egress bill with no end date. The recommendation is on-premise deployment in a state data centre, and the arithmetic is shown so the choice can be checked.
- **Idle GPU time.** Consolidating streams onto fewer GPUs overnight avoids paying peak rates around the clock on a 1,600-GPU fleet [model].
- **Operational benefit.** Tracing a vehicle today means a request to each department in turn. With Sentinel it is one query against one index, answered with timestamps, locations, crops and the departments crossed, and every lookup is attributable to a named officer.

---

## 9. Information required from each department (Dimension 8)

Assessing integration feasibility needs a structured set of information from each participating department. This questionnaire is a submission artefact in its own right.

| # | Item | Why it is needed |
|---|---|---|
| 1 | Camera inventory: count, make and model, analog or IP, resolution, codec | Sizes ingest and decode, and selects the connector type |
| 2 | VMS or NVR platform, vendor, version, AMC status | Determines adapter versus direct pull versus collector |
| 3 | Feed-sharing capability: RTSP, ONVIF, vendor SDK, API, or none | Picks the rung on the connector ladder (section 2.3) |
| 4 | Network topology: public IP, NAT, private WAN, or air-gapped | Determines reachability and whether a department-side collector is needed |
| 5 | Storage: local or cloud, and retention period in days | Sets the retention policy honoured for that department and sizes evidence tiering |
| 6 | Camera geolocation, and bearing, field of view and range where known | Populates the GIS registry, the coverage sectors and the route geography |
| 7 | Credentials, a named technical contact, and the change process | Credential rotation is the most common cause of silent camera loss (section 6) |
| 8 | Bandwidth available at each site | Determines whether processing sits at the edge or the regional tier |
| 9 | Legal and consent status for any private cameras | Governs the view-only private tier (section 2.5) |
| 10 | Existing integrations already in use, such as VAHAN or eGujCop | Avoids duplicate integration work and informs enrichment |

---

## 10. Roadmap (Dimension 10)

| Phase | Scope | What it proves |
|---|---|---|
| **0, Sandbox (now)** | The organisers' 30 cameras across 5 departments plus 28 local sample feeds, one node | Registry with GIS, live viewing of every camera, ANPR, watchlist, alerts, search and route all working against real feeds; six figures measured |
| **1, Pilot district** | One district, one department's real cameras, four edge nodes plus central (section 8.2) | Real-world integration, day-2 health, measured streams per accelerator, detection rate and read rate on production hardware, the retention purge, and Pipeline 3 built on the validated design |
| **2, Multi-district** | 3 to 5 districts, 3 to 5 departments, regional tier introduced | Model 3 adapters and the department-side collector, cross-region route correlation, the model rollout pipeline |
| **3, Statewide** | Towards 80,000 cameras across all 26 departments | Full edge, regional and central fleet; HA and DR; GitOps configuration; dynamic GPU consolidation; VAHAN, SARTHI, eGujCop, AFIS and NAFIS enrichment |

Facial recognition, appearance-based cross-camera re-identification and predictive analytics are roadmap items. Each is introduced only after the ANPR, route and watchlist core is proven at the preceding scale, and each under the same rules: process at the edge, keep metadata rather than video, and measure before claiming.

---

## Appendix A: the 30 versus 50 camera discrepancy

The public problem statement refers to about 50 cameras. The catalogue available after login lists `cam01` through `cam30`. The system is built against the catalogue, which the organisers describe as the contract. The discrepancy is recorded here rather than resolved silently in either direction.

## Appendix B: what this system does not do

- **No Pipeline 3 in the demonstrated system.** Event-triggered evidence capture is **designed and validated separately** (`docs/reference/model-02-1-event-triggered-evidence.md`: a stream-copied ring buffer, a promote step on a watchlist hit, a hashed clip and an audit row, exercised end to end on a separate RTSP rig) and **not built in the demo**. No alert in the demonstrated system links a clip, and no video is kept beyond the 20-second relay window.
- **No arbitrary rewind and no central recording of all video.** Both the privacy posture and the 240 Gbps arithmetic rule it out. Video is captured on justified cause only.
- **No real cross-camera route on the sandbox feeds.** No real vehicle has been read on two sandbox cameras, and the harvest of the organisers' recordings was cut. The route demonstrated is a labelled demonstration vehicle, and the HLS path exists for viewing only.
- **No live facial recognition demonstration.** The approach and its privacy controls are described in section 5.4. It is not built and is not claimed as built.
- **No Model 3 federation demonstration.** The sandbox exposes bare stream endpoints. There are no departmental VMS platforms inside it to federate, so a federation demo would be demonstrating something that is not there. Model 3 is documented in section 2.3 as the integration path for real departments.
- **Not yet built, and part of the pilot:** department-scoped access control, the retention purge, WebRTC viewing, and an HLS source for analytics.

## Appendix C: demonstration data, disclosed

- **Sandbox camera geography.** The organisers' catalogue carries only an id and a name. Each sandbox camera's department, coordinates and tier were assigned for demonstration in a committed seed file (`data/camera_seed.csv`), and are disclosed as such.
- **Sample feeds.** `local01` to `local28` replay stock traffic footage through a local camera server. They are not sandbox footage and were not filmed by the team; their coordinates are seeded (`data/local_feeds.csv`), and each camera record says "sample footage, seeded coordinates". Reads from them are genuine outputs of the live pipeline and carry provenance `live`; the camera record says what the footage is.
- **The demonstration vehicle.** `GJ01AB1234`, its three-camera route, its alerts and its background plates are injected through the real write path and carry provenance `demo` on every screen and in every export. They can be removed by provenance alone.
- **The recording epoch.** The HLS recordings' timeline is anchored to a declared constant, labelled as such and never presented as a measurement.

Every performance, capacity and cost figure in this document carries a label (see "How to read the numbers"). A single invented measurement would make the rest of them worthless, so none of them are invented.
