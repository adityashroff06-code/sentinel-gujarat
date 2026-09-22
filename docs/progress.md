# Progress — session handoff

Append a block after **every** task, in the format at the bottom. Record what was observed, not what was intended. Never delete an entry; supersede it with a later one. The top section is rewritten each session so the next session can start from it.

---

## Current state (22 Sep 2026, 18:00 UTC / 23:30 IST — plan v2.3)

- **Decision:** fresh, structured rebuild (`docs/decisions.md` F1). This repo holds the documentation, the plan and the carried-over deliverables. The previous build at `D:\projects\Sentinel_Repo` still runs as a demo and is the read-only reference.
- **Plan:** `docs/tasks.md` **v2.3 (22 Sep, 23:30 IST)** — v2.2 plus five new tasks ahead of the current position (**S3.0** login + hardening, **S3.7** catalogue adapter, **S3.5** hosting go-live, **S3.6** own-footage ground truth, **S6.1b** overnight hosted soak + backups) and amendments inside S2.2, S2.5, S3.2, S3.3, S3.4, S5.1, S5.4 and S5.5. Nothing already done was re-opened. Previously: v2.2 — 30 one-session tasks S0.2 → S6.3 with the protocol every Claude Code session follows, a calendar re-based to Mon 21 with gates A′/B/C/D, and a cut order. Two independent cold-start reviews (43 + 26 findings, R2) and a third review (7 findings, R3) have been applied. Open decisions O1–O7, O9, O11 are settled (F11–F38); O8 and O10 remain (Adi, in S0.3 and S3.4).
- **Deadline:** **28 Sep 2026 — confirmed on the portal 22 Sep**: "Last Date to Apply and Upload Your Submission", shortlisting the same day; it is an upload, not a live evaluation. The plate is handed over at the on-site hackathon on **12–13 Oct** (FAQ 27), after this plan ends. S0.3 now only has to confirm the entry category. Build window Mon 21 – Thu 24 for code, Fri 25 for deliverables (GATE D 09:00, code freeze at end of day), Sat 26 soak + rehearsal, Sun 27 submit, Mon 28 buffer. The Mon 21 column started a day late; this session (Tue 22) is catching it up.
- **Session environment (new):** this session runs in a Claude Code **cloud container** (Linux, Python 3.11.15, Node 22, no GPU, no ffmpeg preinstalled, no `.env`, no sandbox network access), with the repo cloned at `/home/user/sentinel-gujarat` and push access to `origin`. Code, schema, docs and every test that does not need the laptop's venv pins, GPU, ffmpeg default path or the live sandbox can be built and proven here; laptop-only acceptance items are written off explicitly (`Next:` lines name them) and stay with Adi / a laptop session.
- **Git:** `main` == `origin/main`, baseline commit `577587b` ("S0.2: documentation baseline, plan v2.2") with annotated tag `docs-v0` — Adi had already committed, tagged and pushed before this session; S0.2's checks were then run and passed here (block below).
- **Session result (Tue 22, cloud):** the whole Monday column is caught up except the laptop-only items — **S0.2 [x], S0.4 [~], S1.1 [~], S1.2 [x], S1.3a [x], S1.3b [~], S2.1 [x]**; test suite **68 passed**; every task committed and pushed to `main` with its block in the Log.
- **New scope since v2.2 (does not change what comes next):** the demo is **hosted for the judges with a login** — decisions F41 (users, sessions, roles `viewer`/`evaluator`/`admin`), F42 (tunnel; Tailscale Funnel by default), F43 (a real hit and a real route from our own footage), F44 (`-timeout`, not `-rw_timeout`), F45 (the `/api/ingest` catalogue shape), F46 (an evaluator's first screen and a feed-status strip). Source: `claude/submission-verification-2026-09-22.md` and `claude/demo-gap-review-2026-09-22.md`.
- **Next task:** **S2.2** (RTSP frame source) — a **laptop** session: it needs the live sandbox, the mediamtx local publisher, the laptop's ffmpeg and Adi's 20 s network pull; a cloud session cannot run its acceptance. The S2.1 harness is ready to parametrise with the RTSP source.
- **[Adi] queue before/alongside S2.2** (items don't block each other): ⑥ *(new, v2.3)* a 15-minute Tailscale Funnel trial on the laptop (install, MagicDNS + HTTPS certs, `tailscale funnel --bg 8000`, open the URL from mobile data, reboot and check it comes back) — it gates S3.5, so failing early is worth knowing; ⑦ *(new, v2.3)* film the S3.6 clips: one vehicle with a legible plate at two or three real locations, noting the coordinates; ① create `.env` per S0.4 and run `python scripts/doctor.py`, paste the output here; ② at the next laptop session's start, create the real `.venv` from requirements.txt + requirements-dev.txt and run the S1.1 laptop acceptance lines (pip check; the two-line opencv/onnxruntime assertion; the DmlExecutionProvider import line; `config.ffmpeg()`); ③ `python -m backend.tools.probe` (S1.3b) and record the RTSP-live count; ④ S0.3 portal confirmation; ⑤ S0.5 insurance recording.
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

```
## S0.2 — DONE (baseline verified; commit and tag were already Adi's)
When:      2026-09-22T09:30Z
Observed:  Tree clean on entry — the baseline commit 577587b ("S0.2:
           documentation baseline, plan v2.2") and the annotated tag
           docs-v0 (2302024 -> 577587b) were already on origin, pushed by
           Adi, exactly the "if Adi has already committed" branch of the
           task. All checks then run here and passed:
           - check-ignore -v printed the four expected lines
             (.env -> *.env; data/logs/api.log -> data/logs/;
             models/yolox_s.onnx -> /models/; tools/ffmpeg/bin/ffmpeg.exe
             -> /tools/)
           - check-ignore backend/tools/x.py ml/tools/x.py: no output,
             exit=1 (the two source packages are NOT ignored)
           - git grep --cached for credential URLs: no matches
           - docs/reference/old-build/ holds CONSTITUTION.md and no
             CLAUDE.md; .claude/settings.json in place;
             scripts/claude-settings.json gone
           - docs-v0 is on HEAD; main == origin/main == 577587b
Surprise:  This session is a Claude Code cloud container (Linux,
           Python 3.11.15, no ffmpeg, no .env, repo at
           /home/user/sentinel-gujarat), not the laptop. Laptop-only
           acceptance items of later tasks are called out per task.
Next:      S0.4 — [Adi] creates .env first (task block says how); the
           doctor.py code is written next regardless.
```

```
## S0.4 — PARTIAL (doctor.py written and smoke-run; laptop run is Adi's)
When:      2026-09-22T09:40Z
Observed:  scripts/doctor.py written: stdlib-only, prints Python, Node
           (with the >= 20.19 check), npm, ffmpeg/ffprobe first lines with
           which path answered (SENTINEL_FFMPEG_DIR -> PATH -> old-build
           default), nvidia-smi GPU line, .env presence with variable
           NAMES only, old-build reachability. Smoke run in this cloud
           container: exits 0, no traceback; prints python 3.11.15,
           node v22.22.2 (>= 20.19 ok), npm 10.9.7, ffmpeg/ffprobe not
           found, nvidia-smi not available, .env MISSING, old build not
           reachable — all correct for this box.
Done so far: the script, committed. The cloud run above proves "runs
           before the venv exists, changes nothing, no traceback"; it
           cannot prove the laptop facts.
Next:      [Adi] on the laptop: create .env per the S0.4 block (copy the
           old one + the two new API keys), then run
           `python scripts/doctor.py` and paste the output into a progress
           block here (it contains no secrets). Acceptance passes when it
           shows ffmpeg+ffprobe resolved, Node >= 20.19, the GTX 1650, and
           .env with SENTINEL_EMAIL, SENTINEL_PASSWORD,
           SENTINEL_API_KEY_ADMIN, SENTINEL_API_KEY_VIEWER set.
```

```
## S1.1 — PARTIAL (code, schema and contract fold done and proven here;
##                 the laptop-venv acceptance items remain)
When:      2026-09-22T10:00Z
Observed:  Written and committed: requirements.txt (the F37 pins with the
           platform markers, verbatim from the task block);
           requirements-dev.txt pinned from this first install
           (pytest==9.1.1, pytest-timeout==2.4.0, playwright==1.63.0);
           backend/__init__.py, backend/core/{__init__,config,
           logging_setup,db}.py, backend/core/timeline.py (declared stub
           until S2.1), backend/core/migrations/0001_initial.sql
           (schema v1 exactly as the folded contract), backend/app/
           __init__.py (empty until S1.3a), tests/conftest.py (throw-away
           keys + per-run DB path set BEFORE config import; never reads
           .env), tests/test_schema.py, pytest.ini, CHECKSUMS.txt header.
           docs/api.md: Part B folded into Part A in this commit —
           §1 transport enum + camera_id hygiene, §2 sightings columns +
           time base + bounded dedupe, §3 watchlist columns, §4 alerts
           (alert_seq, kind, cooldown rule), §5 canonical zone shape +
           events columns, §6 = B10 grammar + F21 policy, §7 full endpoint
           table + auth transport + route response (match_distance,
           suspect, warnings[]), §8 = F12 layout; banner on Part B.
           Acceptance observed in this cloud container (.venv on
           python 3.11.15; the seven pure-python pins resolved at exactly
           the F37 versions):
           - .venv/bin/python -m pytest tests/test_schema.py -q
             -> "6 passed in 0.06s"
           - .venv/bin/python -m backend.core.db init
             -> data/sentinel.db created, "schema at version(s) [1]"
           - masked('rtsp://user%40x.y:secret@1.2.3.4:8554/x')
             -> rtsp://<email>:***@1.2.3.4:8554/x   (exact expected string)
           - logging_setup.setup("test") -> data/logs/test.log written,
             record masked (rtsp://<email>:***@h/x)
           - git check-ignore .venv data/sentinel.db -> both printed
Done so far: everything above, committed.
Surprise:  pip resolved every applicable F37 pin on Linux/py3.11 without
           conflict; the same versions exist for both platforms.
Next:      S1.2 runs in this same cloud session (see its block). The
           remaining S1.1 acceptance items are laptop-only and fold into
           the next laptop session's start: create the real .venv with
           Anaconda python per S1.1, install requirements.txt +
           requirements-dev.txt, then run: pip check ("No broken
           requirements found."); pip list | grep -i -E "opencv|onnxruntime"
           prints exactly opencv-contrib-python 4.10.0.84 and
           onnxruntime-directml 1.24.4; the cv2/onnxruntime import line
           prints 4.10.0 1.24.4 with DmlExecutionProvider listed;
           config.ffmpeg() returns an existing path.
```

```
## S1.2 — DONE (plates + matcher core; 35 table-driven tests pass)
When:      2026-09-22T10:25Z
Observed:  backend/core/plates.py (normalise, canonical, plate_like,
           is_partial, weighted plate_match, alertable) and
           backend/core/matcher.py (WatchlistCache with canonical +
           4-char-prefix indexes, exact-first find_match, F21 alertable).
           .venv/bin/python -m pytest tests/test_plates.py -q ->
           "35 passed" (whole suite: 41 passed in 0.13s). Covered, with
           observed values: normalise incl. "GJ32 K 9819"->GJ32K9819->full;
           all seven ambiguity pairs fold; GJ01AB1234 vs GJ01A81234 ->
           (ambiguity, 0.0); vs GJ01AB1235 -> (fuzzy, 1.0), not alertable
           by default and alertable with SENTINEL_ALERT_ON_FUZZY=true;
           GJ05JB432 -> partial and plate_match vs GJ05JB4321 -> none;
           22BH1234AA -> full; OADFIX2FR and DFIX2F -> None; weighted
           distance composes (B->8 0.25 + 4->5 1.0 = 1.25 -> none);
           matcher canonical-index probe over 1,001 seeded rows returned
           the ambiguity hit in < 5 ms (observed ~0.02 ms); fuzzy via the
           prefix bucket works; partial reads take no fuzzy path; expired
           watchlist rows are excluded.
Surprise:  §6's coercion clause and the partial clause CONFLICT on
           GJ05JB432 (B->8 coercion makes it a full 9-char plate, but the
           acceptance pins it as partial). Resolved conservatively as
           decision F40: uncoerced full -> uncoerced structural prefix
           (partial) -> coercion-dependent full -> None. Also recorded
           F39: the cache excludes rows past expires_at (the schema
           carries the column; the task never said who enforces it).
Next:      S1.3a (same session): registry API, auth + audit, schemas,
           cameras/health/stats/gap-analysis, TestClient suite.
```

```
## S1.3a — DONE (registry API; 11 TestClient tests pass)
When:      2026-09-22T10:55Z
Observed:  backend/app/{main,__main__,auth,audit,schemas,routes_cameras,
           routes_meta}.py + backend/services/gap_analysis.py.
           .venv/bin/python -m pytest tests/test_registry_api.py -q ->
           "11 passed" (whole suite 52 passed). Observed per acceptance:
           /api/health open (db ok + counts); 401 without key on GET and
           POST; 403 for the viewer key on POST; POST /api/session sets
           the sentinel_key cookie, cookie authorises GET /crops/x.jpg
           (404 for the missing file, not 401), refuses mutations (405 —
           /crops has no POST route) and ordinary API GETs (401); 201
           manual create; 409 duplicate; 422 for department 'Navy',
           lat 123, and a credential-bearing rtsp URL; PATCH updates
           health/tier; /stream returns only the relayed HLS path;
           CSV import of tests/fixtures/import_3rows.csv -> accepted
           [imp01, imp02], rejected [{row: 3, reason lat}], imp03 absent;
           gap-analysis returns the exact 7-key shape with both isolated
           cameras at radius_km 5.0; stats returns the exact 8 keys; the
           POST wrote an audit row (role admin, action "POST /api/cameras
           -> 201", after_json carrying the row).
           Route-order trap respected: /gap-analysis and /import are
           registered before /{camera_id}.
Surprise:  none. The old build's reference modules on D:\ are unreachable
           from this cloud box; the folded contract in docs/api.md was
           sufficient on its own.
Next:      S1.3b (same session): cdn_session, probe, seed tools, OpenAPI
           export. The probe's live acceptance is laptop-only; the seeders
           and the OpenAPI export are provable here.
```

```
## S1.3b — PARTIAL (all code done; seeders + OpenAPI export proven here;
##                  the live probe run is laptop-only)
When:      2026-09-22T11:30Z
Observed:  backend/core/cdn_session.py (form login, cookie jar, browser
           UA, jittered backoff with one re-login on 403, CDN-origin-only
           fetch guard, masked logs); backend/tools/{probe,seed_registry,
           seed_watchlist,export_openapi}.py.
           Observed on this box:
           - seed_registry on a fresh DB: "cameras: 30 rows, 5 active
             across 5 departments — ACCEPTANCE: PASS"; --add and --replay
             covered by tests/test_seed_tools.py
           - seed_watchlist twice: "25 seeded ... 25 rows total" both
             runs; hero GJ01AB1234 stolen_vehicle/high; all 5 categories
           - export_openapi: "12 operations across 9 paths ->
             deliverables/registry-api.json" (regenerated per B3);
             tests/test_openapi.py asserts every operation has a
             description and a 2xx schema and no snapshot.jpg survives
           - whole suite: 57 passed
Done so far: everything above, committed. The regenerated
           deliverables/registry-api.json replaces the stale 15 Sep
           export (B3) and will grow as S3.1a/S3.1b add endpoints.
Surprise:  none.
Next:      Laptop-only remainder, at the next laptop session (needs .env
           + ffprobe + the sandbox): `python -m backend.tools.probe` —
           expect >= 20 RTSP-live cameras, record the observed count and
           any 403s in a progress block; the probe writes
           data/probe_results_<date>.json and never touches the 14 Sep
           evidence file. Then S2.1 (started in this cloud session).
```

```
## S2.1 — DONE (timeline + replay source + harness; all acceptance ran here)
When:      2026-09-22T12:20Z
Observed:  backend/core/timeline.py (real implementation replacing the
           stub: epoch/loop accessors, position<->stream-time, live
           position honouring the playback offset — 4 tests);
           ml/ingest/base.py (FrameTick, FrameSource, PtsSampler that
           drops on PTS, shared backoff_params logging attempt/base/delay,
           SceneCutDetector on downscaled grey mean-abs-diff);
           ml/ingest/replay.py (ffmpeg -re -stream_loop -1 pipe,
           stream_time = wall_time = pull_start + index/fps continuous
           across loops, wrap ticks from ffprobe duration, respawn with
           jittered backoff, stderr drained at DEBUG, try/finally kill);
           tests/fixtures/make_synthetic.py (60 s 640x360 25 fps testsrc2
           + moving drawbox; generated on this box via apt-installed
           ffmpeg 6.1.1).
           Acceptance observed (pytest, real-time paced by -re):
           - 100 consecutive frames at 3 fps with strictly increasing
             stream_time (and the 640x360 BGR shape)
           - 3 fps sampling over a 20 s window: frame count within
             60 ± 15 % and PTS span within 18-21 s (asserted bounds)
           - looping the 60 s clip to pts 130 s: >= 2 restart ticks,
             stream_time monotonic across the whole run
           - missing file, 3 attempts: logged base = 2, 4, 8 s, each
             delay within [0.5x, 1.5x] of its base, exactly 2 sleeps
             (patched), then ReplaySourceError
           - killing the ffmpeg child mid-read: frames resume after
             respawn, first resumed tick carries restart=True
           - scene-cut detector fires on black->white, silent on
             identical frames; PtsSampler drops on PTS incl. gap catch-up
           Whole suite: 68 passed in 188.72s.
Surprise:  (1) Patching global time.sleep in the backoff test turned
           subprocess's wait-poll into a spin (2,855 no-op sleeps); the
           source now waits through a module-level _sleep indirection and
           the test stubs only that. (2) Replay reads the pipe directly
           instead of the task's "reader thread": a keep-latest thread
           drops frames, which RTSP wants (S2.2) but the counting
           harness and the soak must not — reason recorded in the module
           docstring.
Next:      S2.2 (RTSP source) — needs the laptop: the live sandbox pull,
           the local mediamtx publisher, and Adi's 20 s network pull.
           Before it, the accumulated [Adi]/laptop items: .env, doctor
           run, S1.1 venv acceptance lines, the live probe (S1.3b).
```

```
## R4 — DONE (plan v2.3: the hosted demo, the login and ground truth folded in)
When:      2026-09-22T18:00Z (22 Sep 23:30 IST)
Observed:  Documentation-only revision, made from two reviews written the
           same day: claude/submission-verification-2026-09-22.md (the
           portal re-read against both repos) and
           claude/demo-gap-review-2026-09-22.md (15 gaps; point 5, the
           Model 1 metadata fields, was deliberately excluded by Adi).
           Portal facts now recorded in the docs: submission closes
           28 Sep (upload, shortlisting the same day); the on-site
           hackathon where the plate is handed over is 12-13 Oct.
           Added: decisions F41 (login, roles, sessions - supersedes F4's
           transport, extends F23), F42 (hosted over a tunnel - reverses
           F17), F43 (own-footage ground truth), F44 (-timeout not
           -rw_timeout), F45 (catalogue accepts /api/ingest and
           cameras.json), F46 (evaluator landing + feed-status strip).
           New tasks, all ahead of the current position: S3.0 (login,
           roles, sessions, public-exposure hardening; schema v2 via
           0002_auth.sql), S3.7 (catalogue adapter + new-feed runbook),
           S3.5 (hosting go-live: tunnel, evaluator accounts, 24/7
           runbook), S3.6 (own-footage real hit + real route), S6.1b
           (overnight hosted soak, backups, restart watchdog).
           Amended in place: S2.2 (-timeout, watchdog armed at spawn),
           S2.5 (2-frame zone confirmation), S3.2 (login page replaces
           the key dialog), S3.3 (Start here panel, feed-status strip,
           vehicle-class filter, person count), S3.4 (--many publishes
           local01-local03), S5.1 (HLD: demo deployment, login, costs,
           [model] labels, ffmpeg GPL), S5.4 (both run sheets rewritten),
           S5.5 (judge-facing README, hosted URL + credential check).
           Also updated: CLAUDE.md (dates, rules 11 and 12, doc map),
           docs/api.md (auth transport rewritten, new section 9 with the
           users/sessions schema and the exposure rules, /api/auth/* and
           /api/users in the endpoint table), brief.md section 0,
           architecture.md Part C (five new claim rows), demo-script.md
           (v2.3 run sheets, the old one kept as history),
           submission-checklist.md (hosted demo + demonstration content),
           feed-rules.md (editor's note on /api/ingest), backend/,
           frontend/ and ml/ CLAUDE.md, CODEX.md, .env.example
           (SENTINEL_SESSION_TTL_H, SENTINEL_PUBLIC_HOST), README status.
Surprise:  none - no code was touched and no completed task re-opened.
Next:      S2.2, unchanged. The v2.3 additions start at S3.0 on Wed 23.
```
