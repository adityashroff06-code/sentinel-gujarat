# Progress — session handoff

Append a block after **every** task, in the format at the bottom. Record what was observed, not what was intended. Never delete an entry; supersede it with a later one. The top section is rewritten each session so the next session can start from it.

---

## Current state (23 Sep 2026, 18:00 UTC / 23:30 IST — plan v2.4)

- **Decision:** fresh, structured rebuild (`docs/decisions.md` F1). This repo holds the documentation, the plan and the carried-over deliverables. The previous build at `D:\projects\Sentinel_Repo` still runs as a demo and is the read-only reference.
- **Plan:** `docs/tasks.md` **v2.4 (23 Sep, 23:30 IST)** — v2.3 plus Adi's answers of 23 Sep and decision **F49** (every camera gets a connection check; live tests, the active tier and the demo run on the best-working cameras it picks, never on fixed ids) — see the R5 block. v2.3 (22 Sep, 23:30 IST) was v2.2 plus five new tasks ahead of the current position (**S3.0** login + hardening, **S3.7** catalogue adapter, **S3.5** hosting go-live, **S3.6** own-footage ground truth, **S6.1b** overnight hosted soak + backups) and amendments inside S2.2, S2.5, S3.2, S3.3, S3.4, S5.1, S5.4 and S5.5. Nothing already done was re-opened. Previously: v2.2 — 30 one-session tasks S0.2 → S6.3 with the protocol every Claude Code session follows, a calendar re-based to Mon 21 with gates A′/B/C/D, and a cut order. Two independent cold-start reviews (43 + 26 findings, R2) and a third review (7 findings, R3) have been applied. Open decisions O1–O7, O9, O11 are settled (F11–F38) and O8 on 23 Sep (Category 1, students); O10 remains (Adi, in S3.4).
- **Deadline:** **28 Sep 2026 — confirmed on the portal 22 Sep**: "Last Date to Apply and Upload Your Submission", shortlisting the same day; it is an upload, not a live evaluation. The plate is handed over at the on-site hackathon on **12–13 Oct** (FAQ 27), after this plan ends. S0.3 is closed: **Category 1** (Adi registered as students, 23 Sep). Build window Mon 21 – Thu 24 for code, Fri 25 for deliverables (GATE D 09:00, code freeze at end of day), Sat 26 soak + rehearsal, Sun 27 submit, Mon 28 buffer. The Mon 21 column started a day late and was caught up on Tue 22; today (Wed 23) closed its last two laptop-only items, so the Wed 23 column (S3.0, S3.7, S3.1a, S3.1b, S3.2, S3.3) is the live one after S2.2.
- **Session environment:** this session runs **on the laptop** (Windows 10, Git Bash, Anaconda python 3.13.9 on PATH, real `.env`, GTX 1650, ffmpeg in the old build's `tools/`). The repo had been deleted and re-cloned, so `.venv` was gone; it was rebuilt here from `requirements.txt` + `requirements-dev.txt` and **every laptop-only acceptance item carried since 22 Sep has now run** (S1.1's four lines, S0.4's doctor). The previous session ran in a Claude Code cloud container (Linux, python 3.11.15, no GPU, no ffmpeg, no `.env`), which is why those items were outstanding.
- **Git:** `main` == `origin/main` at `92fa02a` (S2.2) on the laptop and on GitHub before R5 (checked 23 Sep 23:12 IST), clean; R5 is one docs-only commit on top. Baseline commit `577587b` ("S0.2: documentation baseline, plan v2.2") still carries the annotated tag `docs-v0`.
- **Session result (Wed 23, laptop):** the venv is rebuilt and the two carried-over `[~]` tasks are **closed**: **S1.1 [x]** (pip check clean; exactly `opencv-contrib-python 4.10.0.84` + `onnxruntime-directml 1.24.4`; `4.10.0 1.24.4 ['DmlExecutionProvider', 'CPUExecutionProvider']`; `config.ffmpeg()` resolves to an existing exe) and **S0.4 [x]** (`.env` present with both API keys; doctor exits 0 with ffmpeg, ffprobe, Node v24.20.0, the GTX 1650 and the variable names). Suite on the laptop: **68 passed** unchanged from the cloud, then **73 passed** after five regression tests for a doctor bug. Monday's column is now **S0.2 [x], S0.4 [x], S1.1 [x], S1.2 [x], S1.3a [x], S1.3b [~], S2.1 [x]** — S1.3b's live probe is the only Monday item still open.
- **Defect found and fixed this session:** `scripts/doctor.py` reported `npm : not found` although npm 11.19.0 is installed — `subprocess.run(["npm", ...])` cannot launch `npm.cmd` because Windows CreateProcess does no PATHEXT lookup. Resolved through `shutil.which()` now, with regression tests (`tests/test_doctor.py`). It mattered because S3.2 scaffolds the frontend with npm. The cloud smoke run could not have caught it: npm resolves normally on Linux.
- **New scope since v2.2 (does not change what comes next):** the demo is **hosted for the judges with a login** — decisions F41 (users, sessions, roles `viewer`/`evaluator`/`admin`), F42 (tunnel; Tailscale Funnel by default), F43 (a real hit and a real route from our own footage), F44 (`-timeout`, not `-rw_timeout`), F45 (the `/api/ingest` catalogue shape), F46 (an evaluator's first screen and a feed-status strip). Source: `claude/submission-verification-2026-09-22.md` and `claude/demo-gap-review-2026-09-22.md`.
- **Scope change v2.4 (decision F49, Adi, 23 Sep):** every camera gets a connection check (the probe, all 30); the live tests, the active tier and the demo run on the best-working cameras that check picks, never on fixed ids. `data/camera_seed.csv`'s fixed 5-camera tier (cam06, cam09, cam26, cam27, cam28) is now only the fallback; S3.7 builds the pick (`seed_registry --pick-active`), and S2.2's pull, S3.1a's demo route, S4.1's run and S4.2's harvest use it.
- **S2.2 done (Wed 23, laptop):** RTSP frame source built and proven — harness **83 passed** (was 73; +10 for the parametrised RTSP cases and the mediamtx-publisher checksum tests), and a live cam06 smoke read **134 frames, monotonic, tee bounded at 10 segments, restarts_seen=0**, newest tee segment **hevc 1920×1080**. mediamtx v1.21.1 is fetched and SHA-256-pinned in `CHECKSUMS.txt`. A 24-agent adversarial review's 14 confirmed findings were all applied or consciously deferred (F47 scene-cut backed out after measuring a false-positive storm; F48 mediamtx localhost-only + MoQ off). **S1.3b's live probe also ran this session** (RTSP live 30/30, HLS 30/30, 0 × 403 — the grid is now mixed h264 ×24 / hevc ×6), so that Monday item is closed too. Only [Adi]'s 20 s Wi-Fi network pull for S2.2 is deferred (a session can't cut the laptop network) — **set for Thu 24**, run on the best-working camera from a fresh all-camera check (F49).
- **Next task:** **S2.3** (motion gate MOG2, YOLOX-S detector on DirectML with one lock around `session.run()`, greedy IoU tracker, `fetch_models.py` with checksum). Laptop session; the frame source (`for_camera`) is ready to feed it. GATE A′ closes at the end of S2.5.
- **[Adi] queue** (items don't block each other): ①–③ done 23 Sep; ④ **S0.3 done** — Category 1, students; ⑤ **S0.5 recorded** — the check that nothing on screen shows a credential is done at the end, in S5.5 (Adi's call); ⑥ a 15-minute Tailscale Funnel trial on the laptop (install, MagicDNS + HTTPS certs, `tailscale funnel --bg 8000`, open the URL from mobile data, reboot and check it comes back) — it gates S3.5, so failing early is worth knowing; ⑦ **Thu 24:** film the S3.6 clips — **10 recordings of 60–90 s**, one vehicle with a legible plate at real locations a few minutes apart, noting the coordinates; ⑧ **Thu 24:** S2.2's 20 s Wi-Fi pull, on the best-working camera from a fresh all-camera check (F49).
- **Watch item for Wednesday:** Node is **v24.20.0**, not the v20.x the plan assumed. It clears the `>= 20.19` floor, but S3.2 pins Vite 6 / React 18.3.1 — if the scaffold misbehaves, Node 24 is the first suspect.
- **Blockers:** none.
- **Timing note:** a full `.venv/Scripts/python -m pytest -q` takes **~3m20s on this laptop** (vs seconds in the cloud container) — the paddle/cv2 import cost. Budget for it; do not run it casually mid-task.

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

```
## S1.1 — DONE (laptop venv rebuilt from scratch; all four laptop
##              acceptance lines pass; supersedes the 22 Sep PARTIAL)
When:      2026-09-23T07:10Z
Observed:  The repo had been deleted and re-cloned, so .venv was gone and
           the S1.1 laptop acceptance had still never run on this machine.
           Rebuilt: `python -m venv .venv` with Anaconda python 3.13.9
           (D:\Anaconda\python.exe) -> .venv/Scripts/python 3.13.9,
           pip 26.2.1; then
           `.venv/Scripts/python -m pip install -r requirements.txt
            -r requirements-dev.txt` -> resolved every F37 pin on
           Windows/py3.13 with no conflict, 93 distributions installed.
           The four laptop-only acceptance lines, verbatim output:
           - pip check
             -> "No broken requirements found."
           - pip list | grep -i -E "opencv|onnxruntime"
             -> onnxruntime-directml  1.24.4
                opencv-contrib-python 4.10.0.84
             exactly two lines: no opencv-python, no plain onnxruntime.
             The environment markers in requirements.txt did their job.
           - python -c "import cv2, onnxruntime as o; print(cv2.__version__,
             o.__version__, o.get_available_providers())"
             -> 4.10.0 1.24.4 ['DmlExecutionProvider', 'CPUExecutionProvider']
             DirectML is present, so the GTX 1650 is reachable for S2.3.
           - python -c "from backend.core import config;
             print(config.ffmpeg())"
             -> D:\projects\Sentinel_Repo\tools\ffmpeg\
                ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe
             os.path.exists -> True; ffprobe likewise resolves and exists.
           The cloud-proven acceptance items were re-run here on the real
           venv and still hold:
           - `python -m backend.core.db init` -> D:\projects\sentinel-
             gujarat\data\sentinel.db: schema at version(s) [1],
             applied now: [1]
           - masked('rtsp://user%40x.y:secret@1.2.3.4:8554/x')
             -> rtsp://<email>:***@1.2.3.4:8554/x  (exact expected string)
           - `git check-ignore .venv data/sentinel.db` -> both printed
           Whole suite on the laptop venv: `.venv/Scripts/python -m pytest
           -q` -> **68 passed, 2 warnings in 203.09s**. Same 68 as the
           cloud session; nothing platform-specific fails. (Two starlette/
           anyio DeprecationWarnings, pre-existing, not from our code.)
Surprise:  the laptop suite takes 3m23s against a few seconds in the cloud
           container -- the paddle/cv2 import cost on this machine, not a
           regression. Worth remembering when budgeting sessions: a full
           `pytest -q` is a ~3.5-minute step here, so it needs its own
           timeout allowance and should not be run casually mid-task.
Next:      S2.2 (RTSP frame source) -- unchanged, and now unblocked on the
           environment side: the venv, DirectML and ffmpeg are all proven
           on this laptop.
```

```
## S0.4 — DONE (.env in place; doctor passes every acceptance condition;
##              one real defect found and fixed: a false "npm: not found")
When:      2026-09-23T07:20Z
Observed:  Adi's .env is present, so the doctor could finally run for real.
           First run (Anaconda python, no venv needed) exited 0 with no
           traceback and every acceptance condition met except one line
           that read `npm      : not found`.
           That was a defect in scripts/doctor.py, not a missing npm:
           `which npm` -> /c/Program Files/nodejs/npm and `npm --version`
           -> 11.19.0. run_first_line() passed a bare "npm" to
           subprocess.run without shell=True; Windows CreateProcess does
           no PATHEXT lookup, and npm ships as npm.cmd beside an
           extensionless shell script, so the launch failed and the
           doctor reported an installed npm as absent. S3.2 scaffolds the
           frontend with npm, so a false negative here would have sent
           Wednesday's session hunting a non-existent problem.
           Fix: run_first_line() resolves cmd[0] through shutil.which()
           first (which honours PATHEXT on Windows) before launching.
           Second defect, cosmetic but in output this block is required to
           paste: the header and the .env line used em dashes, which the
           laptop's cp1252 console rendered as replacement characters
           (`doctor.py <?> Windows 10 <?> repo ...`). The script's output
           is now ASCII-only.
           Regression tests added (protocol rule 8), tests/test_doctor.py:
           - test_npm_is_not_reported_missing_when_it_is_installed
           - test_doctor_output_is_ascii_so_the_windows_console_can_print_it
           plus three guards on run_first_line() and on env_var_names()
           returning NAMES never values (rule 1). 5 passed in 1.00s.
           `python scripts/doctor.py` after the fix, verbatim and complete
           (it contains no secrets -- variable names only):
             doctor.py - Windows 10 - repo D:\projects\sentinel-gujarat
             python   : 3.13.9 at D:\Anaconda\python.exe
             node     : v24.20.0 (>= 20.19 ok)
             npm      : 11.19.0
             ffmpeg   : ffmpeg version N-126537-g7523428c26-20260913
                        Copyright (c) 2000-2026 the FFmpeg developers
                        [default (old build tools/)]
             ffprobe  : ffprobe version N-126537-g7523428c26-20260913
                        Copyright (c) 2007-2026 the FFmpeg developers
                        [default (old build tools/)]
             gpu      : NVIDIA GeForce GTX 1650, 512.78, 4096 MiB
             .env     : present - variable names: SENTINEL_EMAIL,
                        SENTINEL_PASSWORD, SENTINEL_CDN,
                        SENTINEL_STREAM_IP, SENTINEL_RTSP_PORT,
                        SENTINEL_WHEP_PORT, SENTINEL_DB,
                        SENTINEL_ACTIVE_CAMERAS, SENTINEL_INFER_FPS,
                        SENTINEL_API_PORT, SENTINEL_LOG_LEVEL,
                        SENTINEL_API_KEY_ADMIN, SENTINEL_API_KEY_VIEWER
             old build: reachable at D:\projects\Sentinel_Repo
             EXIT=0
           Against the S0.4 acceptance: no traceback [ok]; ffmpeg and
           ffprobe resolve [ok]; Node >= 20.19 (v24.20.0) [ok]; GPU line
           shows the GTX 1650 [ok]; .env present with SENTINEL_EMAIL,
           SENTINEL_PASSWORD, SENTINEL_API_KEY_ADMIN and
           SENTINEL_API_KEY_VIEWER among its names [ok]. S0.4 closes.
Surprise:  two things. (a) the doctor's one job is to tell the truth about
           the environment and it was lying about npm -- the bug survived
           the cloud smoke run precisely because npm resolves normally on
           Linux, so a Windows-only launch path went untested. Anything
           else the doctor reports as "not found" on this laptop is now
           worth a `which` before it is believed. (b) node is v24.20.0,
           not the v20.x the plan assumed; it clears the >= 20.19 floor,
           but S3.2 pins Vite 6 and react 18.3.1 against it, so if the
           scaffold misbehaves on Wednesday, Node 24 is the first suspect.
           Whole suite after the fix: 73 passed in 196.05s (68 + 5 new).
Next:      S2.2, unchanged.
```

```
## S2.2 — DONE (RTSP frame source; harness 17 green + live cam06 smoke)
When:      2026-09-23T02:20Z (laptop)
Built:     ml/ingest/rtsp.py (RtspFrameSource: one ffmpeg pull, -c copy HLS
           tee, watchdog armed at spawn, jittered backoff, -timeout not
           -rw_timeout, URL built in memory + masked; resolve_url for
           template/placeholder/plain-local URLs); ml/ingest/__init__.py
           for_camera() dispatch (rtsp -> this, replay -> S2.1, hls ->
           NotImplementedError); ml/tools/smoke_rtsp.py; scripts/
           replay_publish.py (--fetch mediamtx + start_mediamtx/publish,
           reused by the harness and S3.4); tests/test_frame_source.py
           re-parametrised over replay+rtsp; tests/test_replay_publish.py.
           mediamtx v1.21.1 fetched, SHA-256 in CHECKSUMS.txt.
Observed:  Local acceptance (harness, mediamtx publishing the synthetic
           clip over RTSP): .venv/Scripts/python -m pytest
           tests/test_frame_source.py tests/test_replay_publish.py ->
           17 passed. Whole suite -> **83 passed in 306.52s** (73 + 10).
           Live sandbox acceptance (laptop, real cam06):
           `smoke_rtsp cam06 --seconds 60` -> frames=134 (>=100 ok),
           monotonic=yes, tee playlist lists 10 (<=10 ok), 11 .ts on disk
           (<=25 ok) held over a 130 s pull, restarts_seen=0 on a clean
           pull. ffprobe on the newest tee segment -> **hevc 1920x1080**
           (the acceptance text said h264; cam06 is hevc). Every log line
           shows rtsp://<email>:***@103.250.160.189:8554/... — the raw
           credential never appears.
           A 24-agent adversarial review found 14 confirmed items; all
           triaged and either fixed or consciously deferred (F47, F48):
           credential leak via TimeoutExpired.cmd -> masked; truncate-
           before-mask -> mask-then-slice; probed size no longer cached
           across reconnects (re-probe each pull); monotonic floor across
           a fast reconnect; interruptible backoff wait (close() wakes it);
           bufsize 4 frames -> 1 frame (8 GB budget); smoke --seconds
           deadline via a Timer so a dead feed can't hang; the scene-cut
           behaviour-8 wiring was BACKED OUT after measuring it (below).
Surprise:  (1) cam06 is hevc, not h264 — today's probe shows 6 hevc among
           30 (h264 x24). The grid is genuinely mixed H.264/H.265, exactly
           what feed-rules warns about; the -c copy tee preserves it and
           the raw-frame branch decodes it fine on CPU at 3 fps. The old
           "h264 on every live camera" was the 14 Sep snapshot.
           (2) Feed-rule 8 (in-stream loop cut) CANNOT be detected on a
           busy live feed by whole-frame diff: measured on cam06, ordinary
           3 fps traffic reaches mean-abs-diff 138 (p90=46, p95=79),
           overlapping any real cut; a threshold false-fired ~9% of frames
           = a restart every ~2.6 s, which would reset the tracker and
           break route reconstruction. Backed the wiring out; restart
           fires on reconnect only; a luminance-baseline detector is
           deferred (decision F47). Restart storm -> 0 after the revert.
           (3) Three harness defects fixed this session, each Windows/
           load-only so the earlier isolated runs missed them:
           MTX_RTSPTRANSPORTS="[tcp]" (bracket list syntax) killed
           mediamtx at startup; _wait_port connected to a STALE mediamtx
           and masked a bind failure (added proc.poll()); mediamtx dropped
           the -re-paced publisher under full-suite CPU load at its 10 s
           writeTimeout -> 404 storm, and pytest-timeout's thread method
           can't kill a blocked pull on Windows so the whole suite wedged
           (fixed: MTX_*TIMEOUT=30s + a wall-clock guard in the _take
           helper so no harness test can hang). mediamtx 1.21's MoQ binds
           0.0.0.0 by default and tripped Windows Firewall (a Block rule
           for mediamtx.exe was written by a cancelled prompt and removed);
           MoQ is now disabled (decision F48).
           (4) An external commit "324f8e4 Task 2.2" landed the bulk of the
           new files mid-session (not this session, not the protocol
           message format); this session's follow-up commit completes S2.2
           with the review fixes, the revert and this write-off.
Deferred:  [Adi] the 20 s Wi-Fi network pull — a session cannot cut the
           laptop network without cutting Claude Code off. The backoff/
           reconnect path is already proven by the smoke log's open-fail
           -> backoff -> pull-started sequence and by three harness tests
           (reconnect+monotonic, backoff-doubling, resume-after-kill).
Next:      S2.3 (motion gate, MOG2, YOLOX-S detector on DirectML, greedy
           tracker, model fetch with checksum).
```

```
## R5 — DONE (plan v2.4: Adi's answers + every camera checked, the best-working ones tested)
When:      2026-09-23T18:00Z (23 Sep 23:30 IST)
Observed:  Documentation-only revision from Adi's answers in chat, 23 Sep.
           Before it, laptop main == GitHub main == 92fa02a, clean.
           S0.3 DONE: Category 1 - Adi registered as students; brief.md
           section 0 updated, O8 closed in decisions.md section 5.
           S0.5: the insurance recording exists (Adi); its second
           acceptance line (no credential on screen) moves to S5.5's
           credential sweep - Adi's call. Marked [~].
           S2.2: the 20 s Wi-Fi pull is set for Thu 24 (Adi). It is not
           a connection test: the smoke runs 180 s, Adi cuts Wi-Fi for
           20 s, and the log must show the drop, doubling backoff and
           frames resuming.
           S3.6: Adi films 10 recordings of 60-90 s on Thu 24 (was two
           or three clips of 30-60 s); mediamtx publishes one path per
           clip used (local01, local02, ...).
           New decision F49 (Adi): every camera gets a connection check;
           the live tests, the active tier and the demo run on the
           best-working cameras that check picks - never on fixed ids.
           Amended in place: tasks.md S2.2 (the pull runs on a picked
           camera after a fresh probe of every camera), S3.7 (builds
           seed_registry --pick-active from the latest probe result;
           budget 45 min -> 1 h), S3.1a (demo route on three picked
           cameras in one geographic cluster; cam06/cam10/cam09 is the
           pinned fallback for the tests), S3.4 (one path per clip; the
           5 active cameras come from the pick), S3.6 (10 recordings),
           S4.1 (probe + pick before the run), S4.2 (harvest clusters
           from the check), S5.5 (carries S0.5's check). Also: brief.md
           (entry category; FR-3.2), decisions.md (F49 added, F43
           note, O8 settled), ml/CLAUDE.md (tier picked, not fixed;
           local01... one per clip).
           Left as they are: historical evidence naming cameras
           (sandbox-findings.md, earlier log blocks, F44/F47), the unit
           tests' fixed ids, and camera_seed.csv's fps_tier column (now
           the fallback only).
Surprise:  none - no code was touched and no completed task re-opened.
Next:      S2.3, unchanged. Thu 24 adds two [Adi] items: the S2.2 Wi-Fi
           pull and the S3.6 filming.
```

```
## R6 — DONE (plan v2.5: port, don't retype; the UI bar; demo held against the HLD)
When:      2026-09-23T20:57Z (24 Sep 02:27 IST), cloud session, branch
           claude/hopeful-franklin-661gt9 — docs only, no code touched.
Observed:  Adi's direction of 24 Sep, recorded as F52-F57 (F50-F51 left
           free for the Phase 2 session running on the laptop):
           F52 working modules are ported from the previous build, not
           retyped (adapted to api.md, defect fixes + regression tests,
           named "ported from <old path>"); F53 the UI bar - port, then a
           design pass on five hero screens (Login, Command, Live Wall,
           Route, Search/Reports), then a review gate (build, lint, smoke,
           pytest, code review at high effort, /security-review); F54 demo
           = Model 1 + Model 2 + Pipeline 1, Pipeline 3 described not
           built, S4.2 and S4.3 cut, GATE C moves to S3.6; F55 demo tier =
           cam06 pulled live + own footage, pick-active cut; F56 own clips
           published once with the real gaps; F57 two lanes.
           tasks.md v2.5: lanes paragraph; ledger; new S3.3b; S3.2/S3.3
           port + review gate; S3.1a/S3.4/S3.6/S3.7/S4.1/S5.1/S5.4
           amended; S4.2/S4.3 [-]; cut order #11. architecture.md Part D
           (the demo against the HLD, model by model, plus the names
           table). CLAUDE.md, frontend/CLAUDE.md ("Port and polish"),
           CODEX.md (its map still described the old src/ui layout and
           told reviewers NOT to use backend/frontend/ml - rewritten),
           README status, demo-script, submission-checklist.
           Phase 2 (S2.3-S2.5 blocks) and this file's Current state were
           deliberately NOT edited, so the laptop session is undisturbed;
           the first session after the merge folds v2.5 into Current state.
           Login and hosted URL - checked across every doc: consistent in
           CLAUDE.md rule 11, F41/F42, api.md section 9, backend/ and
           frontend/CLAUDE.md, .env.example, S3.0, S3.5, S6.1b, the
           checklist's "Hosted demo and credentials" and demo-script beat
           1. Gaps: none of it is built yet (S3.0, S3.5 open); Adi's
           Funnel trial (queue item 6) is not recorded as done and gates
           S3.5; HLD section 6 still says "ships a single role" and has
           no deployment section (Part C rows, fixed in S5.1). The portal
           lists the hosted URL as optional (brief.md line 14).
           Demo against the HLD: matches Model 1 + Model 2 as built; the
           HLD's Pipeline 3 must be worded "designed and validated
           separately, not built" (HLD line 6, section 1, Appendix B).
Surprise:  (1) "Live views on a central command, nothing saved" was
           called Pipeline 3 and live streams Model 3 in chat; in this
           design and the brief they are Pipeline 1 and Model 2 - the
           names table in Part D fixes the vocabulary for every document.
           (2) Seven commits landed in the read-only previous repo on
           24 Sep 00:18-01:05 IST, after R5 (10-minute measured run:
           RAM peak 1,397 MB, 6.0% plate-read success, every real read on
           cam06; ingest_file.py; the D4 alert-id fix). They are not in
           this repo; F52 brings them here by porting (S4.1 names
           measure_run.py). The "Key measurements" table here stays blank
           until S4.1 measures this build.
Merge:     merge after the running Phase 2 session has committed; expect
           conflicts only at the end of this file and in decisions.md
           section 2 (if that session added F50/F51) - keep both sides.
Next:      unchanged for the laptop lane: S2.3. Cloud lane may start
           S3.0, S3.7 and S3.2 once this is on main.
```
