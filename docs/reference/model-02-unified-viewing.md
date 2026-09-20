# Model 2 — Unified Viewing & Metadata Analytics

**Official subtitle:** *Centralised Viewing with Metadata-Based Analytics*
**Source:** Step 2, Problem Statement page, sentinel.gujarat.gov.in
**Status:** One of five reference models. Not mandatory (Model 1 is). Can be paired with Model 1 or absorbed into a hybrid.

---

## 1. The idea in one sentence

Build one screen that shows every department's cameras by plugging **directly** into each department's existing system — and instead of hoarding all that video, just take notes on what you saw.

---

## 2. The problem it solves

A central command centre wanting to view cameras from four departments today must open four separate applications, with four logins and four interfaces. The source's words: this *"increases operational complexity and reduces monitoring efficiency."*

Analogy: four separate TVs, one per streaming service. Model 2 builds one TV that tunes into all of them.

---

## 3. How it works — two independent pipelines

This is the part that is easy to misread. **Two things run simultaneously and they are separate.**

### Pipeline 1 — Live viewing (full video, passes through, nothing kept)

The operator opens the platform and sees a grid of real live feeds — full continuous video, not selected frames — from any cameras they choose to open. But that video is a **relay**: camera → your gateway → operator's screen → gone. It is never written to disk.

### Pipeline 2 — Analytics (runs on everything, keeps only text)

Independently, in the background, the AI watches **every** camera continuously — including the ones nobody has open on screen — reads number plates, and writes tiny records:

```
GJ01AB1234 | Camera 12 | Naroda Road | 2026-09-22 14:32:07
```

Those records persist forever and are instantly searchable. The video they came from does not persist.

### The governing principle

> **Watching is not the same as storing.**

A night guard sees everything on his monitor wall, all night. Nothing is recorded. But he keeps a notebook — *"2:32am, silver Swift, GJ01AB1234, north gate."* Six months later you can't watch that night, but you can search the notebook in seconds.

Model 2 is that guard: the notebook writes itself, it never blinks, and it watches 50 cameras at once.

This is why the source can promise ANPR metadata, event tagging, camera-wise indexing and searchable vehicle-movement records **"without centralised storage of all video feeds."**

### What operators actually get

| View | What they see | What is saved |
|---|---|---|
| Live grid | Full continuous video from any cameras they open | Nothing |
| Search / alerts | Plate sightings, timestamps, a route drawn on the map | Small text records, permanently |

**Design addition worth including:** save a small **snapshot** with each detection — the cropped plate plus one frame. A few KB per hit, not GB per hour. This frame is captured by *your* gateway from the passing stream at the moment of detection; you never request anything from the department. It is the difference between an alert an operator trusts and an alert an operator ignores.

---

## 4. The rule that defines Model 2

**Direct connection to each departmental system. No middleman.**

The platform talks straight to each departmental CCTV or VMS via RTSP, ONVIF, vendor SDKs, or whatever API is exposed — with, verbatim, *"no intermediate middleware or federation layer."*

Existing departmental VMS and storage **continue to operate independently and are not disturbed.**

Mental picture: 26 separate cables running from 26 departments into your control room. Model 3 replaces all of them with one junction box — that is the entire difference between the two models.

---

## 5. Required functional features

1. Feed aggregation through RTSP, ONVIF, or vendor APIs
2. ANPR-based metadata generation
3. Event tagging and camera-wise indexing
4. Searchable vehicle-movement records
5. Configurable video walls and multi-camera grid views
6. Alerts for tagged events and vehicles of interest

> Note the source's hedge: these analytics apply *"depending upon technical feasibility."* The organisers are acknowledging clean analytics won't be available off every feed.

---

## 6. Suggested technology stack

| Layer | Suggestion | What it's for |
|---|---|---|
| Streaming | WebRTC / HLS relay | **WebRTC** — near-instant, video-call latency, for live monitoring. **HLS** — a few seconds behind but works everywhere, including phones and locked-down government networks |
| Integration | ONVIF / RTSP libraries / vendor SDKs | **ONVIF** — a common language most cameras speak, avoiding a per-brand driver. **RTSP** — the "start sending video" protocol |
| AI / ML | ANPR, open-source or custom | The number-plate reader — the one genuinely mandatory analytic |
| Backend | Node.js or Python microservices | Independent services, so one failing camera handler doesn't take the system down |
| Messaging / Search | Kafka, Elasticsearch, PostgreSQL | **Kafka** — conveyor belt for thousands of plate-reads per second. **Elasticsearch** — finds a plate across millions of sightings in milliseconds. **PostgreSQL** — the durable record |

---

## 7. Expected deliverables

- Unified viewer connected to sample feeds from **at least two different systems** (heterogeneity is the point — two cameras off one box will not count)
- ANPR demonstration on live or recorded feeds
- Searchable metadata dashboard
- **Architecture note proving existing departmental systems remain unaffected** — the "we didn't break anything" evidence

---

## 8. Architecture flow (as diagrammed on the site)

```
Departmental VMS Platforms    →   RTSP / ONVIF / Vendor APIs   →   Unified Stream Gateway
(existing systems remain          (secure feed access layer)       (relay · transcode ·
 independent)                                                       session control)
                                                                            ↓
                                                            Analytics & Metadata
                                                            (ANPR · tagging · indexing · alerts)
                                                                            ↓
                                                            Unified Control-Room View
                                                            (multi-camera viewing and search)
```

---

## 9. Drawbacks — three families

### A. Consequences of not storing video

| Drawback | Why it hurts |
|---|---|
| **No rewind** | "Show me Camera 12 last Tuesday 3pm" has no answer. You must ask the department, and only if their 7–15 day retention hasn't overwritten it |
| **No retroactive analytics** | Add a new detector next month and it applies only going forward. Every analytic you didn't anticipate is permanently lost. Model 4 would just re-process the archive |
| **A miss is permanent** | Glare, dirty plate, bad angle, high speed → the sighting never existed. A hole in the route with no recovery path |
| **Weak evidentiary standing** | Your snapshot is a JPEG your own system made. Court wants the department's original with its own chain of custody |

### B. Consequences of connecting directly

| Drawback | Why it hurts |
|---|---|
| **Connector sprawl** | 26 departments → 26 connectors, eventually thousands. No abstraction layer. Every VMS upgrade, credential rotation or network change on their side breaks your integration. **This is the structural weakness Model 3 exists to solve** |
| **Coverage hostage to cooperation** | Departments that expose no RTSP/ONVIF, sit behind NAT, or offer only a proprietary Windows SDK simply don't join |
| **Wide security surface** | You hold live credentials into 26 government systems. Compromise your platform, compromise all of them |

### C. Consequences of pulling video continuously

| Drawback | Why it hurts |
|---|---|
| **You still move all the video** | To run ANPR everywhere you pull every stream, always, to wherever the GPUs are. No storage bill — a permanent bandwidth bill. **At 80,000 cameras this, not storage, is the wall** |
| **Every viewer costs another stream** | The Resources page: *"Each connected client receives its own copy of the stream."* Ten operators on Camera 12 = ten pulls off that department's NVR. You can degrade their infrastructure by being popular |

**Mitigations to name in the submission:** fan-out relay in the gateway (pull once, serve many — precisely why their diagram says *"relay · transcode · session control"*); edge processing near the camera so only metadata crosses the network.

---

## 10. Why this model matters for our submission

**The sandbox is a Model 2 environment.** The hackathon hands us RTSP endpoints directly — `rtsp://<host>:8554/stream/<id>` — with no departmental VMS in between. That is Model 2's exact connection pattern. Whatever we claim architecturally, the thing we actually build against the test feeds *is* a Model 2 integration.

**Model 2's headline feature is verbatim the scored test.** Its listed capability "searchable vehicle-movement records" is word-for-word what Step 4 grades: a plate handed over on the day, a route reconstructed across the camera network.

**Working hypothesis (not yet a decision):** Model 1 + Model 2 as the spine — the mandatory registry supplying camera identity and geography, Model 2 doing the watching and plate-reading, the GIS map drawing the route. Everything beyond that is bonus-mark territory.

**Naming these drawbacks is itself worth marks.** Section 9A and 9B are what separate a team that chose the easy model from a team that understood the trade-off and chose deliberately. The evaluation criteria explicitly reward "technical soundness, feasibility... and clarity" of the architecture.

---

*Compiled from the Step 2 dropdown for Model 2 on the official problem statement page, plus the streaming constraints published on the Resources page.*
