# Progress — session handoff

Append a block after **every** task, in the format at the bottom. Record what was observed, not what was intended. Never delete an entry; supersede it with a later one. The top section is rewritten each session so the next session can start from it.

---

## Current state (20 Sep 2026, 17:30 IST)

- **Decision:** fresh, structured rebuild (`docs/decisions.md` F1). This repo holds the documentation and the carried-over deliverables; **no code has been written yet**. The previous build at `D:\projects\Sentinel_Repo` still runs as a demo and is the read-only reference.
- **Deadline:** 28 Sep 2026 (per Adi; confirm the milestone on the portal). Build window 20–24 Sep for application plus deliverables.
- **Next step:** write the plan — frontend, backend, API, ML, deliverables — into `docs/tasks.md`, settle the open decisions (`docs/decisions.md` §5), then execute in order.
- **Blockers:** none. Risks below.

## What exists in this repo

| Area | State |
|---|---|
| `CLAUDE.md`, `docs/*.md` | Written 20 Sep from the previous build's docs, with MUST content copied verbatim |
| `docs/reference/` | The design record (portal scrape, sandbox spec, 80k review, Model 2/2.1 specs, promote.py, glossary) and the previous build's own docs verbatim under `old-build/` |
| `deliverables/` | As submitted 15 Sep: HLD (md + pdf), deck (pptx + pdf + generator + images), workflow diagram (svg + pdf), `registry-api.json`, gap-analysis report, detection report (contains demo rows — regenerate) |
| `data/` | `cameras_raw.json` (the catalogue, 30 cameras), `probe_results.json` (laptop probe 14 Sep: RTSP 27/30), `camera_seed.csv` (disclosed departments, coordinates, 5-camera active tier) |
| `.env.example`, `LICENSE` (Apache-2.0), `.gitignore` | Carried over / written for the new layout |
| `backend/`, `frontend/`, `ml/` | Only their `CLAUDE.md` layer rules; empty otherwise |
| git | **Not yet initialised** — first action of the next session |

## What the previous build achieved *(verbatim, STATUS.md "SESSION SUMMARY (2026-09-14)")*

> Built & validated this session: P0 (probe/registry/GATE A), P1 (API+GIS+
> wall+gap report+OpenAPI), P2 (full ANPR pipeline — frame_source HLS/AES,
> motion, YOLOX, PaddleOCR+super-res, sightings), P3 (watchlist+matcher+SSE
> alerts), P4 (route+report), P6.3 (HLD). 21 API endpoints, all documented.
> Two named Model-1 deliverables + the detection report + the HLD are on
> disk. GATE B decision = best 3-4 cameras + low recall + a confirmed real
> hero vehicle (Adi). The ONE blocker to a full live demo is the laptop
> harvest (CDN rate-limits the cloud IP; laptop has GPU + no limit).

And on the laptop, 14 Sep 18:30Z *(verbatim, "FULL END-TO-END VERIFIED")*:

> Verified (browser, localhost:8000, all real HTTP):
>            - Live Wall: real RTSP video on all 4 tiles (cam06 daytime road,
>              cam10 evening road w/ van+auto, cam09/cam26 night) via the
>              RTSP->local-tee->relay->hls.js path. Grid 1/4/9 + paging.
>            - Command dashboard: 36 sightings, 34 plates, 4 alerts, live
>              alert cards w/ crops, latest plate reads w/ crops, mini-map.
>            - Route (THE scored view): type GJ01AB1234 -> 4 stops, 7.8 km,
>              12 min, departments GSRTC/Municipal/Police, numbered pins +
>              polyline + timeline w/ per-stop speeds and crops.
>            - Search: auto-loads recent reads on mount (was blank before the
>              fix); 36 rows w/ crops + per-row route click-through.
>            - Alerts: 4 severity-coded HIGH stolen_vehicle cards w/ crops,
>              ack + route buttons.
>            - Reports: detection CSV (clean columns) + HTML (200) +
>              per-camera object table from REAL live detections.

The route above is the **demo vehicle** (decision C10). What was never done: the 10-minute measurement run, a real multi-camera route, the two demo videos, live screenshots in the deck, and the deliverable corrections listed in `docs/architecture.md` Part C.

## Key measurements *(verbatim table from STATUS.md; blank rows are still blank)*

| Measurement | Value | Where measured |
|---|---|---|
| Cameras in catalogue | **30** (id + name only) | P0.2 |
| Cameras live | **14/30** (HLS) | P0.2 |
| RTSP reachable? | **No from cloud workspace** (raw-TCP egress blocked there; laptop untested — test in P2) | P0.2 |
| HLS reachable? | **Yes — 14/30 live**, session-cookie auth required | P0.2 |
| Codec mix | **h264 × 14** (no hevc among live) | P0.2 |
| Resolution mix | 1920×1080 ×4 · 1280×960 ×2 · 1280×720 ×1 · 960×576 ×1 · 854×480 ×5 · 640×480 ×1 | P0.2 |
| Mean bitrate (kbps) | partial: cam07 segment samples 362–745 kbps; full per-camera table pending re-measure after 403 cooldown | P0.2/measure |
| Declared-vs-measured fps mismatch count | partial: cam24 declared 12 → measured 5.61; cam07 declared 25 → measured 25.0 (150 frames / 6 s segment); rest pending | P0.2/measure |
| **Sustained inference fps per camera, N active** | | P2.7 |
| **Real detection rate (vehicles/camera/min)** | | P2.7 |
| Peak VRAM used | | P2.7 |
| Peak RAM used | | P2.7 |

Superseded by the laptop: RTSP **is** reachable from the laptop (27/30, `data/probe_results.json`); a 61-second stats snapshot from 18 Sep gives per-camera sustained fps 0.46–1.43 and detections/min 0–67.9 with 5 active (`docs/sandbox-findings.md` §8) — **not** a 10-minute measurement, so the four blank rows stay blank.

## Gate decisions *(verbatim, STATUS.md)*

| Gate | Decision | When | Rationale |
|---|---|---|---|
| A — transport | **HLS-only, with session-cookie auth.** All 14 live cameras carry `transport='hls'`; 16 unreachable carry `'none'`. Catalogue carries no department/coordinates → seed path taken: `data/camera_seed.csv` committed, DISCLOSED in submission. | 2026-09-13 ~14:30Z | RTSP (raw TCP :8554) unreachable from the cloud dev workspace; HLS is the guide's guaranteed-anywhere path. RTSP retest from the laptop queued for P2 — design does not depend on it. |
| B — ANPR viability | | | |
| C — route works | | | |
| D — documentation start | | | |

GATE A was later reversed on the laptop (RTSP primary, decision C6). GATE B's decision was recorded in the log but never in the table: *"best 3-4 cameras, accept low recall"* (Adi, 14 Sep). GATE C passed only with the demo vehicle. The fresh plan sets its own gates.

## Open risks

| Risk | Mitigation in the plan |
|---|---|
| Sandbox CDN or RTSP gateway goes away before the 28th | Record fallback footage of every component the moment it works; local replay of own footage for development |
| No real vehicle crosses two cameras | Demo vehicle through the real pipeline (labelled); harvest attempt on the CDN recordings when it is not rate-limiting |
| RTSP session cap (~6 suspected) | Active tier ≤ 6; wall served from the worker's tee, never a second pull |
| Documentation squeezed by code | Thursday 24 Sep is documents and videos; nothing else |
| Claims in the deliverables that the code does not back | `docs/architecture.md` Part C is the checklist; every `[measured]` needs the run |

---

## Log

```
## <task id> — <status: DONE | BLOCKED | CUT>
When:      <UTC timestamp>
Observed:  <what actually happened — numbers, errors, counts>
Surprise:  <anything that differed from the plan>
Next:      <task id>
```

```
## R0 — DONE (fresh repo created)
When:      2026-09-20T12:00Z
Observed:  New repo `D:\projects\sentinel-gujarat` written from the previous
           build: CLAUDE.md + 10 docs authored (MUST blocks verbatim), 8
           design-record files under docs/reference/, 18 old-build docs
           archived verbatim, data/ (catalogue, laptop probe, seed CSV),
           deliverables/ as submitted, .env.example, LICENSE, .gitignore.
           The previous DB held 46 sightings (32 demo, 14 real all on cam06),
           4 alerts (all demo), 553 events, 27 watchlist rows; no real plate
           on two cameras.
Surprise:  STATUS.md's last narrative says 6 active cameras; the committed
           seed, the last launch log and the DB say 5 (cam10 dropped). The
           seed is the truth. The exported registry-api.json still lists a
           snapshot.jpg endpoint the code no longer has.
Next:      git init + first commit + tag docs-v0; then write the plan into
           docs/tasks.md.
```
