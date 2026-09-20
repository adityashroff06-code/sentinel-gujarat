# Decisions — every choice carried over or still open, and why

**Editor's note (20 Sep 2026).** Sections 1–2 are decisions already made (carried over from the previous build with their evidence, or made on 20 Sep for the fresh build). Section 3 turns the previous build's review into design rules. Section 4 is the review's do-not-do list, verbatim. Section 5 lists what the plan (`docs/tasks.md`) still has to decide. Add a row here whenever a choice is made; never delete one — supersede it.

---

## 1. Carried over from the previous build

Each was validated on this laptop against the real sandbox. "Source" names the entry in `docs/reference/old-build/STATUS.md` or the document.

| # | Decision | Why | Source |
|---|---|---|---|
| C1 | **Hybrid architecture: Model 1 + Model 2 + Pipeline 3** (evidence capture), Model 3 federation and FRS *described* in the HLD, not built | Model 1 is mandatory; Model 2 is the sandbox's own shape; Pipeline 3's design is validated on a separate rig. No departmental VMS exists in the sandbox to federate; FRS carries privacy obligations | `docs/architecture.md` Part A; `docs/reference/model-2-1-architecture-spec.md` |
| C2 | **SQLite (WAL) for the demo; Postgres/PostGIS, Kafka/NATS, OpenSearch, Valkey only in the HLD** | 8 GB RAM shared with a browser and inference; SQLite carried 6 writers once the pragmas were right | `docs/constraints.md`; STABILITY FIX entry |
| C3 | **FastAPI + uvicorn**; the generated OpenAPI *is* the Model 1 API-documentation deliverable | Closes a named deliverable for free | P1.3 entry |
| C4 | **React 18 + Vite, Leaflet (BSD-2), hls.js (Apache-2.0)**; Leaflet CSS bundled, not loaded from a CDN | Venue may have no internet; pins and route still render without basemap tiles | GAP-CLOSURE PASS (14 Sep 10:30Z), item 5 |
| C5 | **YOLOX-S on ONNX Runtime (DirectML on the laptop), PaddleOCR PP-OCRv5_mobile det/rec, MOG2 motion gate** — all Apache-2.0; **never Ultralytics** | Licensing (procurement blocker) and measured speed: 46–55 ms/frame detector, 0.45 s/crop OCR | `docs/constraints.md`; gap-closure pass 2 |
| C6 | **RTSP over TCP is the primary transport on the laptop; the CDN HLS relay is the fallback and the harvest path**; transport recorded per camera in the registry | Laptop probe: RTSP 27/30, HLS 0/30; the inverse of the cloud | LAUNCHER RUN 1 entry; `data/probe_results.json` |
| C7 | **Pipeline 1 relays HLS through the backend**; for RTSP cameras the worker's ffmpeg tees a stream-copied local HLS window that the API serves, so the wall costs no extra pull | Browser cannot carry the CDN cookie; one pull per camera | P1 entry ("HLS RELAY validated"); LAUNCHER RUN 1 fix |
| C8 | **Department, coordinates and tier come from a committed seed file and are disclosed** as demonstration data | Catalogue is `{id, name}` only | P0.3 (GATE A) |
| C9 | **Tiered processing: 5–6 active cameras across all five departments in two geographic clusters (Junagadh, Bilimora)**; all others registered, viewable, health-monitored | 4 GB VRAM; suspected ~6 RTSP sessions per account; clusters give plausible multi-camera routes | P0.5; gap-closure pass 2 item 10; `data/camera_seed.csv` |
| C10 | **Demo vehicle injected through the real pipeline** (`record_sighting` + `match_sighting`, rows tagged and removable) as the guaranteed end-to-end walkthrough, alongside live reads | Live RTSP cameras sit at different loop positions, so no real vehicle crossed two live cameras; the CDN rate-limited the harvest | FULL END-TO-END VERIFIED entry (14 Sep 18:30Z) |
| C11 | **Watchlist seeded at every launch** (idempotent, 25 invented entries) before workers start; matcher cache refreshed every supervisor poll | The watchlist was empty on the first laptop run because seeding only ran inside the harvest flow | gap-closure pass 2, item 5 |
| C12 | **No `.exe`; a Python launcher (`launch.py`) with `.bat` wrappers** that fetches portable ffmpeg, creates the venv, pins deps, fetches weights, probes, seeds, starts API + workers detached with log files | PyInstaller-bundling Paddle + ONNX + OpenCV + ffmpeg is a multi-hour fragile build with no scoring value | LAUNCHERS entry |
| C13 | **Cut order when time runs short** (verbatim `PLAN.md`): 1 Pipeline 3 · 2 intrusion detection · 3 WHEP · 4 object-detection surfacing · 5 bulk-CSV import *screen* (keep the endpoint) · 6 fuzzy matching. **Never cut:** registry, GIS map, live wall, ANPR, sightings search, watchlist, alerts, route reconstruction, any submission document | The scored moment outranks everything | `docs/reference/old-build/PLAN.md` |
| C14 | **Health of active RTSP cameras is judged by local tee freshness, not by probing the CDN** | A CDN probe flipped 29/30 cameras offline and emptied the active set | gap-closure pass 2, item 7 |
| C15 | **Alert SSE in the API tails the alerts table** (2 s poll) rather than an in-process bus | Alerts fire in the worker process | gap-closure pass 2, item 6 |
| C16 | **Every number in the HLD labelled `[measured]` or `[model]`** | One caught fabrication discounts the whole submission | CLAUDE.md rule 8 |

## 2. Made on 20 September 2026 for the fresh build

| # | Decision | Why |
|---|---|---|
| F1 | **Fresh, structured rebuild in this repo; the previous repo is read-only reference.** Knowledge is carried over verbatim (this `docs/` set); code is rewritten to the corrected contract | Adi's call after the structure review: the old docs pointed at folders that did not exist, rules conflicted with the enhancement plan, and the contract had drifted from the code |
| F2 | **Layout: `backend/` (API, storage, alerting, route, reports), `ml/` (ingest, detection, OCR, tracking, zones — the worker process), `frontend/` (React)**, each with its own `CLAUDE.md`. Where the two Python layers share code (config, DB access, plate normalisation, the matcher), see open item O2 | Adi's template; matches the two-process shape |
| F3 | **Git from the first commit, a tag per milestone, a regression test for every bug fixed** | The review found three regressions of things that once worked; the old repo had no git and no tests |
| F4 | **Auth from day one**: `X-API-Key` + roles `viewer`/`admin`, crops behind auth, an append-only audit table | Review defect D2; the PRD's "no auth unless P1–P4 complete" is withdrawn |
| F5 | **No bulk download of the sandbox footage.** Test replay uses **Adi's own footage** (a phone clip of a road is enough) served by a local RTSP/HLS replay; real-feed testing stays on the live sandbox | CLAUDE.md rule 6 and the organisers' "don't plan around obtaining copies of the footage"; the review's Phase 0.1 conflicted with both |
| F6 | **Python 3.13.9 (the installed Anaconda), pinned requirements with hashes, checksum-pinned ffmpeg zip and model weights** | Validated wheels; review defect D14 |
| F7 | **Every timestamp carries its clock; every row carries provenance** (`live | harvest | demo`) — see `docs/api.md` B6 | Review defect D3 breaks the scored route |
| F8 | **The submitted deliverables are carried over as the base and corrected, not rewritten** — see `docs/architecture.md` Part C for the claim-by-claim list | Three of seven evaluation areas are documentation; the architecture is unchanged |
| F9 | **Second "system" for the Model 2 viewer requirement: a local camera (phone/webcam) published over RTSP and onboarded through the new camera form** | Model 2 requires feeds from at least two different systems; the sandbox is one system |
| F10 | **Pipeline 3 is built only after the route, alerts and both onboarding screens work**; until then it stays "described, validated separately" | Cut order C13; the deck already presents it that way honestly |

## 3. Design rules from the review of the previous build

The review (`docs/reference/old-build/P7-enhancements.md` §0) found 15 defects, each verified against code. The contract-level ones are already in `docs/api.md` Part B (B6–B14). The rest become build rules here, grouped by layer.

**Ingestion (ml/)**
- Any looping source resets its "last yielded PTS" on wrap or resync, and the wrap wait must not busy-loop the CDN (D1). Test across two simulated wraps on the local replay before trusting it.
- Every pull has a **stall watchdog**: no frame for N seconds → kill the ffmpeg child → existing jittered backoff (D9). Add `-rw_timeout` on RTSP.
- Motion gate, object-event throttle and trackers reset on `stream_restart` (D12).
- `roi_json` is wired end to end: mask detection and the motion gate per camera; the caption band becomes a per-camera exclusion zone (D12, A4).
- OCR uses **track-level consensus voting**, never a first-read latch; per-track OCR budget stays (D10, A1). The DirectML detector session is locked; CPU ONNX sessions are thread-safe and need no global lock.
- Tracker matches on vehicle superclass so car↔truck flips do not fragment tracks; per-class NMS in the detector (A3).
- Plate grammar covers BH-series and a state-code whitelist, in one module (D11, A2).

**Backend**
- Health checker probes first, writes after, in one short transaction — never a write transaction held across network probes (D9).
- Single writer thread with `BEGIN IMMEDIATE` for the worker's DB writes; `busy_timeout=30 s`, `synchronous=NORMAL` under WAL; event writes batched (C4 of the review).
- `stop()` kills only its own child processes (psutil process tree), never every `ffmpeg.exe` on the machine; WMIC is dead on Windows 11 24H2 (D9).
- Retention: configurable TTL purge per data class (sightings, non-hit crops shorter, watchlist-hit evidence longer under a case reference).

**Frontend**
- One `formatTs()` in IST via `Intl.DateTimeFormat`; no raw UTC slices (D13).
- Every fetch checks `r.ok`; failures are visible in a connection-status strip — never `.catch(() => {})` (D13).
- The severity map covers every value incl. `critical`; the alerts list is capped; OSM attribution is on (ODbL) (D13).
- Zone saves report the real result; zone edits reach the workers without a restart (D12, D13).

**Ops and integrity**
- Every process writes a rotating log file under `data/logs/`; the launcher polls the port and fails loudly (D9).
- Requirements pinned with environment markers (`onnxruntime-directml; sys_platform == "win32"`) and a hash-locked lockfile; SHA-256 pins for the ffmpeg zip and `yolox_s.onnx` (D14).
- No credential in process `argv` (D14).
- Claims match code; `[measured]` only after the measurement ran (D15).

**Measured verdicts to reuse, not re-derive** (all measured on this laptop, per the review §6): NVDEC decode works on the GTX 1650 (driver 512.78) with a ~6× decode-CPU cut per camera and ~129 MB VRAM per session, but costs ~200 MB system RAM per camera; batched YOLOX-S is 3.0× at batch 4 but DirectML needs `add_free_dimension_override_by_name('batch', 4)` or it crashes; **FP16 under DirectML is 1.5–1.8× slower** (refuted); `fast-plate-ocr` is 9.5 ms/crop on CPU but India is absent from its training regions (side-by-side gate mandatory); one OSRM `/table` call returns the 30×30 road matrix in 1.28 s with median circuity 1.19 and p90 1.92 (a flat 1.3 factor is refuted). Recipes: `docs/reference/old-build/P7-enhancements.md` Appendix.

## 4. Do-NOT-do list *(verbatim, P7-enhancements.md §9)*

- **FP16 under DirectML** — measured slower; production-HLD material only.
- **TypeScript migration of the UI** — high effort, zero user-visible value solo; generate types for the new data layer only.
- **Postgres/PostGIS port now** — SQLite + indexes + single-writer carries a 10–30 camera pilot comfortably; build only the seam.
- **Full Gujarati i18n now** — the actual operator pain is the UTC display bug (fixed in Phase 1); translate once a pilot commits.
- **YOLOX-Tiny** — capacity is no longer the constraint after C1/C2; the small-object accuracy cost lands exactly where ANPR hurts.
- **Copying ByteTrack's `kalman_filter.py` or using `open-image-models` YOLOv9 plate weights** — GPL lineage in a state-owned stack.
- **`leaflet.offline` pre-seeding of OSM tiles** — prohibited by the OSMF tile policy.
- **Training or fine-tuning any model** — standing rule; it is also why LPRNet-class (Chinese-plate) candidates are rejected.
- **Refactor-for-elegance of working modules; a test suite for its own sake** — the constitution's rules still hold.

## 5. Open — to be settled in the plan

| # | Question | Default if not decided | Notes |
|---|---|---|---|
| O1 | Confirm the stack (C2–C5) for the fresh build, or change any part of it | Keep — every piece is validated on this laptop | Any change must pass the licensing table in `docs/constraints.md` |
| O2 | Where shared Python code lives (config, DB layer, plate normalisation, matcher) — a `shared/` package, or `ml/` importing from `backend/` | `backend/` owns storage and contracts; `ml/` imports them as a package | Two processes, one codebase; decide before the first module |
| O3 | Time-base implementation (`docs/api.md` B6): one timeline module mapping wall ↔ recording position for HLS; RTSP stamped from pull start + PTS with `clock_source = rtsp-live` | As stated | Route refuses cross-domain speed math |
| O4 | Tracker: reimplement a BYTE-style Kalman tracker from equations/filterpy (MIT), or keep an IoU tracker and say so | IoU tracker, described truthfully; Kalman only if measured ID-switch reduction | Never copy ByteTrack's filter |
| O5 | Harvest strategy for a real multi-camera route (CDN permitting): which cameras, which daylight window, how many segments | Junagadh cluster first (cam06/09/10), daylight tail of the recording | Keep the demo vehicle as the guaranteed path |
| O6 | Pipeline 3 in or out for the 28th | Out until F10's preconditions are met | Design already validated |
| O7 | Hosted URL with test credentials for the judges (optional deliverable) | Not hosted; local demo only | Would need the API key story (F4) and a tunnel |
| O8 | Entry category (1 vs 2) and the exact 28 Sep milestone | Category 1 | Check the portal/registration |
| O9 | Which measurements to run on the 10-minute soak and when (post-thermal) | fps/camera, detections/min, peak VRAM/RAM, skip rate, plate-read rate — the HLD's blank rows | Instrument existed in the old worker (`worker_stats.json`) |
