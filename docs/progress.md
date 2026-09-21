# Progress — session handoff

Append a block after **every** task, in the format at the bottom. Record what was observed, not what was intended. Never delete an entry; supersede it with a later one. The top section is rewritten each session so the next session can start from it.

---

## Current state (22 Sep 2026, 00:45 IST)

- **Decision:** fresh, structured rebuild (`docs/decisions.md` F1). This repo holds the documentation, the plan and the carried-over deliverables; **no code has been written yet**. The previous build at `D:\projects\Sentinel_Repo` still runs as a demo and is the read-only reference.
- **Plan:** `docs/tasks.md` v2.2 — 30 one-session tasks S0.2 → S6.3 with the protocol every Claude Code session follows, a calendar re-based to Mon 21 with gates A′/B/C/D, and a cut order. Two independent cold-start reviews (43 + 26 findings, R2) and a third review (7 findings, R3) have been applied. Open decisions O1–O7, O9, O11 are settled (F11–F38); O8 and O10 remain (Adi, in S0.3 and S3.4).
- **Deadline:** 28 Sep 2026 (per Adi; S0.3 confirms the milestone on the portal). Build window Mon 21 – Thu 24 for code, Fri 25 for deliverables (GATE D 09:00, code freeze at end of day), Sat 26 soak + rehearsal, Sun 27 submit, Mon 28 buffer. **Note:** it is now the small hours of Tue 22 and no S0.x/S1.x session has run yet — the calendar's Mon 21 column is a day behind; Adi decides whether to re-base it or absorb the slip.
- **Git:** the repo exists — `main`, initial commit `883b8fc` pushed to `https://github.com/adityashroff06-code/sentinel-gujarat`; everything written after it (plan v2.1/v2.2, `CLAUDE.md`, docs, `.claude/settings.json`) is the uncommitted documentation baseline until S0.2 (or Adi) commits it.
- **Next task:** **S0.2** (baseline commit, tag `docs-v0`, push), then S0.3–S0.5 (Adi creates `.env` before S0.4), then S1.1. Paste into Claude Code: `Run task S0.2 from docs/tasks.md, following its "How a session runs" protocol exactly. Start by reading CLAUDE.md and the "Current state" section of docs/progress.md.`
- **Blockers:** none.

## What exists in this repo

| Area | State |
|---|---|
| `CLAUDE.md`, `docs/*.md` | Written 20 Sep from the previous build's docs, with MUST content copied verbatim |
| `docs/reference/` | The design record (portal scrape, sandbox spec, 80k review, Model 2/2.1 specs, promote.py, glossary) and the previous build's own docs verbatim under `old-build/` |
| `deliverables/` | As submitted 15 Sep: HLD (md + pdf), deck (pptx + pdf + generator + images), workflow diagram (svg + pdf), `registry-api.json`, gap-analysis report, detection report (contains demo rows — regenerate) |
| `data/` | `cameras_raw.json` (the catalogue, 30 cameras), `probe_results.json` (laptop probe 14 Sep: RTSP 27/30), `camera_seed.csv` (disclosed departments, coordinates, 5-camera active tier) |
| `.env.example`, `LICENSE` (Apache-2.0), `.gitignore` | Carried over / written for the new layout |
| `backend/`, `frontend/`, `ml/` | Only their `CLAUDE.md` layer rules and package layouts; empty otherwise (layout decided: F12) |
| `scripts/claude-settings.json` → `.claude/settings.json` | Claude Code permissions for every session (F38): read the old repo without prompting, no edits there, `.env` unreadable, Bash timeouts 5 min / 60 min. Written to `scripts/` because the file bridge cannot write into `.claude/`; S0.2 (or Adi) moves it into place |
| git | Initialised 20 Sep; `main` with the initial commit `883b8fc` pushed to `origin` (GitHub `adityashroff06-code/sentinel-gujarat`). The plan revisions since are uncommitted until S0.2 commits the baseline and tags `docs-v0` |

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

GATE A was later reversed on the laptop (RTSP primary, decision C6). GATE B's decision was recorded in the log but never in the table: *"best 3-4 cameras, accept low recall"* (Adi, 14 Sep). GATE C passed only with the demo vehicle.

**Fresh-build gates** (`docs/tasks.md` calendar) — the session that passes or fails one fills its row:

| Gate | Due | Decision | When | Observed |
|---|---|---|---|---|
| A′ — replay soak (S2.5): 10 min, zero restarts; live RTSP frames with correct timing (S2.2) | Tue 22 | | | |
| B — ANPR viability on the live sandbox (S4.1): real reads with sane confidence | Thu 24 | | | |
| C — route across ≥ 3 cameras from a plate typed into the UI (S4.2; demo vehicle qualifies) | Thu 24 20:00 | | | |
| D — documents start whatever the code state (S5.1) | Fri 25 09:00 | | | |

## Open risks

| Risk | Mitigation in the plan |
|---|---|
| Sandbox CDN or RTSP gateway goes away before the 28th | Record fallback footage of every component the moment it works; local replay of own footage for development |
| No real vehicle crosses two cameras | Demo vehicle through the real pipeline (labelled); harvest attempt on the CDN recordings when it is not rate-limiting |
| RTSP session cap (~6 suspected) | Active tier ≤ 6; wall served from the worker's tee, never a second pull |
| Documentation squeezed by code | Friday 25 Sep is documents and videos (GATE D 09:00); nothing else |
| Claims in the deliverables that the code does not back | `docs/architecture.md` Part C is the checklist; every `[measured]` needs the run |

---

## Log

```
## <task id> — <status: DONE | PARTIAL | BLOCKED | CUT>
When:      <UTC timestamp>
Observed:  <what actually happened — numbers, errors, counts; the acceptance check's real output>
Done so far: <PARTIAL only — what is finished and committed>
Surprise:  <anything that differed from the plan>
Next:      <task id, or for PARTIAL: the first thing the next session must do>
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

```
## R1 — DONE (build plan written; open decisions settled)
When:      2026-09-20T13:10Z
Observed:  docs/tasks.md rewritten as 27 sessions (S0.2–S6.3), each with
           Read-first / Build / Acceptance / Write-off, plus the session
           protocol, calendar with GATE A'/B/C/D and the cut order.
           decisions.md: F11–F21 added (stack, layout backend/+ml/ with
           backend/core shared, time base, IoU tracker, harvest time-box,
           Pipeline 3 conditional, no hosting, measurement method, second
           system via mediamtx, test footage, fuzzy-alert policy).
           CLAUDE.md §5/§6 and the three layer CLAUDE.md files point at the
           protocol and the package paths.
Surprise:  none.
Next:      S0.2
```

```
## R2 — DONE (plan v2 after the cold-start review)
When:      2026-09-20T19:15Z
Observed:  An independent reviewer (a separate agent that had not seen the
           docs being written) read the whole doc set as a cold Claude Code
           session would and returned 43 findings: 5 blockers (S0.2's own
           acceptance checks could not pass; every date a day stale; the
           S1.1 schema conflicted with F13/S1.2/S2.5 and blocked zone
           alerts; header-only auth made <img>/EventSource/hls.js
           unbuildable), 28 should-fix, 10 nits. All 43 applied:
           tasks.md rewritten (30 sessions; S1.3 and S3.1 split; PARTIAL +
           dirty-tree + [Adi]-task rules; calendar Mon 21 -> Sun 27);
           decisions F22-F32 added, C13 marked superseded, O11 settled;
           api.md B6/B7/B8/B10/B12 rewritten and B15 added; CLAUDE.md
           (dates, rule 9 provenance incl. test, read-first authority,
           tests/scripts/CHECKSUMS); backend/ml/frontend CLAUDE.md
           (cookie auth transport, alerts-only tailer, ffmpeg via config,
           FrameTick, React 18 pins); .gitignore (tools/ and models/ fully
           ignored, root CHECKSUMS.txt committed, data/measurements kept,
           data/screens ignored); .env.example rewritten with the eight new
           variables; README points at S0.2; editor's notes on the three
           verbatim run-sheets.
           A second, independent reviewer then read plan v2 cold and returned
           26 more findings (1 blocker: unanchored `tools/` and `models/`
           ignore patterns would have silently dropped backend/tools and
           ml/tools from every commit; plus Git-Bash shell forms, S2.1/S2.2
           acceptance numbers that could not pass, TestClient vs
           TrustedHost, the Vite scaffold on a non-empty folder,
           seed_registry needing the catalogue, ACTIVE_CAMERAS=6, alerts.zone_id,
           single-writer semantics, F15/F16/F21 wording, calendar remnants).
           All 26 applied (tasks.md v2.1; decisions F33–F36; .gitignore
           anchored; .env.example ACTIVE_CAMERAS=6). S0.2's acceptance was
           re-simulated in a scratch git repo after the changes: passes.
Surprise:  The previous plan's first session would have halted on its own
           acceptance check twice (check-ignore on non-existent paths; the
           credential grep matching the plan's example URL); and v2's own
           .gitignore would have lost two source packages.
Next:      S0.2
```

```
## R3 — DONE (plan v2.2: third review, 7 findings applied)
When:      2026-09-21T19:15Z (22 Sep 00:45 IST)
Observed:  A third reviewer checked plan v2.1 against the laptop itself
           (old repo folder listing, the old .venv, the new repo's .git).
           Findings and fixes:
           1. The repo already existed (GitHub Desktop: initial commit
              883b8fc pushed to origin/main on 20 Sep) while the plan and
              progress.md said "no repo yet" / "git init" — S0.2 would have
              re-run git init and could have failed its own commit. S0.2 is
              now "baseline commit + ignore checks + tag docs-v0 + push";
              protocol step 4, the ledger, README and Current state agree.
           2. .env: S0.4 mixed a Claude session with Adi copying secrets.
              The copy + two API keys are now an [Adi] step BEFORE S0.4;
              no session reads or creates .env (PARTIAL path if missing).
           3. .claude/settings.json written (F38): Read allow + additional
              directory for D:\projects\Sentinel_Repo (dozens of Read-first
              pointers go there), Edit deny there, Read deny on .env (also
              the old repo's), BASH_DEFAULT_TIMEOUT_MS 300000 and
              BASH_MAX_TIMEOUT_MS 3600000 for the soaks. Validated against
              the published settings schema (0 errors). The file bridge
              refuses to write into .claude/, so it sits at
              scripts/claude-settings.json until S0.2 moves it into place
              (step added) - or Adi does: mkdir .claude, then
              move scripts\claude-settings.json .claude\settings.json.
           4. Package versions (F37): the old .venv holds opencv-python
              5.0.0.93 AND opencv-contrib-python 4.10.0.84 (paddlex's pin)
              over one cv2/ folder; cv2.pyd carries the contrib install's
              timestamp, so contrib is what ran. S1.1 now lists the exact
              versions read off that venv's dist-info (fastapi 0.141.1,
              uvicorn 0.53.0, python-multipart 0.0.32, python-dotenv 1.2.3,
              httpx 0.28.1, pydantic 2.13.5, numpy 2.3.5,
              opencv-contrib-python 4.10.0.84, Pillow 12.3.0,
              cryptography 50.0.1, psutil 7.2.2, onnxruntime-directml
              1.24.4, paddlepaddle 3.3.1, paddleocr 3.7.0, paddlex 3.7.2)
              and its acceptance asserts pip check + a single OpenCV.
           5. docs/reference/old-build/CLAUDE.md (the 13-Sep rulebook)
              archived verbatim as CONSTITUTION.md (editor's note on top)
              so Claude Code never loads it as instructions; root CLAUDE.md
              §5 points at the new name. The file bridge cannot delete, so
              the old path holds a 5-line "archived stub - nothing here
              applies" until S0.2 git-rm's it (step added to S0.2).
           6. Protocol step 5 gained the rule "from S1.2, python means
              .venv/Scripts/python"; the 14 plain python/pip commands in
              S1.1–S4.2 were rewritten to the venv form; launch.py and
              doctor.py are named as the stdlib-only Anaconda exceptions;
              backend/ and ml/ CLAUDE.md run lines say the same.
           7. The two network pulls (S2.2 20 s, S6.1 60 s) are marked as
              Adi's steps with a detached-log procedure, since a session
              cannot unplug the laptop and the pull disconnects Claude Code.
           Also: .gitignore now ignores .claude/settings.local.json.
Surprise:  The laptop's Claude Code shell did not start for the reviewing
           session, so the files were written through the file bridge and
           the baseline commit is left to S0.2 (or Adi) — hence finding 1's
           "may still be uncommitted" wording in S0.2.
Next:      S0.2
```
