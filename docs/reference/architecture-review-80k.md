# Architecture Review — Scaling to 80,000 Cameras

**Reviewed:** Model 1 + Model 2 + Model 2.1 (hybrid), as designed 9–10 Sep 2026
**Posture:** adversarial. Brutally honest, as requested.
**Caveat on my own numbers:** these are planning estimates from stated assumptions, not benchmarks. Where I say "measure this," I mean it — do not put my figures in the HLD as measurements.

---

## 0. The finding that outranks all the others

**You do not have an architecture yet. You have one validated component and a set of untested assumptions.**

| | Validated | Claimed |
|---|---|---|
| Cameras | **1** | 80,000 |
| Duration | 6 minutes | 24/7/365 |
| Network | localhost | statewide WAN, ~1,000 km |
| Failure modes exercised | none | all of them |

That is a **five-order-of-magnitude extrapolation from a single data point.** Model 2.1's ring buffer is genuinely proven — at one camera, on loopback, for six minutes. Everything else in the scaling story is currently arithmetic and hope.

This is not fatal, and for the hackathon it may not even be a problem: Step 4 scores a working demo on ~50 cameras plus a *credible written* scaling story. But if you present the current design as a production architecture, a Principal Architect on the jury will find the hole in about ninety seconds. **The defensible posture is: "here is what we measured, here is what we modelled, here is what we would measure next."** State the boundary yourself before someone else does.

**The highest-value next action is not more design. It is measuring streams-per-GPU on the real sandbox feeds.** Every capacity number below is a guess until that exists.

---

## 1. Ingestion & Network Bottlenecks

### 1.1 Centralising video is dead on arrival — and this is the strongest argument you have

| Per-camera bitrate | Aggregate at 80,000 cameras |
|---|---|
| 1 Mbps (720p, heavy compression) | **80 Gbps** |
| 3 Mbps (1080p typical) | **240 Gbps** |
| 8 Mbps (4K) | **640 Gbps** |

240 Gbps sustained is mid-size-ISP backbone territory. On a state government network this is not a budget problem, it is a *physics and procurement* problem.

**Edge processing is not an optimisation. It is the only thing that makes the problem tractable:**

| What crosses the WAN | Volume |
|---|---|
| Raw video (centralised) | 240 Gbps |
| Full-frame JPEG per detection | 320 Mbps / 3.46 TB per day |
| Vehicle crop per detection | 64 Mbps / 0.69 TB per day |
| Plate crop only | 21 Mbps / 0.23 TB per day |
| Text metadata only | **2.1 Mbps** |

*(assumption: one vehicle detection per camera per minute, statewide average — a figure you must replace with measurement)*

**Edge processing is a ~3,750× reduction in WAN load.** Put that number on a slide. It is the single most persuasive argument in the entire submission, and it simultaneously kills Model 4 as a statewide option.

### 1.2 HIGH RISK — Reconnect storms

Barely anyone designs for this and it takes down real systems.

| Event | Simultaneous reconnects |
|---|---|
| One edge node reboots | 500 |
| District WAN blip | 5,000 |
| Regional power event | up to 80,000 |

Two compounding failures:

1. **GOP replay burst.** The Resources page states the gateway replays its buffered group-of-pictures on connect. 500 simultaneous reconnects = 500 simultaneous bursts against departmental NVRs that were never sized for it. **You can take down a department's recorder purely by recovering.**
2. **Synchronised backoff.** Exponential backoff without jitter means every client waits the same 2s, 4s, 8s. They resynchronise and hammer in waves, forever. This is the classic thundering herd.

**Concrete fixes:**
- **Jittered backoff** — `sleep(base * 2^n * random(0.5, 1.5))`. One line. Non-negotiable.
- **Connection admission control** — a token bucket per edge node capping reconnects to N/second regardless of how many cameras want in.
- **Staggered cold start** — on node boot, ramp camera connections over 60–120s, never all at once.
- **Per-department circuit breaker** — if a department's endpoint fails repeatedly, back off *that department* as a unit rather than per camera.

### 1.3 Protocol choices — correct, with one gap

RTSP-over-TCP is right (UDP dies to NAT and government firewalls). WebRTC for the control room and HLS as fallback is right.

**The gap: you have no answer for departments that expose neither RTSP nor ONVIF** — Windows-only vendor SDKs, or systems behind NAT with no inbound route. At 26 departments, assume 3–6 fall into this category. That is potentially thousands of cameras your architecture silently cannot reach.

**Fix:** a **department-side collector** — a small agent deployed inside the department's network that speaks their SDK locally and pushes outbound to you. Outbound connections traverse NAT trivially. Name this in the HLD; it demonstrates you have thought past the happy path.

---

## 2. Compute & Inference Efficiency

### 2.1 The GPU fleet number

| Optimisation level | Streams/GPU | GPUs needed |
|---|---|---|
| Naive: every frame, full-frame ANPR | 30 | **2,667** |
| 5 fps sampling | 50 | 1,600 |
| + motion gating on quiet cameras | 100 | 800 |
| + cascade detector + INT8 quantisation | 150 | 533 |
| + ROI cropping, aggressive tuning | 200 | **400** |

**The gap between naive and tuned is 6.7× — roughly 2,200 GPUs.** This single table is the most valuable thing in your infrastructure-sizing section, because it shows sizing is a *consequence of engineering choices*, not a fixed cost.

### 2.2 HIGH RISK — You are probably sizing the wrong bottleneck

Everyone sizes for inference. **Decode usually binds first.**

Every stream must be H.264/H.265 decoded before any model sees it. GPUs have dedicated decode engines (NVDEC) with hard limits — roughly 20–40 concurrent 1080p30 sessions.

| Decode sessions/GPU | GPUs for **decode alone** |
|---|---|
| 20 | 4,000 |
| 30 | 2,667 |
| 40 | 2,000 |

**Read that against §2.1.** If tuning gets inference to 200 streams/GPU but NVDEC caps at 30, you need 2,667 GPUs and **your tensor cores sit 85% idle.** All that inference optimisation buys nothing.

**Mitigations:**
- **Decode at reduced rate.** You don't need 25 fps. Decode only the frames you'll infer on — this is the single biggest decode saving available.
- **Prefer H.265 sources** where the choice exists — fewer bits to decode.
- **Consider CPU decode for low-fps streams.** A many-core CPU decoding at 5 fps can be more cost-effective than burning NVDEC.
- **Measure both ceilings independently** and provision to whichever binds.

### 2.3 Where compute is being wasted

- **Running the model on empty frames.** On most cameras most of the time, nothing is happening. A background-subtraction motion check costs almost nothing on CPU and can skip 60–90% of inference on quiet cameras. **The cheapest inference is the one you don't run.**
- **Full-frame OCR.** Cascade properly: cheap vehicle detector → crop → plate detector on crop → OCR on plate crop only. Never OCR a full frame.
- **Processing sky and buildings.** Per-camera ROI masks. Ties directly into the Model 1 registry — ROI is camera metadata.
- **FP32 inference.** INT8 quantisation typically gives 2–3× throughput with marginal accuracy loss on plate reading. Validate the loss; don't assume it.
- **Uniform treatment of non-uniform cameras.** A highway camera and a village junction do not deserve the same frame rate. Tier them, and store the tier in the registry.

---

## 3. Day-2 Operations & Device Management

**This is where the project actually dies, and it is the section teams skip.**

### 3.1 At this scale, permanent partial failure is the steady state

At a 2% failure rate, **1,600 cameras are broken at any given moment — forever.** There is no state in which everything works. If your system has no automated concept of camera health, coverage rots silently and nobody notices until a case fails.

**Required: a continuously computed per-camera quality score:**

| Failure | Detection method |
|---|---|
| No signal | Connection state, `last_seen` |
| Frozen frame | Consecutive frame hashes identical |
| Too dark / blown out | Mean luminance outside band |
| Out of focus | Laplacian variance below threshold |
| Lens obstruction (web, dust, sticker) | Static high-edge region persisting across scene changes |
| **Camera drift/rotation** | Periodic scene hash vs stored reference image |
| Wrong time | Clock skew vs NTP |

**Camera drift is the insidious one.** A camera nudged 15° over six months keeps producing perfectly good-looking video while your ROI mask, calibration and lane assignment are all silently wrong. Nothing alarms. Detection quality just quietly degrades. Catch it with a reference-image comparison on a schedule.

Output must be a **ranked maintenance worklist**, not a dashboard nobody reads.

### 3.2 Model rollout across ~1,600 edge nodes

You cannot push a new ANPR model everywhere at once. One bad model = statewide blindness.

**Required pipeline:** shadow mode (new model runs alongside old, outputs compared, nothing acted on) → canary 1% → 10% → 50% → 100%, with **automatic rollback** on accuracy or latency regression. You need a held-out labelled set per region to measure against — plate styles and lighting differ across Gujarat.

### 3.3 Configuration at 80,000 units

80,000 camera configs — ROI, thresholds, fps tier, schedules. **These must be declarative and version-controlled (GitOps), never hand-edited.** Config drift across 1,600 nodes is unrecoverable once it starts.

### 3.4 The unglamorous killer

**Credential rotation across 26 departments.** A department changes a password and doesn't tell you. Cameras drop silently. Multiply by 26 organisations with independent IT policies and no shared change process. Budget for a credential health check and a documented escalation path per department — this is an organisational problem wearing a technical costume.

---

## 4. Failover & High Availability

### 4.1 HIGH RISK — Model 2.1's ring buffer is a data-loss window

The buffer lives on edge-local disk. **Edge node dies → buffer dies.** Any detection whose clip hadn't been promoted yet is unrecoverable.

Worse: the promote step *deliberately waits ~30 seconds* for post-event footage. **That wait is a 30-second window in which node failure destroys evidence for a confirmed watchlist hit** — precisely the moments that matter most.

**Mitigations:**
- Write the **pre-event** portion to the evidence store immediately on detection; append post-event when it arrives. Halves the exposure.
- **Replicate promoted clips to a second region synchronously.** They're 22 MB; this is cheap.
- Accept buffer loss as designed behaviour — it's transient by construction — but **state the RPO explicitly** in the HLD. Being honest about a 30-second RPO is far stronger than pretending there isn't one.

### 4.2 Split-brain camera ownership

If node A and node B both believe they own camera 12: double stream pulls (double load on the department), duplicate detections, duplicate alerts, duplicate clips. Operators lose trust in the alert feed fast.

**Fix:** distributed leases (etcd/Consul). A node holds a time-bounded lease per camera and must renew. Lease expiry → another node may claim it. Never allow two owners.

### 4.3 The alert path is the real single point of failure

Video ingestion can degrade gracefully. **The alert path cannot.** If the alerting service is down when the stolen vehicle passes, the entire system has failed at its one job — and worse, it will look healthy on every dashboard.

**Fix:** detections go to a **durable queue (Kafka) before** any alerting logic. If alerting is down, events queue and replay. Never let a detection exist only in the memory of the service that's about to crash. Add explicit end-to-end synthetic testing: inject a known plate, assert an alert arrives, alarm if not.

### 4.4 Regional DC loss

Cross-region replication for Elasticsearch and Postgres. But answer the harder operational question in the HLD: **during a regional outage, do edge nodes keep detecting and buffer their events, or stop?** They should keep detecting — see §4.5.

### 4.5 HIGH RISK — Watchlist dependency

Covered fully in §5.3 because it is simultaneously an availability and a cost problem. Short version: **if matching requires a live call to VAHAN/eGujCop, then those systems become a hard dependency for every detection in the state.** They are legacy government systems. They will be down sometimes.

---

## 5. Hidden Cost Drivers

### 5.1 The thing you optimised is 150× smaller than the thing you didn't

This is the most uncomfortable finding in the review.

| | Per day |
|---|---|
| Evidence clips (Model 2.1) @ 10,000 hits | **220 GB** |
| **Detection snapshots** @ full-frame JPEG | **3,460 GB** |

We spent significant effort making evidence clips efficient — and the snapshot pipeline, which nobody has designed yet, is **fifteen times larger.**

**Fixes, in order of leverage:**
- **Store plate crops (~2 KB), not full frames (~30 KB).** 15× reduction, to 0.23 TB/day. Keep the full frame only for confirmed watchlist hits, where you have the clip anyway.
- Aggressive expiry: unmatched sighting snapshots expire in days, not years.
- Dedupe: the same parked vehicle detected 500 times overnight should not produce 500 snapshots. Per-plate-per-camera cooldown.

### 5.2 Sighting records — 42 billion per year

| | |
|---|---|
| Records/day | 115 million |
| Records/year | **42 billion** |
| Indexed size/year | ~21 TB before replication |

Elasticsearch at 42 B records/year needs a deliberate shard and tiering strategy from day one. Hot (7 days) → warm (90 days) → cold/frozen (archive). **Retro-fitting this after the index is built is a migration nobody wants to run.**

### 5.3 The self-inflicted DDoS

If watchlist matching is centralised:

> **1,333 queries/second against VAHAN/eGujCop, 24 hours a day = 115 million queries/day** against legacy government systems.

That is not an integration. That is an attack on your own source of truth, and those systems will fail under it.

**Fix — and this is an architectural decision, not a tuning knob: matching happens at the edge against a locally-cached watchlist.** Sync the watchlist out (it's small — hundreds of thousands of records, a few tens of MB) every few minutes. Only *confirmed matches* call the central system, for enrichment. That converts 1,333 QPS into a handful.

This also makes the system **resilient to central outage** — edge nodes keep matching against their cached list when the WAN is down.

### 5.4 Idle GPU cycles

Provision for peak, pay for peak 24/7. Traffic at 04:00 is a fraction of 18:00. On a 1,600-GPU fleet, idle capacity overnight is enormous waste.

**Fix:** dynamic stream-to-GPU assignment. Consolidate streams onto fewer GPUs during quiet hours and power down the rest. Requires stream ownership to be mobile — which you need anyway for §4.2.

### 5.5 Egress — the cloud trap

If any of this runs in public cloud, **egress fees will dominate the bill.** Even the optimised 64 Mbps of snapshots is ~0.69 TB/day leaving the cloud, every day, forever.

**Recommendation: argue explicitly for on-premise / state data centre**, and put the egress arithmetic in the cost-benefit section. It converts a cost risk into evidence that you did the analysis.

### 5.6 Per-camera licensing

If any VMS, SDK or ANPR engine in the stack carries per-camera licensing, **multiply it by 80,000 before choosing it.** A ₹500/camera/year licence is ₹4 crore annually. This alone justifies the open-source posture the hackathon already asks for — make that argument explicitly rather than leaving it implicit.

---

## 6. Highest-risk flaws, ranked

| # | Risk | Impact | Fix cost |
|---|---|---|---|
| 1 | **No capacity model grounded in measurement** | Every HLD number is invented and indefensible under questioning | Low — measure on sandbox |
| 2 | **NVDEC decode ceiling ignored** | GPU fleet undersized 5–8×; inference tuning wasted | Low — measure, then design around |
| 3 | **Centralised watchlist matching** | 1,333 QPS kills VAHAN; central outage blinds the state | Medium — cache at edge |
| 4 | **Snapshot storage undesigned** | 3.46 TB/day, 15× the clip volume we optimised | Low — store crops not frames |
| 5 | **Reconnect storms** | Recovery takes down departmental NVRs | Low — jitter + admission control |
| 6 | **Evidence loss window on node failure** | Lose clips for confirmed hits — the only ones that matter | Medium — early promote + replicate |
| 7 | **No camera health/drift detection** | Coverage silently rots; 1,600 cameras permanently dark | Medium — health scoring service |
| 8 | **Split-brain ownership** | Duplicate alerts destroy operator trust | Medium — distributed leases |

Note that **five of the top six are cheap to fix.** They are dangerous because they are unglamorous and easy to omit, not because they are hard.

---

## 7. What I would do next, in order

1. **Measure streams-per-GPU and decode sessions-per-GPU on real sandbox feeds.** Everything above is a guess until this exists. Half a day's work; converts the entire scaling section from assertion to evidence.
2. **Measure the actual detection rate per camera.** My "one per minute" assumption drives every storage and query number in this document. It could be off by 10× in either direction.
3. **Add jittered backoff and connection admission control.** One hour of work, removes a whole failure class.
4. **Move watchlist matching to the edge.** Architectural decision — make it now, before code depends on the other shape.
5. **Change snapshots to plate crops.** 15× storage reduction for a trivial change.
6. **Write the HLD scaling section around the two tables in §1.1 and §2.1.** They show the reader that sizing follows from engineering choices — which is precisely the maturity being graded.

---

## 8. What is genuinely strong here

Being adversarial doesn't mean being unbalanced. Three things hold up:

- **Model 2.1's evidence-capture design is sound and validated.** The ring buffer plus event-triggered promote is a real answer to a real problem, and the 0.54% CPU measurement is honest evidence, not a claim.
- **The edge-first instinct is correct**, and §1.1 now gives it a hard number — 3,750× — instead of an intuition.
- **The privacy posture is a genuine differentiator.** Retain nothing by default, promote only on justified cause, expire on schedule, audit every promotion. Most teams will present mass retention and never mention civil liberties. That gap is worth marks.

The architecture isn't wrong. It's **incomplete in exactly the places that only appear above about a thousand cameras** — which is precisely what a scaling section is for.

---

*Numbers computed 10 Sep 2026 from stated assumptions. Replace with measurements before submission.*
