# Architecture — the locked target design, and what the sandbox forces on it

**Editor's note (20 Sep 2026).** Part A is the previous build's `01-architecture.md`, **copied verbatim** — the design is locked (CLAUDE.md §4) and the fresh build implements the same three pipelines over the same registry. Its one stale pointer, `reference/claude_model-2-1-architecture-spec.md`, is now `docs/reference/model-2-1-architecture-spec.md`. Parts B and C are new: what the sandbox turned out to be and how that reshaped the design in practice, and where the previous implementation diverged from the description (the fresh build must not repeat the divergence, and the HLD must be corrected either way).

---

# Part A — The locked design *(verbatim)*

# 01 — Architecture (LOCKED — do not redesign)

Full background in `reference/claude_model-2-1-architecture-spec.md`. This file is the operative summary.

## One paragraph

One stream pull per camera feeds three concurrent pipelines. **Pipeline 1** relays live video to the control room and stores nothing. **Pipeline 2** runs AI analytics and stores only text metadata plus a small plate crop. **Pipeline 3** keeps a fixed-size rolling buffer of compressed video and promotes a ±30 s clip to permanent storage *only* when a watchlist match fires. Underneath all three sits the **Model 1 registry** — the mandatory camera inventory and GIS layer that tells every component which cameras exist, where they are, and how to reach them.

## Diagram

```
              ┌──────────────────────────────────────────┐
              │  MODEL 1 — CAMERA REGISTRY + GIS         │
              │  the control plane for everything below  │
              │  · id, department, location, geometry    │
              │  · stream URLs, codec, resolution        │
              │  · health, last_seen, fps_tier, ROI      │
              └────────────────┬─────────────────────────┘
                               │ tells workers what to connect to
                               ▼
CAMERA GRID ──── ONE pull per camera (HLS or RTSP/TCP) ────► INGEST WORKER
                                                                  │
        ┌─────────────────────────────────────────────────────────┼──────────────────────┐
        │                              │                                                 │
  PIPELINE 1                     PIPELINE 2                                        PIPELINE 3
  LIVE VIEW (relay)              AI ANALYTICS                                  EVIDENCE CAPTURE
        │                              │                                                 │
  hls.js in browser         sample @ fps_tier (PTS-driven)                ring buffer, HLS segments
  WHEP if reachable         motion gate → skip empty frames               fixed N, self-overwriting
  NOTHING SAVED             detect vehicle → crop → plate → OCR                          │
        │                   match vs LOCAL watchlist              ◄── promote(t±30s) on match only
        ▼                              │                                                 ▼
  CONTROL ROOM WALL          sighting row + plate crop (~2 KB)                 CLIP + SHA-256 + audit
  multi-camera grid                    │
                                       ▼
                          SEARCH + GIS ROUTE + ALERTS
                          "where has GJ01AB1234 been?"
```

## What is stored, and what is not

| Pipeline | Persists | Does not persist |
|---|---|---|
| 1 — Live view | nothing | all video passing through |
| 2 — Analytics | sighting rows (text) + plate crop (~2 KB) | frames, full-frame JPEGs |
| 3 — Evidence | promoted clip + audit row | the rolling buffer (self-overwriting) |

**The governing principle: watching is not the same as storing.** Video becomes permanent only where a specific, logged, auditable watchlist match justifies it. This is a civil-liberties position, not only an optimisation, and it maps onto the bonus criterion for privacy protection and auditability. State it in the deck.

## What we build vs what we describe

| | Built for the demo | Described in the HLD only |
|---|---|---|
| Registry + GIS | ✅ | scaling to 80,000 entries |
| Live viewing | ✅ | video-wall layouts at control-room scale |
| ANPR + sightings + search | ✅ | GPU fleet sizing, INT8, edge deployment |
| Watchlist + alerts | ✅ (local seed DB) | VAHAN / SARTHI / eGujCop / AFIS / NAFIS adapter design |
| Cross-camera route | ✅ | Re-ID at statewide scale |
| Object + intrusion detection | ✅ if P4 passes | — |
| Evidence clips (Pipeline 3) | only if time remains | the full design, already validated |
| **Model 3 federation layer** | ❌ not buildable | ✅ the path from sandbox to 26 heterogeneous departments |
| FRS | ❌ | approach + privacy controls (description is mandatory) |

## On Model 3

The sandbox exposes bare stream endpoints. There are no departmental VMS platforms in it to federate, so a Model 3 demo would be demonstrating something that is not there. Model 3 belongs in the HLD as the answer to **heterogeneity, not scale** — 26 departments running 26 different systems, which is true on day one of a real deployment rather than at some later camera count. It is the honest completion of the connector-sprawl weakness already documented as Model 2's structural flaw, with the department-side collector as the mitigation for departments exposing neither RTSP nor ONVIF.

Frame it that way in the deck. "We will federate later" reads as filler; "here is the weakness we named, and here is its structural fix" reads as engineering.

## Design invariants

1. One pull per camera. Fan out internally, never open a second connection to a source.
2. Watchlist matching is local, against a cached list.
3. All timing from PTS.
4. RTSP over TCP, or HLS. Never UDP.
5. Detections are persisted before any alerting logic runs.
6. The registry is the single source of truth, populated from the catalogue.

---

# Part B — What the sandbox forces on this design

Every point here is a measured fact from `docs/sandbox-findings.md`; this section only draws the architectural consequence.

## B1. Two transports with opposite characters

| | RTSP (`103.250.160.189:8554`, creds in URL) | HLS (`cctv.corp8.cloud`, cookie) |
|---|---|---|
| From the laptop | **works, 27/30**, live-paced, native resolution | times out or rate-limits; reachable only sometimes |
| From a cloud box | blocked (raw TCP egress) | works, 14/30 |
| Nature | a live stream — position is the gateway's, one second per second | a **12-hour AES-128 VOD recording** — position is ours to choose |
| Concurrency | suspected **~6 sessions per account** | rate limiter bans bursts for minutes |

**Consequence.** On the laptop, **RTSP is the primary transport for analytics** and the HLS relay is the fallback and the cross-camera harvest path. The registry records the transport per camera (`transport` column) and the worker must accept both. Design the ingest so that the active set never exceeds the RTSP cap and so that a flaky CDN can never empty the active set.

## B2. The browser cannot reach the CDN, so Pipeline 1 relays

hls.js cannot carry the CDN's session cookie cross-origin, and the CDN 403s non-browser agents. The previous build's live wall therefore played `/api/hls/{camera}/live.m3u8` served by the backend: a rewritten sliding-window playlist, the AES key proxied, segments proxied. For RTSP cameras, the **worker's own ffmpeg process tees a stream-copied local HLS window** (`data/hls/<cam>/`, 10 × 2 s, self-deleting) that the API serves when fresh — so the wall shows the exact pull the detector reads and there is still **one pull per camera**. Cameras without a worker fall back to the CDN relay.

This is the honest reading of "Pipeline 1 stores nothing": a self-overwriting 20-second window on disk, which is a relay buffer, not a recording. **The HLD must say this** (Part C).

## B3. One shared timeline, or the route is wrong

The recordings loop on a common ~12 h timeline (organisers' statement, confirmed by sampling). HLS reads are stamped by *recording position* (epoch + offset), RTSP reads by *pull start + PTS*, and the previous build ended up with sightings on **two incompatible clocks** — P7's defect D3, which breaks the scored route the moment transports mix. The fresh build designs the time base first: every sighting stores the stream time, the wall time and which clock produced them, and route reconstruction never computes speed across clocks (`docs/api.md` Part B).

## B4. Two processes, one database

Inference cannot live inside the API process (GPU session, threads, crashes), so the previous build ran an **API process** and a **worker process** (one thread per active camera plus a supervisor). Everything that crosses that boundary — sightings, alerts, zone events, worker stats — must go through durable storage, never an in-process bus. Alert SSE in the API **tails the alerts table**. The DirectML session and the OCR engine are shared across camera threads behind locks (`docs/sandbox-findings.md` §7).

## B5. Plates are small, cameras are overview PTZ units

Wide traffic-overview cameras put plates at 10–25 px even on close vehicles. The cascade that worked: motion gate → YOLOX-S vehicle detection → vehicle crop → **upscale (~400 px wide, ≤4×) + CLAHE** → PaddleOCR mobile det/rec on the crop → structural plate filter (Indian format, ambiguity-coerced) → dedupe. Skip boxes in the top ~5 % of the frame (burned-in caption). A read that is not structurally full (`docs/api.md` §6) is partial: stored, never alerted, never fuzzy-matched.

## B6. The cross-camera route needs a plan of its own

Live RTSP cameras sit at different loop positions, so **no real vehicle appeared on two live cameras** during the previous build. A genuine multi-camera route can only come from harvesting the CDN recordings across cameras on the shared timeline (CDN permitting). The demo must therefore have **two paths**: a demo vehicle injected through the real pipeline (labelled `demo` end to end), and a harvest attempt for a real one. Both are decisions in `docs/decisions.md`.

## B7. The process model the fresh build starts from

```
launch.py / task runner
 ├─ API process (FastAPI + uvicorn, :8000)
 │    serves /api/*, the HLS relay, alert SSE (tails the DB), reports, the built frontend
 │    background: health checker (never probes the CDN for RTSP cameras)
 └─ Worker process (one thread per active camera + supervisor)
      frame source (RTSP via ffmpeg pipe, or HLS segment reader) → motion gate → detector (shared, locked)
      → tracker → OCR (shared, locked, budgeted) → sighting (durable) → watchlist match (cached) → alert (durable)
      → object/zone events (best-effort) → local HLS tee for the wall → stats file
SQLite (WAL) is the only channel between the two.
```

The fresh build keeps this shape and fixes what the review found (`docs/decisions.md` §3): one time base, sequence-based alert ids, zone alerts written as `alerts` rows so one DB-tailing broadcaster serves both kinds, a stall watchdog on every pull, log files for every process, and auth on every endpoint (header, plus a cookie for the browser's `<img>`/hls.js/SSE requests).

---

# Part C — What the previous build built vs what its documents say

| Claim in `deliverables/HLD.md`, README or deck | What the code did | Fresh build / HLD correction |
|---|---|---|
| Within-camera tracking uses **ByteTrack** (MIT) | A greedy **IoU + centre tracker** (`src/anpr/track.py`), stated in STATUS as a "ByteTrack stand-in" | Either implement a BYTE-style tracker from the equations (never copy ByteTrack's `kalman_filter.py` — GPL lineage) or describe the IoU tracker truthfully |
| Live video is "never written to disk" | RTSP workers tee a self-deleting 10 × 2 s HLS window to `data/hls/<cam>/` for the wall | Describe it as a relay buffer with a fixed, self-overwriting size |
| The two anchor numbers (sustained fps/camera, detection rate) are `[measured]` | The 10-minute measurement run never happened; only a 61 s stats snapshot exists | Run the 10-minute measurement, then label; until then `[model]` |
| "Every watchlist change, every acknowledgement and every cross-department access is logged" | No audit table exists | Build the audit table (`docs/decisions.md`) or remove the claim |
| "A single-camera onboarding **form** and the equivalent API call" | API only; no form, no CSV upload screen, no watchlist screen | Build the screens — Model 1 requires onboarding to be *demonstrated* |
| Alert broadcast is an in-process queue over SSE | The bus is in-process in the *worker*; the API's SSE polls the alerts table every 2 s | Describe the DB tail (it is the right design across processes) |
| Pipeline 3 evidence clips linked from alerts | Schema columns exist (`clip_path`, `clip_sha256`), never populated | Either build it (design is validated, `docs/reference/model-02-1-event-triggered-evidence.md`) or keep it "described, not built" as the deck already says |
| README's architecture image `deliverables/Sentinel-Workflow-Integration-Diagram.png` | Only `.svg` and `.pdf` exist | Export the PNG or link the SVG |
| Deck slides 4, 6, 9, 10, 11 show "dev UI captures on the synthetic test scenario" | Never replaced with live screenshots | Replace before submission (`deliverables/deck/img/`, rebuild with `build_deck.js`) |
| Demo videos 1 and 2 | Never recorded | Record per `docs/demo-script.md` |
