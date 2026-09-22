# Tasks — the build plan, one session at a time

This file is the plan **and** the checklist. Each task is sized for one Claude Code session and is self-contained: what to read, what to build, how to prove it, how to hand off. Execute in order unless a task says otherwise. A task is done when its acceptance check has **run and passed** and its block is in `docs/progress.md`.

Status marks: `[ ]` open · `[x]` done · `[~]` partial (a `PARTIAL` block exists in progress.md) · `[!]` blocked (reason in progress.md) · `[-]` cut

Revision: v2.2, 22 Sep 2026 00:45 IST — v2.1 (21 Sep 01:30) re-based the calendar to Monday 21 Sep and applied 43 + 26 findings from two independent cold-start reviews (`docs/progress.md` R2); v2.2 applies the 7 findings of a third review (`docs/progress.md` R3): the repo already exists so S0.2 is a baseline commit, `.env` is Adi's step before S0.4, a `.claude/settings.json` permissions file, S1.1 pins copied from the old `.venv` (one OpenCV package), the old constitution renamed, the venv-`python` rule, and the two network pulls marked as Adi's.

---

## How a session runs (the protocol — every session, every time)

**Prompt to paste into Claude Code** — either form:

```
Run task <ID> from docs/tasks.md, following its "How a session runs" protocol exactly.
Start by reading CLAUDE.md and the "Current state" section of docs/progress.md.
```
```
Resume Sentinel: read CLAUDE.md, then docs/progress.md "Current state", and run the task it
names as "Next task" from docs/tasks.md, following the "How a session runs" protocol exactly.
```

**Start**
1. Read `CLAUDE.md` (root) and the `CLAUDE.md` of every layer folder you will touch (`backend/`, `ml/`, `frontend/`).
2. Read `docs/progress.md` → **Current state**, and the **last block of the Log**. If the last block is `PARTIAL` for your task, continue from its `Done so far:` / `Next:` lines.
3. Read **only your task block** below and the documents its *Read first* line names. The *Read first* line is authoritative for the session; do not read the whole docs folder.
4. `git status` must be clean on `main` (S0.2 excepted — whatever is dirty when S0.2 starts is the documentation baseline, and S0.2 commits it itself). If it is dirty: (a) if Current state's **Next task** is your task, or the last Log block is `PARTIAL` for it, the previous session died mid-way — run `git diff --stat`, write the missing `PARTIAL` block from what you see, commit `<ID>: WIP` and continue; (b) if the dirt is an `[Adi]` task's doc edits, commit them as `<Adi-ID>: <what changed>` first; (c) otherwise stop and report — do not commit someone else's half-done work.
5. **Shell:** Claude Code's shell on Windows is Git Bash; every command below is written in bash form with an explicit interpreter — `.venv/Scripts/python -m …` after S1.1 creates the venv, plain `python` (Anaconda, on PATH) before that. Never rely on `activate`, `set` or `cd` persisting between tool calls; environment variables go inline (`SENTINEL_DB=data/soak.db .venv/Scripts/python -m ml`). If you are in PowerShell instead, translate (`$env:NAME='value'`).
   **From S1.2 onward, `python` means `.venv/Scripts/python`** — every `python`, `pip`, `pytest` and `playwright` in a task block or a layer `CLAUDE.md` is the venv's: `.venv/Scripts/python -m pytest …`, `.venv/Scripts/python -m pip …`, `.venv/Scripts/python -m playwright …`. Plain `python` in Git Bash is Anaconda, which has none of the project's packages. The only deliberate exceptions are stdlib-only entry points that must run before or around the venv: `python scripts/doctor.py` (S0.4) and `python launch.py …` (S3.4, S4.1 — the launcher spawns `.venv/Scripts/python` for everything else), plus the `[Adi]` tasks that run the old build.
   **Long-running commands:** `.claude/settings.json` raises the Bash tool's default timeout to 5 min and the ceiling to 60 min. A soak or measurement that runs longer than 5 min is started with an explicit timeout above its duration, or detached with its output in `data/logs/` and polled — never with the default and never blocking for hours.

**Work**
6. Build exactly what the task says. Deviations are allowed only with a reason written in the progress block.
7. A decision the task does not settle: take the default the task names; if it names none, take the most conservative option, record it as a new row in `docs/decisions.md` §2 (next free `F` number), and continue. Never stall a session on a choice.
8. Every bug fixed gets a regression test named after it (`tests/test_<area>.py::test_<bug_in_words>`).
9. Any change to a stored shape or an endpoint updates `docs/api.md` Part A **in the same commit**.

**Finish — mandatory even when the task is incomplete or the session is running out of context**
10. Run the acceptance check. Copy the *observed* output (numbers, counts, errors) into the progress block. Never write "should work".
11. Append a block to the **Log** at the end of `docs/progress.md` (format there; status `DONE`, `PARTIAL`, `BLOCKED` or `CUT`), then rewrite its **Current state** section: what is done, the **Next task** id, blockers.
12. Tick this file: `[x]`, `[~]`, `[!]` or `[-]` on the task's heading **and** in the Session ledger's Status column, with a one-line note if not `[x]`.
13. `git add -A && git commit -m "<ID>: <one line of what was observed>"`. Verify with `git status` first that `.env`, `data/` runtime files, `models/` and `tools/` are not staged (they are ignored; `data/measurements/`, `data/camera_seed.csv`, `data/cameras_raw.json`, `data/probe_results.json` and `CHECKSUMS.txt` are committed on purpose).

If context is running low: stop at a clean, compiling point, do steps 10–13 with status `PARTIAL`, and list precisely what is done and what the next session must do first.

**`[Adi]` tasks** are done by Adi, not by a Claude session, and **never block the next Claude task** (S0.3 and S0.5 can happen while S1.x runs). Adi records the outcome in `docs/progress.md` (or tells the next Claude session, which writes it off as its first action) and commits before the next Claude session starts, so the tree is clean.

**Environment facts every session may rely on**: Windows laptop; Python 3.13.9 (Anaconda `D:\Anaconda\python.exe`, on PATH as `python`) creates `.venv` in S1.1 and everything after that runs as `.venv/Scripts/python`; Node **20.19+** with npm (S0.4 verifies); Git; `ffmpeg`/`ffprobe` are **not** on PATH — every invocation goes through `backend.core.config.ffmpeg()` / `ffprobe()`, which resolve `SENTINEL_FFMPEG_DIR` (default `D:\projects\Sentinel_Repo\tools\ffmpeg\ffmpeg-master-latest-win64-gpl\bin`) then PATH; GTX 1650 via `onnxruntime-directml`; the sandbox credentials and the two API keys in `.env` (never printed). **`.env` is Adi's file:** he creates and edits it (before S0.4); `.claude/settings.json` denies every session reading, creating or editing it — a session that needs a value asks Adi to set it and reads only variable *names* through `scripts/doctor.py`. The same file lets sessions read the old build at `D:\projects\Sentinel_Repo` without prompting and blocks edits there. Commands are written to run from the repo root (`python -m …`, `npm --prefix frontend …`); `copy`/`type` lines are for `cmd`.

---

## Session ledger

| ID | Session | Day | Budget | Status |
|---|---|---|---|---|
| S0.1 | Fresh repo with structured docs; plan written and reviewed | Sat 20 – Mon 21 00:45 | — | done |
| S0.2 | Baseline commit of the plan, ignore-rule checks, tag `docs-v0`, push (the repo and its GitHub remote already exist) | Mon 21 | 10 min | [x] done Tue 22 (cloud session; commit+tag were already Adi's) |
| S0.3 | [Adi] Confirm the 28 Sep milestone and the entry category | Mon 21 | 10 min | |
| S0.4 | Environment check (`scripts/doctor.py`); `.env` is created by Adi **before** this session | Mon 21 | 30 min | [~] script written + cloud smoke; laptop run + .env are Adi's |
| S0.5 | [Adi] Insurance recording of the old build running | Mon 21 | 30 min | |
| S1.1 | Backend skeleton: venv, config, logging, schema v1 + migrations, contract folded, tests | Mon 21 | 1.5 h | [~] code+schema+fold proven (cloud, Tue 22); laptop venv acceptance remains |
| S1.2 | Plates + matcher core (shared), table-driven tests | Mon 21 | 1 h | [x] done Tue 22 (cloud); 35 tests pass; decisions F39, F40 |
| S1.3a | Registry API: app, auth + audit, schemas, cameras, health, stats, gap analysis | Mon 21 | 1.5 h | [x] done Tue 22 (cloud); 11 TestClient tests pass |
| S1.3b | CDN session, probe, seed tools, OpenAPI export — first live contact | Mon 21 | 1.5 h | |
| S2.1 | Timeline + replay frame source + frame-source test harness | Mon 21 | 1.5 h | |
| S2.2 | RTSP frame source: ffmpeg pipe + HLS tee + watchdog + backoff (the 20 s network pull in its acceptance is Adi's step) | Tue 22 | 2 h | |
| S2.3 | Motion gate, detector, tracker, model fetch with checksum | Tue 22 | 2 h | |
| S2.4 | OCR cascade, consensus voting, sightings with dedupe + provenance | Tue 22 | 2 h | |
| S2.5 | Alerts, events + zones, worker + supervisor, 10-min replay soak — **GATE A′** | Tue 22 | 3 h | |
| S3.1a | Analytics API: sightings, route, watchlist, alerts + SSE tailer, events, workers; demo seeder | Wed 23 | 1.5 h | |
| S3.1b | Reports, HLS relay, health checker; OpenAPI re-export | Wed 23 | 1.5 h | |
| S3.2 | Frontend foundation: scaffold, data layer, key dialog, IST time, Map, Cameras, Watchlist | Wed 23 | 2.5 h | |
| S3.3 | Frontend operations: Command, Live Wall, Search, Route, Alerts, Zones, Reports | Wed 23 | 3 h | |
| S3.4 | Launcher, second system over mediamtx, end-to-end walkthrough | Thu 24 | 2 h | |
| S4.1 | Live sandbox run, 10-minute measurement — **GATE B** | Thu 24 | 2 h | |
| S4.2 | HLS VOD reader + harvest for a real multi-camera route — time-boxed — **GATE C** | Thu 24 (stop 20:00) | 3 h | |
| S4.3 | Pipeline 3 evidence clips — only if S4.2 finished on Thu and S5.1–S5.3 are done by Fri noon | Fri 25 pm | 3 h | |
| S5.1 | HLD corrections + PDF | Fri 25 | 2 h | |
| S5.2 | Deck with live screenshots, links, PDF; diagram PNG | Fri 25 | 2 h | |
| S5.3 | Reports, `registry-api.json`, sample dataset, notes regenerated | Fri 25 | 1 h | |
| S5.4 | [Adi + Claude] Demo video 1 (own feed) and video 2 (government feed) | Fri 25 | 2 h | |
| S5.5 | Submission checklist walk-through, credential sweep, tag `v2.0-submission` | Fri 25 | 1 h | |
| S6.1 | Soak + fault injection; fix blockers only (the 60 s network pull is Adi's step) | Sat 26 | 3 h | |
| S6.2 | [Adi] Rehearsal, fallback footage of every screen | Sat 26 | 2 h | |
| S6.3 | [Adi] Submit; verify every link from a private window | Sun 27 | 1 h | |

Budgets total ≈ 47 h of sessions over Mon–Fri. They are session budgets, not promises: when a session overruns, the cut order below decides what goes, never the documents.

## Calendar and gates

| Day | Sessions | Gate at end of day |
|---|---|---|
| **Mon 21** | S0.2–S0.5, S1.1, S1.2, S1.3a, S1.3b, S2.1 | Schema, plate rules and registry API under test; the live probe has run once; frames from the replay source with correct timing |
| **Tue 22** | S2.2, S2.3, S2.4, S2.5 | **GATE A′**: live frames from the sandbox over RTSP with correct timing (S2.2); detector proven on real sandbox frames (S2.3) and OCR on a rendered plate (S2.4); a 10-minute replay soak with zero worker restarts (S2.5) |
| **Wed 23** | S3.1a, S3.1b, S3.2, S3.3 | The API answers every contract endpoint under auth; every screen smoke-tested; the demo seeder routes the hero vehicle in the browser |
| **Thu 24** | S3.4, S4.1, S4.2 (hard stop 20:00) | **GATE B**: real plates read from the live sandbox; the 10-minute measurements are in progress.md. **GATE C**: a plate typed into the UI returns a timestamped route across ≥ 3 cameras — the demo vehicle qualifies; a harvested real one is bonus |
| **Fri 25** | **GATE D at 09:00: documents start whatever the code state** — S5.1–S5.5; S4.3 only if its two conditions hold | Code freeze at end of day: tag `v2.0-submission` |
| **Sat 26** | S6.1, S6.2 | Soak clean; fallback footage of every screen on disk; nothing new is built after today |
| **Sun 27** | S6.3 | Submitted; every link verified from a private window. Mon 28 is buffer only |

If S0.3 shows the 28th is a **live** evaluation rather than an upload, the 48-hour rule makes Fri 25 the last build day regardless — which this calendar already respects.

## Cut order (when time runs short, cut in exactly this sequence)

1. S4.3 Pipeline 3 evidence clips (design already validated — describe it)
2. S4.2 harvest + HLS VOD reader (the demo vehicle remains the route path; absolute rule 4's HLS fallback then exists for viewing only — say so in the HLD)
3. The CDN HLS relay for non-active cameras in S3.1b (the wall then shows active cameras only; the endpoint returns a clear 404 for the rest)
4. Zones editor polish in S3.3 (keep zone events and the API)
5. Object-detection surfacing in reports (S5.3)
6. Bulk-CSV import *screen* (keep the endpoint and the add-camera form)
7. Fuzzy route candidates (keep exact + ambiguity matching)

**Never cut:** registry + map, live wall, ANPR on live feeds, sightings search, watchlist screen, alerts over SSE, route reconstruction, the add-camera form, detection report, auth, any Phase 5 document.

---

## Phase 0 — Bootstrap (Mon 21 Sep)

### S0.1 — Fresh repo with structured docs; plan written and reviewed `[x]`
Done 20–21 Sep; see progress.md R0, R1, R2.

### S0.2 — Baseline commit, ignore-rule checks, tag `docs-v0`, push `[x]`
*Read first:* nothing beyond the protocol.
*State on entry:* **the repository already exists — do not run `git init`.** `main` holds the initial commit `883b8fc` ("Initial commit", 20 Sep, the whole tree as it stood then) and is pushed to `origin` = `https://github.com/adityashroff06-code/sentinel-gujarat.git`. Everything written since (plan v2.1 → v2.2, `CLAUDE.md`, the docs, `.claude/settings.json`) may still be uncommitted when this session starts; that dirt is the documentation baseline and this task commits it — protocol step 4's clean-tree rule is waived for S0.2 only. If Adi has already committed and pushed it, the tree is clean on entry and the commit step below has nothing to do; run every check anyway and put the tag on `HEAD`.
*Build:* from the repo root:
```
git status --short --branch
grep -q "^# Archived stub" docs/reference/old-build/CLAUDE.md 2>/dev/null && git rm -qf docs/reference/old-build/CLAUDE.md   # removes the placeholder left by the v2.2 review; CONSTITUTION.md is the real content (-f: the tracked file was rewritten)
mkdir -p .claude && mv -f scripts/claude-settings.json .claude/settings.json 2>/dev/null; test -f .claude/settings.json && echo settings-ok   # the v2.2 review could not write into .claude/ and left the file in scripts/; a no-op if Adi already moved it
git add -A
git status --short
git check-ignore -v .env data/logs/api.log models/yolox_s.onnx tools/ffmpeg/bin/ffmpeg.exe
git check-ignore backend/tools/x.py ml/tools/x.py; echo "exit=$?"
git grep --cached -n -I -E "(rtsp|https?)://[^<{/ ]+:[^<{/ *]+@" -- ':!docs/tasks.md' ':!docs/reference'
git commit -m "S0.2: documentation baseline, plan v2.2"      # skip if "nothing to commit"
git tag -a docs-v0 -m "Documentation baseline, 22 Sep 2026"
git push origin main --follow-tags
git rev-parse --short main origin/main
```
*Acceptance:* `git status --short` after `git add -A` lists no `.env`, nothing under `data/` (the three committed data files are unchanged since `883b8fc`, so they do not appear), nothing under `models/` or `tools/`; `check-ignore -v` prints four lines (one per path); the second `check-ignore` prints nothing and `exit=1` (the packages `backend/tools/` and `ml/tools/` are **not** ignored); the `git grep` prints nothing; `docs/reference/old-build/` contains `CONSTITUTION.md` and no `CLAUDE.md`; `settings-ok` was printed and `scripts/claude-settings.json` no longer exists; after the commit `git status` is clean, `git tag` lists `docs-v0`, and `git rev-parse` prints the same hash twice — `main` and `origin/main` on one commit, so the push succeeded (if the push asks for credentials, stop and tell Adi; never type or store a token).
*Write-off:* progress block S0.2 (the first block after R3).

### S0.3 — [Adi] Confirm the 28 Sep milestone and the entry category `[ ]`
*Build:* open the portal / registration email; record in `docs/brief.md` §0 what the 28th is (upload deadline? live evaluation? both?) and the registered category; update `docs/decisions.md` O8 and, if the 28th is a live evaluation, note in the Calendar that Fri 25 is the last build day.
*Acceptance:* both facts written with the source (page or email) named; committed.

### S0.4 — Environment check (`scripts/doctor.py`); `.env` is Adi's, created before this session `[~]`
*Read first:* `docs/sandbox-findings.md` §7 (library behaviours); `.env.example`.
**[Adi] before the session starts — not a Claude step:** in `D:\projects\sentinel-gujarat`, `copy ..\Sentinel_Repo\.env .env`, then append the two new lines `SENTINEL_API_KEY_ADMIN=<long random>` and `SENTINEL_API_KEY_VIEWER=<long random>` (`python -c "import secrets;print(secrets.token_urlsafe(32))"` twice). The old `.env` carries the sandbox login and endpoints; the new `.env.example` documents every other variable's default, so nothing else is required. **The Claude session never reads, creates or edits `.env`** — `.claude/settings.json` denies it — so if the file is missing when the session runs, the doctor says so, the session writes S0.4 off as `PARTIAL` with `Next: Adi creates .env, then re-run python scripts/doctor.py and paste the output`, and S1.1 may start anyway (nothing before S1.3b's first live contact needs the real credentials; the tests set their own throw-away keys and database path in `conftest.py`, never reading `.env`).
*Build:* `scripts/doctor.py` — prints, **changing nothing**: Python version and path; `node --version` (must be ≥ 20.19) and `npm --version`; `ffmpeg -version` / `ffprobe -version` first lines and which path answered (PATH, or `SENTINEL_FFMPEG_DIR`, or the default `D:\projects\Sentinel_Repo\tools\ffmpeg\ffmpeg-master-latest-win64-gpl\bin`); `nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv`; whether `.env` exists and which variable **names** it sets (never values — the script reads the file itself; the session does not open it); whether `D:\projects\Sentinel_Repo` is reachable. Uses only the standard library so it runs before the venv exists.
*Acceptance:* `python scripts/doctor.py` (Anaconda python; the venv does not exist yet) prints every line without a traceback; ffmpeg and ffprobe resolve; Node ≥ 20.19; GPU line shows the GTX 1650; `.env` present with `SENTINEL_EMAIL`, `SENTINEL_PASSWORD`, `SENTINEL_API_KEY_ADMIN`, `SENTINEL_API_KEY_VIEWER` set (names only in the output).
*Write-off:* paste the doctor output (it contains no secrets) into the progress block.

### S0.5 — [Adi] Insurance recording of the old build `[ ]`
*Build:* `python launch.py` in `D:\projects\Sentinel_Repo`, then `python launch.py demo`; screen-record Command, Map, Live Wall, Search, Route (`GJ01AB1234`), Alerts, Reports — 3–5 minutes, no narration needed. Save outside both repos (e.g. `D:\projects\sentinel-media\insurance-old-build.mp4`).
*Acceptance:* the file plays; nothing on screen shows a credential (check the address bar and any terminal).

---

## Phase 1 — Backend foundations (Mon 21 Sep)

### S1.1 — Backend skeleton, venv, config, logging, schema v1, migrations, contract folded, tests `[~]`
*Read first:* `docs/api.md` (all of Part A and all of Part B — Part B is folded into Part A in this task); `docs/decisions.md` F12, F13, F21, F22–F30, F37; `backend/CLAUDE.md`. The version pins are **in this task block**, not in the old repo's `requirements.txt` (that file pins only the two Paddle packages; the versions below were read off the old `.venv`'s installed distributions on 21 Sep — the set that actually ran the 15 Sep demo on this laptop, Python 3.13.9).
*Build:*
- **Environment:** `python -m venv .venv` (Anaconda python), then `.venv/Scripts/python -m pip install -r requirements.txt -r requirements-dev.txt`. `requirements.txt` is **exactly this** (decision F37):
  ```
  fastapi==0.141.1
  uvicorn[standard]==0.53.0
  python-multipart==0.0.32
  python-dotenv==1.2.3
  httpx==0.28.1
  pydantic==2.13.5
  numpy==2.3.5
  opencv-contrib-python==4.10.0.84
  Pillow==12.3.0
  cryptography==50.0.1
  psutil==7.2.2
  onnxruntime-directml==1.24.4; sys_platform == "win32"
  onnxruntime==1.24.4; sys_platform != "win32"
  paddlepaddle==3.3.1
  paddleocr==3.7.0
  paddlex==3.7.2
  ```
  **One OpenCV distribution, and it is the contrib one.** The old `requirements.txt` said `opencv-python` (unpinned → 5.0.0.93) while PaddleOCR's dependency chain (`paddlex`) pins `opencv-contrib-python==4.10.0.84`; both wheels unpack into the same `cv2/` folder (49 files in common) and the contrib wheel, installed last, is the one whose `cv2.pyd` actually ran. Listing `opencv-python` here would repeat that clobbering, so it is **not** listed and must never be added (nor `opencv-python-headless`); `opencv-contrib-python` is a superset of `opencv-python`. Likewise the plain `onnxruntime` wheel must never be installed on Windows — it shares the `onnxruntime/` folder with the DirectML wheel and silently replaces it (the old launcher had to force-reinstall `onnxruntime-directml` for this reason); the environment markers above keep it off the laptop. `requirements-dev.txt`: `pytest`, `pytest-timeout`, `playwright` — after the first install, pin each to the version `pip freeze` shows, in the same commit. Hash-locking is deferred (decision F6 amended in F24).
- **Layout** (decision F12): `backend/__init__.py`, `backend/core/{__init__,config,logging_setup,db,timeline}.py` (timeline is a stub until S2.1), `backend/core/migrations/0001_initial.sql`, `backend/app/__init__.py` (empty until S1.3a), `tests/conftest.py`, `pytest.ini` (`pythonpath = .`, `testpaths = tests`, `timeout = 120`), `CHECKSUMS.txt` at the repo root (empty header now; every downloaded binary's SHA-256 lands here: mediamtx, ffmpeg zip if fetched, `yolox_s.onnx`).
- `config.py`: loads the repo-root `.env` with `python-dotenv` (`override=False`, so a real environment variable wins; tests point `SENTINEL_DB` elsewhere), then reads every variable in `.env.example` with its documented default — the file already lists the new ones: `SENTINEL_API_KEY_ADMIN`, `SENTINEL_API_KEY_VIEWER`, `SENTINEL_LOG_DIR`, `SENTINEL_FFMPEG_DIR`, `SENTINEL_ALERT_ON_FUZZY`, `SENTINEL_STALL_TIMEOUT_S`, `SENTINEL_RECORDING_EPOCH`, `SENTINEL_CAPTION_BAND`. `ffmpeg()` / `ffprobe()` return the executable path (`SENTINEL_FFMPEG_DIR` → PATH → raise with a clear message). `masked(s)` masks **any** `scheme://user:pass@` userinfo generically and additionally scrubs the env email and password (raw and percent-encoded) anywhere in the string.
- `logging_setup.py`: `setup(name)` → rotating file `data/logs/<name>.log` (5 × 10 MB) plus stderr; level from `SENTINEL_LOG_LEVEL`; the masking function applied to every record.
- `db.py`: `connect()` with WAL, `foreign_keys=ON`, `busy_timeout=30000`, `synchronous=NORMAL`; `migrate()` applying `migrations/*.sql` in order and recording them in `schema_version`; `.venv/Scripts/python -m backend.core.db init`.
- **Schema v1** = Part A folded with Part B, exactly this:
  - `cameras` as §1, `transport` ∈ `hls | rtsp | replay | none` (for `replay`, `rtsp_url_template` holds the local file path), plus `source`, `ownership` as already there.
  - `sightings` as §2 **plus** `wall_time TEXT NOT NULL`, `clock_source TEXT NOT NULL` (`rtsp-live | hls-vod | harvest | demo | replay`), `provenance TEXT NOT NULL` (`live | harvest | demo | test`), `plate_canonical TEXT NOT NULL`, index `(plate_canonical, seen_at)`; `seen_at` keeps its name and means the **stream-time instant**; `bbox_json` stays `[x, y, w, h]` in source pixels (the detector's xyxy is converted at write); `vehicle_class` ∈ `car | truck | bus | motorcycle | auto | unknown` (the detector emits the first four or `unknown`).
  - `watchlist` as §3 plus `plate_canonical TEXT NOT NULL` (indexed), `reason`, `authority`, `expires_at` (nullable).
  - `alerts`: `alert_seq INTEGER PRIMARY KEY AUTOINCREMENT`, `alert_id TEXT NOT NULL UNIQUE`, `kind TEXT NOT NULL` (`watchlist | zone`), `sighting_id INTEGER NULL REFERENCES sightings`, `watchlist_id INTEGER NULL REFERENCES watchlist`, `event_id INTEGER NULL REFERENCES events`, `zone_id TEXT NULL`, `plate TEXT NULL`, `plate_canonical TEXT NULL`, `camera_id TEXT NOT NULL REFERENCES cameras`, `category TEXT NULL`, `severity TEXT NOT NULL`, `match_type TEXT NOT NULL DEFAULT 'none'` (`exact | ambiguity | fuzzy | none`), `match_distance REAL NOT NULL DEFAULT 0`, `clock_source TEXT NOT NULL`, `fired_at TEXT NOT NULL` (stream time), `acknowledged_at`, `acknowledged_by`, `clip_path`, `clip_sha256`; index `(fired_at)`, `(plate_canonical, camera_id, fired_at)`.
  - `events` as §5 plus `wall_time`, `clock_source`, `provenance`; indexes `(occurred_at)` and `(camera_id, occurred_at)`.
  - `audit(audit_id INTEGER PK AUTOINCREMENT, at TEXT NOT NULL, actor TEXT, role TEXT, action TEXT NOT NULL, entity TEXT, entity_id TEXT, before_json TEXT, after_json TEXT)` — `before_json`/`after_json` are written by the handlers, not by middleware.
  - `schema_version(version INTEGER PK, applied_at TEXT)`.
  - Zones canonical shape (api.md B1): `type` ∈ `intrusion | line`, `severity`, `points` — written into §5.
- **Fold Part B into Part A** of `docs/api.md`: rewrite §1–§7 to the schema above, including §6 = the plate grammar and matching rules exactly as `docs/api.md` B10 states them (S1.2 implements them; do not invent a second version), the route response's `match_distance`, `suspect` and `warnings[]`, the endpoints of B3, the auth transport of B12 (header **or** session cookie for GET on `/crops/*`, `/api/hls/*`, `/api/alerts/stream`; mutations always need the header), and the provenance rule. Then put a banner above Part B — "**Resolved in S1.1 on <date> — historical; Part A is binding**" — and keep Part B's text (other docs cite its item numbers). From this commit on, Part A alone is binding.
*Acceptance:* `.venv/Scripts/python -m pip check` prints `No broken requirements found.`; `.venv/Scripts/python -m pip list | grep -i -E "opencv|onnxruntime"` prints exactly two lines — `opencv-contrib-python 4.10.0.84` and `onnxruntime-directml 1.24.4` (no `opencv-python`, no plain `onnxruntime`); `.venv/Scripts/python -c "import cv2, onnxruntime as o; print(cv2.__version__, o.__version__, o.get_available_providers())"` prints `4.10.0 1.24.4 [...]` with `DmlExecutionProvider` in the list (a Paddle import is not required here; S2.4 proves OCR); `.venv/Scripts/python -m backend.core.db init` creates `data/sentinel.db`; `.venv/Scripts/python -m pytest tests/test_schema.py -q` passes a test that asserts every table, column, enum default and index above (write it); `.venv/Scripts/python -c "from backend.core import config; print(config.masked('rtsp://user%40x.y:secret' + '@1.2.3.4:8554/x'))"` prints `rtsp://<email>:***@1.2.3.4:8554/x`; `config.ffmpeg()` returns an existing path on the laptop; a log file appears under `data/logs/` when `setup("test")` is called; `git check-ignore .venv data/sentinel.db` prints both paths.
*Write-off:* progress block; note the schema version and the api.md sections rewritten.

### S1.2 — Plates + matcher core (shared) `[x]`
*Read first:* `docs/api.md` §6 (as rewritten in S1.1); `docs/decisions.md` F21; `docs/sandbox-findings.md` §5 (what real reads look like).
*Build:* `backend/core/plates.py` — one module, no duplicates anywhere else:
- `normalise(raw)`: uppercase, strip non-`A-Z0-9`.
- `canonical(plate)`: fold the ambiguity map to a canonical form (`O→0, I→1, S→5, B→8, Z→2, G→6, Q→0`) for indexing.
- `plate_like(s) -> "full" | "partial" | None`: **full** = standard `^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{4}$` **or** BH-series `^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$`, after position-aware ambiguity coercion (where a letter is expected map `0→O, 1→I, 5→S, 8→B, 2→Z, 6→G`; where a digit is expected map the reverse) and a state-code whitelist for the standard form (`AN AP AR AS BR CG CH DD DL DN GA GJ HP HR JH JK KA KL LA LD MH ML MN MP MZ NL OD OR PB PY RJ SK TN TR TS UK UP WB`); **partial** = a structural prefix of either form (no coercion) with length ≥ 4 that is not full; None otherwise.
- `is_partial(s)`: `plate_like(s) != "full"`.
- `plate_match(a, b) -> (matched: bool, distance: float, rule: "exact" | "ambiguity" | "fuzzy" | "none")`: exact → ambiguity-equal (same length, differs only inside ambiguity classes) → confusion-weighted edit distance where a substitution inside an ambiguity class costs 0.25 and any other substitution or indel costs 1.0; **fuzzy requires both sides `full`** and weighted distance ≤ 1.0. Partial reads never fuzzy-match.
- `backend/core/matcher.py`: `WatchlistCache` (rows + canonical index; `refresh(con)` every 10 s by the caller), `find_match(plate) -> (watchlist_row, rule, distance) | None`: index probe on `plate_canonical` first, then fuzzy only over candidates sharing the first 4 canonical characters; alertable = rule in (`exact`, `ambiguity`) or (`fuzzy` and `SENTINEL_ALERT_ON_FUZZY`).
*Acceptance:* `.venv/Scripts/python -m pytest tests/test_plates.py -q` passes a **table-driven** test covering: normalise; each ambiguity pair; `GJ01AB1234` vs `GJ01A81234` → `ambiguity`, distance 0; `GJ01AB1234` vs `GJ01AB1235` → `fuzzy`, distance 1.0, not alertable by default; `GJ05JB432` → `partial`, and `plate_match("GJ05JB432", "GJ05JB4321")` → `none`; `22BH1234AA` → `full`; `OADFIX2FR` and `DFIX2F` → None; `GJ32 K 9819` normalises to `GJ32K9819` → `full`; matcher index probe finds an exact canonical hit among 1,000 synthetic rows in < 5 ms.
*Write-off:* progress block with the test count.

### S1.3a — Registry API: app, auth + audit, schemas, cameras, health, stats, gap analysis `[x]`
*Read first:* `docs/api.md` §1, §7 (cameras, health, stats, gap-analysis, stream, import; the auth transport rule); `backend/CLAUDE.md`; old code for reference only: `D:\projects\Sentinel_Repo\src\api\routes_cameras.py`, `src\api\schemas.py`.
*Build:*
- `backend/app/main.py` (FastAPI app; CORS to `http://localhost:5173`; `TrustedHostMiddleware` for `localhost`, `127.0.0.1`; routers; `/crops` static behind auth; SPA fallback serving `frontend/dist` when present — `/`, `/assets/*`, `/docs`, `/openapi.json`, `/api/health` are open) and `backend/app/__main__.py` (`uvicorn` on `SENTINEL_API_PORT`).
- `backend/app/auth.py`: dependency that accepts `X-API-Key` **or**, for `GET` on `/crops/*`, `/api/hls/*` and `/api/alerts/stream`, the cookie `sentinel_key`; roles `viewer`/`admin` from the two configured keys; mutations require the header (a cookie alone never authorises a change) **and** admin. `POST /api/session` validates a key and sets the cookie (`SameSite=Strict`, `HttpOnly`, path `/`); `DELETE /api/session` clears it. The API refuses to start if either key is unset.
- `backend/app/audit.py`: middleware writing an `audit` row for every non-GET request and every `GET /api/plates/*` and `GET /api/sightings*`; handlers pass `before/after` through `request.state.audit`.
- `backend/app/schemas.py`: Pydantic request **and response** models for every endpoint in this task (response models are what makes the exported OpenAPI real).
- `backend/app/routes_cameras.py` (register `/gap-analysis` and `/import` **before** `/{camera_id}` — FastAPI route-order trap), `routes_meta.py` (`/api/health` open; `/api/stats` with the keys in api.md), `backend/services/gap_analysis.py` (nearest-neighbour Haversine, offline/degraded durations, department summary).
- `camera_id` pattern `^[A-Za-z0-9_-]{1,64}$`; `rtsp_url_template` may contain `<email>`/`<password>` placeholders (filled from env in memory) **or** be a plain local URL (used as is) — both accepted; no stored URL ever contains a credential; `GET /api/cameras/{id}/stream` returns only `/api/hls/{id}/live.m3u8`.
- `POST /api/cameras/import`: CSV upload, per-row `accepted[] / rejected[]{row, reason}`, validated in one transaction (no partial commit). Write `tests/fixtures/import_3rows.csv` (two valid rows, one with an out-of-range latitude) — S3.2's smoke test reuses it.
*Acceptance:* `.venv/Scripts/python -m pytest tests/test_registry_api.py -q` passes tests with `TestClient(app, base_url="http://localhost")` (the default `testserver` Host is rejected by `TrustedHostMiddleware` — put the client in `conftest.py`) for: 401 without key; 403 for viewer on POST; cookie accepted on `GET /crops/x.jpg` (404 for a missing file, not 401) but refused on POST; 201 manual create; 409 duplicate; 422 bad department / lat; CSV import of 3 rows with one bad row → 2 accepted, 1 rejected with a reason, the bad row absent; PATCH; gap-analysis shape; stats keys; an `audit` row written for the POST with `after_json`; `/api/health` open.
*Write-off:* progress block.

### S1.3b — CDN session, probe, seed tools, OpenAPI export — first live contact `[ ]`
*Read first:* `docs/sandbox-findings.md` §1–§3; `docs/reference/sandbox-access-spec.md` §1; `docs/decisions.md` C6, C8, C9, C11; old code for reference only: `D:\projects\Sentinel_Repo\src\tools\probe.py`, `src\ingest\session.py`, `src\tools\seed_registry.py`, `src\tools\seed_watchlist.py`.
*Build:*
- `backend/core/cdn_session.py`: form login to `/auth/login` (fields `email`, `password`), cookie jar, browser-like User-Agent, retry with jittered backoff and one re-login on 403/timeouts, `get(url)` helper — shared by probe, relay (S3.1b) and harvest (S4.2). Every log line masked.
- `backend/tools/probe.py`: fetch `cameras.json` → `data/cameras_raw.json`; per camera ffprobe RTSP (`-rtsp_transport tcp`, 20 s timeout, **4 at a time** — respect the suspected session cap) and an HLS playlist head via the session; write registry rows (`transport` = `rtsp` if RTSP ok, else `hls`, else `none`; `health`, `last_seen`, codec/resolution/declared fps); results to `data/probe_results_<YYYYMMDD>.json`, masked (the 14 Sep file stays as evidence); never overwrite department/coordinates/tier that the seed set.
- `backend/tools/seed_registry.py`: **upsert every id from `data/cameras_raw.json`** (`transport='none'`, `source='catalogue'` until the probe fills them — so a fresh database gets all 30 rows without the probe), then apply `data/camera_seed.csv` (department, location, lat/lon, tier) and print the acceptance line (active count, departments spanned, `ACCEPTANCE: PASS/FAIL`). Options: `--add <id> <department> <url> [--tier active]` for a manual/local camera, `--replay <file> <id>…` for `transport='replay'` rows (S2.5's soak).
- `backend/tools/seed_watchlist.py`: idempotent; 25 invented entries across all categories and severities (with `reason`, `authority`, `source_ref`); `--from-sightings N` adds observed full plates; `GJ01AB1234` present as `stolen_vehicle / high` (the demo hero).
- `backend/tools/export_openapi.py` → `deliverables/registry-api.json`.
*Acceptance:* on the laptop, with `.env` present: `.venv/Scripts/python -m backend.tools.seed_registry` on an empty database creates 30 rows and prints `ACCEPTANCE: PASS` with 5 active cameras across 5 departments; `.venv/Scripts/python -m backend.tools.probe` finishes and prints a summary with ≥ 20 RTSP-live cameras (sandbox permitting — record the number and any 403s); `.venv/Scripts/python -m backend.tools.seed_watchlist` twice leaves exactly the same 25 rows; `.venv/Scripts/python -m backend.tools.export_openapi` writes `deliverables/registry-api.json` and `.venv/Scripts/python -m pytest tests/test_openapi.py -q` asserts every operation has a description and a response schema and that no `snapshot.jpg` path exists.
*Write-off:* progress block with the live camera count observed.

---

## Phase 2 — Ingestion and ANPR (Mon 21 – Tue 22 Sep)

### S2.1 — Timeline + replay frame source + frame-source test harness `[ ]`
*Read first:* `docs/feed-rules.md` (all, especially "Required behaviour of frame_source.py" — the fresh build's name for that module is `ml/ingest/`); `docs/sandbox-findings.md` §2, §4; `docs/decisions.md` F13, F20, F29; `ml/CLAUDE.md`.
*Build:*
- `backend/core/timeline.py` (decision F13): `RECORDING_EPOCH` from `SENTINEL_RECORDING_EPOCH` (default `2026-06-13T21:00:00+05:30` — a demo constant anchoring the recordings' burned-in clock, not a claim about the footage), `LOOP_SECONDS` (default 43200), `position_to_stream_time(offset_s)`, `stream_time_to_position(ts)`, `live_position(now)` honouring `SENTINEL_PLAYBACK_OFFSET_S` and the loop length; pure functions, unit-tested.
- `ml/ingest/base.py`: `FrameTick(frame, pts_ms, stream_time, wall_time, clock_source, restart: bool)` — `stream_time` is the in-memory name of what is stored as the `seen_at` column; an abstract `FrameSource` with `frames()` generator, `close()`, and the shared **sampler** that drops on PTS to hit the target fps (never sleeps).
- `ml/ingest/replay.py`: reads a local file through ffmpeg (`-re -stream_loop -1 -i <file> -map 0:v:0 -an -vf fps=<n> -pix_fmt bgr24 -f rawvideo pipe:1`), reader thread, `pts_ms = index / fps`, **`stream_time = wall_time = pull_start + pts` — continuous across loops** (with `-stream_loop` the pipe's PTS never resets); **wrap detection** via the file's duration from `ffprobe`: when `index/fps` crosses `k × duration` emit one tick with `restart=True` (the tick tells trackers and the motion gate to reset; it does not touch the clock), `clock_source="replay"`, jittered backoff on process death, `try/finally` kill. ffmpeg/ffprobe via `config.ffmpeg()`/`ffprobe()`.
- Backoff lives in `base.py` and is shared: `attempt n` → `base = min(2 · 2ⁿ, 30)` s, `delay = base · random(0.5, 1.5)`; **log all three** (`attempt`, `base`, `delay`) on one line so tests assert on `base` doubling, not on jittered values; `n` resets after 30 s of healthy frames. `base.py` also holds a shared **scene-cut detector** (mean absolute difference of two consecutive down-scaled grey frames above a threshold → `restart=True`), used by every source for the sandbox's loop cut (feed rule 8).
- `tests/fixtures/make_synthetic.py`: generates `tests/fixtures/synthetic_60s.mp4` (60 s, 640×360, 25 fps) with ffmpeg lavfi (`testsrc2` plus a `drawbox` that moves across the frame) if missing; conftest calls it.
- `tests/test_frame_source.py`: the harness used again by S2.2 — parametrised over sources.
*Acceptance:* `.venv/Scripts/python -m pytest tests/test_timeline.py tests/test_frame_source.py -q` passes: 100 consecutive frames at 3 fps with strictly increasing `stream_time`; sampling at 3 fps over a 20 s window yields 60 ± 15 % frames with a PTS span of ~20 s; looping the 60 s clip for 130 s emits ≥ 2 `restart` ticks and `stream_time` is monotonic across the whole run; pointing the source at a non-existent file for 3 attempts logs `base` = 2, 4, 8 s with each `delay` within [0.5×, 1.5×] of its base (test with a patched sleep), then killing the ffmpeg child mid-read of the real clip makes frames resume; the scene-cut detector fires on a black→white frame pair and not on two identical frames.
*Write-off:* progress block with the four observed numbers.

### S2.2 — RTSP frame source: ffmpeg pipe + HLS tee + watchdog + backoff `[ ]`
*Read first:* `docs/feed-rules.md`; `docs/sandbox-findings.md` §3, §7; `docs/decisions.md` §3 "Ingestion", F25; `ml/CLAUDE.md`; old reference: `D:\projects\Sentinel_Repo\src\ingest\frame_source.py` class `RtspFrameSource` (the pipe + tee recipe that worked).
*Build:*
- `ml/ingest/rtsp.py`: one ffmpeg process per camera — `-nostdin -hide_banner -loglevel warning -rtsp_transport tcp -rw_timeout 15000000 -i <url>` with two outputs: `-map 0:v:0 -an -vf fps=<n> -pix_fmt bgr24 -f rawvideo pipe:1` and `-map 0:v:0 -an -c:v copy -f hls -hls_time 2 -hls_list_size 10 -hls_flags delete_segments+omit_endlist+independent_segments -hls_segment_filename data/hls/<cam>/seg%06d.ts data/hls/<cam>/index.m3u8`; reader thread keeps only the latest frame (a slow pipeline never back-pressures the pull); `stream_time = wall_time = pull_start + pts`, `clock_source="rtsp-live"`; **stall watchdog** (no frame for `SENTINEL_STALL_TIMEOUT_S` → kill child → backoff → restart with `restart=True`); jittered exponential backoff (2 s · 2ⁿ · random(0.5, 1.5), cap 30 s); decoder warnings from stderr logged at DEBUG; the URL built in memory from the template + env and **never logged unmasked** (assert in a test that the masked form appears in logs and the raw never does); `try/finally` kill; tee directory cleaned on close.
- `ml/ingest/__init__.py`: `for_camera(row)` dispatch on `transport` (`rtsp` → this; `replay` → S2.1; `hls` → S4.2, until then a clear `NotImplementedError`).
- `ml/tools/smoke_rtsp.py <camera_id> --seconds N`: pulls one registry camera and prints frame count, first/last `stream_time`, tee state.
- `scripts/replay_publish.py`: `--fetch` downloads the MIT-licensed mediamtx Windows release zip (latest v1.x) into `tools/mediamtx/` and records version, URL and SHA-256 in `CHECKSUMS.txt` (verifies on every later run); without `--fetch` it starts mediamtx and publishes a file over RTSP (`ffmpeg -re -stream_loop -1 -i <file> -c:v libx264 -preset veryfast -f rtsp rtsp://127.0.0.1:8554/stream/<name>`) — reused by S3.4.
*Acceptance:* the S2.1 harness, parametrised with `ml/ingest/rtsp.py` reading `rtsp://127.0.0.1:8554/stream/test` published by `scripts/replay_publish.py` (the monotonic, sampling and backoff cases; the wrap-tick case is replay-only — a re-encoded RTSP loop has continuous PTS), passes; then **on the laptop against the live sandbox**: `.venv/Scripts/python -m ml.tools.smoke_rtsp cam06 --seconds 60` prints ≥ 100 frames with monotonic stream_time, the tee playlist `data/hls/cam06/index.m3u8` lists ≤ 10 segments and the segment files on disk stay bounded (≤ 25) over 2 minutes, `ffprobe` on the **newest** segment shows h264; then the network pull — **[Adi] step, not Claude's** (a session cannot unplug the laptop, and cutting the network cuts Claude Code off too): the session starts `.venv/Scripts/python -m ml.tools.smoke_rtsp cam06 --seconds 180` detached with its output going to `data/logs/smoke_rtsp.log`, tells Adi "pull now", and Adi turns Wi-Fi off for 20 s and back on; when Claude Code is reachable again the session reads that log, which must show the child exiting (`-rw_timeout`) or the watchdog killing it, then backoff lines with `base` doubling (2, 4, 8 … capped at 30) and jittered `delay`, then frames resuming. If Adi is not at the keyboard, this one check is written off as `PARTIAL` (`Next: Adi's 20 s network pull, then read data/logs/smoke_rtsp.log`) and everything else in the task is still judged on its own evidence.
*Write-off:* progress block with the observed frame count, tee state and backoff delays.

### S2.3 — Motion gate, detector, tracker, model fetch with checksum `[ ]`
*Read first:* `docs/sandbox-findings.md` §5, §7; `docs/decisions.md` §3 "Ingestion", F14; `ml/CLAUDE.md`; old reference: `D:\projects\Sentinel_Repo\src\anpr\{detect,motion,track}.py`, `src\tools\fetch_models.py` (the YOLOX-S release URL).
*Build:*
- `ml/tools/fetch_models.py`: download YOLOX-S ONNX to `models/yolox_s.onnx`; on first download compute SHA-256 and append it to `CHECKSUMS.txt` (committed); later runs verify and refuse a mismatch.
- `ml/anpr/motion.py`: MOG2 gate, per-camera threshold (registry `notes` JSON or config default), `reset()` on restart.
- `ml/anpr/detect.py`: ONNX Runtime session (providers `DmlExecutionProvider` then CPU; log which); letterbox to 640; **one lock around `session.run()`**; per-class NMS; classes kept: person, bicycle, car, motorcycle, bus, truck, backpack, handbag; `superclass()` mapping car/truck/bus/motorcycle → `vehicle`; ROI mask from `roi_json` applied before inference; caption band exclusion (`SENTINEL_CAPTION_BAND`, default 0.05 = top 5 %); returns `Detection(cls, superclass, conf, xyxy)`.
- `ml/anpr/track.py`: greedy IoU + centre-distance tracker matching on **superclass**, velocity from PTS deltas, `max_age`, `Track(id, boxes, last_seen_pts, ocr_reads[])`; reset on restart.
*Acceptance:* `.venv/Scripts/python -m pytest tests/test_detect.py tests/test_track.py -q`: detector on `deliverables/deck/img/feed_cam01.jpg` returns ≥ 3 vehicles (record the count and the provider used); on a black frame returns 0; motion gate skips ≥ 90 % of identical frames and passes the synthetic moving box; tracker keeps one id for the synthetic box across 30 frames and across a car→truck class flip; ROI mask zeroes detections outside the polygon; `fetch_models` refuses a tampered file. On the laptop record detector latency on DirectML (expect ~50 ms).
*Write-off:* progress block with counts, provider and latency.

### S2.4 — OCR cascade, consensus voting, sightings with dedupe + provenance `[ ]`
*Read first:* `docs/sandbox-findings.md` §5, §7; `docs/api.md` §2 (as rewritten); `docs/decisions.md` §3; `ml/CLAUDE.md`; old reference: `D:\projects\Sentinel_Repo\src\anpr\{ocr,pipeline,sightings}.py`.
*Build:*
- `ml/anpr/ocr.py`: PaddleOCR with `PP-OCRv5_mobile_det` / `en_PP-OCRv5_mobile_rec`, `enable_mkldnn=False`, models under `models/paddle/` where the library allows (else document the `~/.paddlex` path in the progress block); one lock around init + predict; input = vehicle crop → upscale to ~400 px wide (≤ 4×) + CLAHE → OCR → for each text region: `plate_like()` gate, confidence, quad → bbox **mapped back to source-frame pixels as `[x, y, w, h]`**.
- `ml/anpr/pipeline.py`: per frame: motion gate → detector → tracker → OCR budget (skip tracks with a `full` consensus; ≥ 1.5 s between reads per track; ≤ 2 crops per frame, largest first) → **consensus voting** per track (per-character majority weighted by confidence over the track's reads; a read is committed when ≥ 2 reads agree or the track dies with ≥ 1 full read) → sighting; object-event and zone-event hooks (filled in S2.5). Returns `FrameResult`.
- `ml/anpr/sightings.py`: `record_sighting(con, …)` — dedupe: an existing row with the same `plate_canonical` on the same camera whose `seen_at` is within 60 s of the new read **and** whose `wall_time` is within 10 min of the new read's `wall_time` → update confidence if better (never insert); otherwise insert; crop saved as JPEG ~2 KB under `data/crops/<cam>/`, path with forward slashes; writes every §2 column including `wall_time`, `clock_source`, `provenance` (the caller's value — `live` for real pulls, `test` for replay, `demo` for the seeder), `pts_ms`, `bbox_json`, `vehicle_class`, `track_id`.
*Acceptance:* `.venv/Scripts/python -m pytest tests/test_ocr.py tests/test_sightings.py -q`: a plate image rendered with PIL (`GJ01AB1234`, 22 px high inside a 90 px crop) reads as `GJ01AB1234` or its ambiguity-equivalent; a caption-band string is rejected; consensus over reads `[GJ01AB1234, GJ01A81234, GJ01AB1234]` yields `GJ01AB1234`; dedupe matrix (same plate 30 s later → 1 row with the higher confidence; 61 s later → 2 rows; a read whose `seen_at` is 30 s away but whose `wall_time` is 20 min earlier → separate row); a partial read is stored and never alertable; every row carries the provenance the caller gave. On the laptop: OCR latency per crop recorded (expect ~0.45 s).
*Write-off:* progress block.

### S2.5 — Alerts, events + zones, worker + supervisor, 10-minute replay soak — GATE A′ `[ ]`
*Read first:* `docs/api.md` §3–§5 (as rewritten); `docs/decisions.md` §3 "Backend" and "Ingestion", F21, F26; `docs/sandbox-findings.md` §7 (SQLite, DirectML, process model); `ml/CLAUDE.md`; old reference: `D:\projects\Sentinel_Repo\src\ingest\worker.py`, `src\alerting\matcher.py`, `src\analytics\zones.py`.
*Build:*
- `backend/core/alerts.py`: `create_alert(con, *, kind, camera_id, severity, seen_at, clock_source, sighting=None, wl_row=None, rule="none", distance=0.0, event=None)` — cooldown 5 min per (`plate_canonical`, `camera_id`) for watchlist alerts and per (`zone_id`, `camera_id`) for zone alerts (both columns exist on `alerts`), **derived from the last matching `alerts` row with the same `clock_source`** (never in-memory, so a purge resets it); insert with `alert_seq` autoincrement and `alert_id = ALERT-YYYYMMDD-NNNN` derived from `alert_seq`; returns the row.
- `ml/analytics/events.py`: object events per camera per class throttled (≥ 5 s apart), **batched** through the writer thread, best-effort; throttle reset on restart. `ml/analytics/zones.py`: canonical zone shape; polygon entry (foot point) fires once per track; line crossing with direction (down = +y) fires once; high-severity zone hit → `create_alert(kind="zone", …)` with `event_id`.
- `ml/worker.py`: `CameraWorker` thread — `for_camera` source → pipeline → `record_sighting` → `matcher.find_match` → `create_alert` → events. **All writes go through the supervisor's single writer thread**: sightings and alerts are submitted as jobs and awaited (a `Future`; the sighting is committed before the match runs, the alert before anything broadcasts); events are enqueued as async batches. The writer retries a transient lock; a worker never dies on a DB error — it logs, skips the frame, continues; captures closed in `finally`.
- `ml/supervisor.py` + `ml/__main__.py`: reads the active tier from the registry (`transport IN ('rtsp','replay')`, `fps_tier='active'`, capped at `SENTINEL_ACTIVE_CAMERAS` concurrent pulls), never two workers on one camera, restarts a dead worker with damping, **single DB writer thread** (`BEGIN IMMEDIATE`) that all workers enqueue into, refreshes the watchlist cache and zones every 10 s, writes `data/worker_stats.json` atomically every 10 s (`frames, fps_sustained, inferred, motion_skip_rate, detections, detections_per_min, sightings, alerts, zone_events, uptime_s, restarts, rss_mb`), graceful stop on SIGINT or a `data/stop` file, own-process-tree kill via psutil.
*Acceptance:* `.venv/Scripts/python -m pytest tests/test_alerts.py tests/test_zones.py -q`: a sighting for a watchlisted plate → exactly one alert; four more within 5 min (stream time) → still one; a partial read → none; `GJ01AB1235` vs watchlisted `GJ01AB1234` → none by default; **purge all alerts then a new sighting → a new alert with a fresh `alert_seq`** (regression for D4); zone entry fires once; line cross fires downward only; high-severity zone → alert `kind='zone'` with `event_id` set and `sighting_id` null. Then the **replay soak** on a separate database (bash; inline env): `SENTINEL_DB=data/soak.db .venv/Scripts/python -m backend.core.db init`, `SENTINEL_DB=data/soak.db .venv/Scripts/python -m backend.tools.seed_registry --replay tests/fixtures/synthetic_60s.mp4 replay01 replay02 replay03` (and one real-vehicle clip if Adi has recorded one), then `SENTINEL_DB=data/soak.db .venv/Scripts/python -m ml` for **10 minutes**: 0 worker restarts, uniform uptime, `rss_mb` growth < 100 MB over the run, stats file updated every 10 s, ≥ 2 `restart` ticks handled per camera, every sighting `provenance='test'`. The working database `data/sentinel.db` is untouched.
*Write-off:* progress block with the soak numbers → this is GATE A′.

---

## Phase 3 — Analytics API, frontend, launcher (Wed 23 – Thu 24 Sep)

### S3.1a — Analytics API: sightings, route, watchlist, alerts + SSE tailer, events, workers; demo seeder `[ ]`
*Read first:* `docs/api.md` §7 (as rewritten) and the route response; `backend/CLAUDE.md`; `docs/decisions.md` C10, C15, F13, F21, F27; old reference: `D:\projects\Sentinel_Repo\src\api\routes_analytics.py`, `src\analytics\route.py`, `src\tools\demo_seed.py`.
*Build:*
- `backend/app/routes_analytics.py`: `GET /api/sightings` (filters plate/camera_id/from/to/min_confidence/provenance, `limit`/`offset`, `total` computed with the same WHERE), `GET /api/plates/{plate}/route` (via `backend/services/route.py`: normalise → exact + ambiguity candidates by canonical index, fuzzy candidates flagged, order by `seen_at`, collapse same-camera stops within 2 min, Haversine elapsed/speed/distance, `suspect` on implausible speed, `departments_crossed`, `gaps`, **grouped by `clock_source`; no speed across groups and a `warnings[]` field saying so**), watchlist GET/POST/DELETE, `GET /api/alerts` (severity/acknowledged/kind/limit), `POST /api/alerts/{id}/ack` (persists actor), `GET /api/alerts/stream` (SSE; **one background tailer** on `alert_seq` with `id:` frames and `Last-Event-ID` replay; async generator; cookie auth accepted), `GET /api/events`, `GET /api/events/summary`, `GET /api/workers`.
- `backend/tools/demo_seed.py` (`inject` / `purge`): hero `GJ01AB1234` (on the watchlist as stolen/high) through **`record_sighting` and `find_match`/`create_alert`** with `provenance='demo'`, `clock_source='demo'`, `track_id` prefixed `DEMO-`: cam06 (GSRTC) at t, cam10 (Municipal) at t+7 min, cam09 (Police) at t+15 min, and an ambiguity near-miss `GJ01A81234` on cam09 at t+21 min; ~20 background plates on the active cameras. `purge` deletes only rows with `provenance='demo'` (and their alerts), and alerts must keep working afterwards.
*Acceptance:* `.venv/Scripts/python -m pytest tests/test_analytics_api.py tests/test_demo_seed.py -q`: route response validates field-for-field against api.md for the seeded scenario — 4 stops on 3 cameras in time order (3 `exact` for the hero, then the near-miss as one `ambiguity` stop on cam09), elapsed times 420 s, 480 s, 360 s, plausible speeds, 3 departments crossed; a `GJ01AB1235` sighting appears as a `fuzzy` stop; mixed `clock_source` rows produce a warning and no cross-group speed; SSE test — subscribe, insert an alert, receive within 4 s (the tailer polls every 2 s), purge, insert, receive again, reconnect with `Last-Event-ID` replays the gap; pagination `total` honours filters; after `purge`, `GET /api/alerts` is empty and a new sighting alerts again.
*Write-off:* progress block.

### S3.1b — Reports, HLS relay, health checker; OpenAPI re-export `[ ]`
*Read first:* `docs/api.md` §7 (reports, hls); `docs/decisions.md` C7, C14; `docs/sandbox-findings.md` §1–§2; old reference: `D:\projects\Sentinel_Repo\src\api\{routes_hls,routes_reports}.py`, `src\tools\report.py`, `src\ingest\health.py`.
*Build:*
- `backend/app/routes_reports.py` + `backend/services/reports.py`: `GET /api/reports/detections?format=csv|html` with filters and a **provenance column**, HTML escaped, CSV formula-prefix escaped; `GET /api/reports/route/{plate}?format=…`; `GET /api/reports/gap-analysis`.
- `backend/app/routes_hls.py`: `GET /api/hls/{cam}/live.m3u8` serves the worker's local tee when fresh (< 20 s) rewritten to `/api/hls/{cam}/local/{seg}`; otherwise (cut candidate #3) the CDN relay via `cdn_session`: rewritten sliding window of the upstream VOD playlist at the shared-timeline position, `/key` proxied (16-byte check), `/seg/{name}` proxied only for names present in the fetched playlist and only within the configured CDN origin; playlists cached 10 min. Every path accepts header or cookie auth.
- `backend/services/health.py`: background task in the API (`SENTINEL_HEALTH_INTERVAL_S`, 0 = off): active RTSP cameras judged by tee freshness; other cameras by a paced RTSP `ffprobe` (2 at a time, 20 s timeout) — **never by probing the CDN**; probes first, then one short write transaction.
- `.venv/Scripts/python -m backend.tools.export_openapi` re-run.
*Acceptance:* `.venv/Scripts/python -m pytest tests/test_reports.py tests/test_relay.py tests/test_health.py -q`: report XSS test (`<script>` in a plate filter comes back escaped), CSV `=cmd` prefixed, provenance column present; relay refuses a segment name not in the playlist and any off-origin URL, serves the local tee when present; health marks a camera with a stale tee `degraded` and one with a dead RTSP `offline` without touching the CDN (assert no CDN call). `deliverables/registry-api.json` re-exported; `tests/test_openapi.py` still passes.
*Write-off:* progress block.

### S3.2 — Frontend foundation: scaffold, data layer, key dialog, IST time, Map, Cameras, Watchlist `[ ]`
*Read first:* `frontend/CLAUDE.md`; `docs/api.md` §1, §3, §7 and the auth transport; `docs/decisions.md` §3 "Frontend", F28; old reference: `D:\projects\Sentinel_Repo\ui\src\` (`api.js` DEPT_COLORS, `pages/MapView.jsx`, `components/FitBounds.jsx`, `vite.config.js`).
*Build:* scaffold into a temporary folder (`frontend/` already holds `CLAUDE.md`, and create-vite prompts or overwrites on a non-empty dir): `npm create vite@6 frontend-scaffold -- --template react`, move its contents into `frontend/`, delete the temp folder; then pin `react@18.3.1 react-dom@18.3.1 react-router-dom@6 leaflet@1.9.4 react-leaflet@4.2.1 hls.js@1`; `vite.config.js` proxies `/api` and `/crops` to `http://localhost:8000`; `src/lib/api.js` (one client: base `/api`, `X-API-Key` from an in-memory store seeded by a key dialog and `sessionStorage`; on key entry it also calls `POST /api/session` so `<img>`, hls.js and `EventSource` work through the cookie; `r.ok` checked everywhere; typed errors surfaced to a global status strip), `src/lib/time.js` (`formatTs` via `Intl.DateTimeFormat` `Asia/Kolkata`, date + time), `src/lib/poll.js` (one shared poller for stats/health), `src/components/{Shell,Header,StatusStrip,KeyDialog,DeptLegend}.jsx`; pages **Map** (pins by department, opacity by health, filters, record panel), **Cameras** (table with filters; add-camera form → POST; CSV import with per-row results; edit → PATCH incl. tier/ROI/zones JSON), **Watchlist** (table, add form with category/severity/reason, remove). Leaflet CSS bundled. OSM tiles with attribution. `.venv/Scripts/python -m playwright install chromium` for the smoke script (the `playwright` package itself came with `requirements-dev.txt` in S1.1).
*Acceptance:* `npm --prefix frontend run build` clean; with the API running (`.venv/Scripts/python -m backend.app`) against a fresh test DB seeded by `seed_registry` (30 cameras), `scripts/smoke_frontend.py` (Playwright, headless Chromium; run as `.venv/Scripts/python scripts/smoke_frontend.py`) enters the viewer key, opens `/map`, `/cameras`, `/watchlist`, asserts pins = camera count, the cameras table has 30 rows, the import of `tests/fixtures/import_3rows.csv` shows 2 accepted / 1 rejected, and the watchlist add/remove round-trips with the admin key; screenshots saved to `data/screens/` for the deck. **[Adi verify]** visually in Chrome.
*Write-off:* progress block; note anything the smoke could not check.

### S3.3 — Frontend operations: Command, Live Wall, Search, Route, Alerts, Zones, Reports `[ ]`
*Read first:* `frontend/CLAUDE.md`; `docs/api.md` route response and SSE; `docs/demo-script.md` (what the screens must show on video); old reference: `D:\projects\Sentinel_Repo\ui\src\pages\{Dashboard,LiveWall,Search,RouteView,Alerts,Zones,Reports}.jsx`, `components\Tile.jsx`.
*Build:* **Live Wall** (1/4/9 grid, paging; `Tile` mounts hls.js on view and `destroy()`s on hide, `recoverMediaError` + jittered retry; label = id + department + live dot), **Command** (4 active tiles, mini-map, live alert feed via SSE, latest reads with crops, object counts, worker health from `/api/workers`, provenance badges), **Search** (filters incl. provenance; results with crop thumbnails; row → route), **Route** (input + `/route/:plate`; numbered pins, polyline dashed across gaps, timeline with crops, header with first/last seen, duration, distance, cameras, **departments crossed**; fuzzy and suspect stops marked; warnings shown), **Alerts** (SSE newest first, severity map complete incl. `critical`, crop, camera, department, timestamp, category, match type, ack persists, route link only for `kind='watchlist'`, list capped at 200), **Zones** (draw polygon / line on the camera's live tile, canonical shape, save reports the real result, hot-reload notice), **Reports** (detection CSV/HTML with filters, per-plate route export, gap-analysis, OpenAPI link, object counts table).
*Acceptance:* build clean; extend `scripts/smoke_frontend.py`: run `.venv/Scripts/python -m backend.tools.demo_seed inject` against the test DB, open `/route/GJ01AB1234` → numbered pins on 3 cameras, 4 timeline entries (the near-miss marked `ambiguity`) and a header naming 3 departments; open `/alerts`, insert an alert via `create_alert` → card appears within 3 s without reload; open `/wall` at 4 tiles → exactly 4 playlist requests in the network log, page to the next 4 → the first 4 players are destroyed (0 further segment requests for them); `/search?plate=GJ01` shows rows with thumbnails (cookie auth for `<img>`). Screenshots to `data/screens/`. **[Adi verify]** in Chrome.
*Write-off:* progress block.

### S3.4 — Launcher, second system over mediamtx, end-to-end walkthrough `[ ]`
*Read first:* `docs/decisions.md` C11, C12, F9, F19, F25, F30; `docs/sandbox-findings.md` §7 (launcher lessons); old reference: `D:\projects\Sentinel_Repo\launch.py`.
*Build:*
- `launch.py` — **standard library only, run as plain `python launch.py …` (Anaconda), because it exists before and around the venv; everything it spawns runs as `.venv/Scripts/python`** — modes `check | start | stop | status | demo | demo-clear | measure | harvest | replay-start | replay-stop` (`harvest` and `measure` are stubs that print "built in S4.2 / S4.1" until those sessions run): `start` = `scripts/doctor.py` checks → `.venv` + pinned deps (hash `requirements.txt` to decide reinstall; force-reinstall `onnxruntime-directml` if the plain wheel clobbered it) → ffmpeg resolved via config (fetch the BtbN portable build only if nothing resolves; SHA-256 into `CHECKSUMS.txt`) → models fetched + verified → probe on first run → seed registry (every start) → seed watchlist (every start) → build frontend if `frontend/dist` is missing → start API and worker **detached with stdout/stderr to `data/logs/`** → poll `:8000` for 30 s and fail loudly → open the dashboard. `stop` kills only the recorded PIDs' process trees (psutil). `status` prints the stats file and DB counts. `demo` / `demo-clear` call `backend.tools.demo_seed`. `.bat` wrappers as one-liners.
- Second system (F9/F19): `replay-start` runs `scripts/replay_publish.py` with Adi's own clip (or the laptop webcam via `dshow`) at `rtsp://127.0.0.1:8554/stream/local01`; the registry row `local01` (`transport='rtsp'`, plain URL, `source='manual'`, `fps_tier='active'`, department and ownership per O10) is added **through the add-camera form** during the demo (and by `backend.tools.seed_registry --add local01 <department> rtsp://127.0.0.1:8554/stream/local01 --tier active` for tests). `SENTINEL_ACTIVE_CAMERAS` is 6 so `local01` runs alongside the 5 seeded active cameras.
*Acceptance:* on the laptop: `python launch.py start` → dashboard opens, `python launch.py status` shows the API up and N workers alive; `python launch.py demo` → Route for `GJ01AB1234` shows the route across 3 cameras / 3 departments (4 timeline entries with crops, the near-miss marked), Alerts shows 4 cards, Reports CSV has the rows with `provenance=demo`; `python launch.py demo-clear` → rows gone, then a new synthetic sighting still produces an alert (regression D4); `python launch.py replay-start` + adding `local01` in the Cameras form → a live tile for `local01` plays and its worker appears in `/api/workers` alongside the sandbox cameras — **two different systems in one viewer**; `python launch.py stop` leaves no orphan `ffmpeg.exe` from this repo running (`tasklist` check) and does not kill unrelated ffmpeg processes.
*Write-off:* progress block; this is the end-to-end walkthrough the videos will follow.

---

## Phase 4 — Real feeds and measurements (Thu 24 Sep)

### S4.1 — Live sandbox run, 10-minute measurement — GATE B `[ ]`
*Read first:* `docs/sandbox-findings.md` §3–§5, §8; `docs/decisions.md` C9, F18; `docs/progress.md` "Key measurements".
*Build:* `python launch.py measure --minutes 10`: after the platform has run ≥ 10 min (warm-up), samples `nvidia-smi --query-gpu=memory.used --format=csv,noheader` and both processes' RSS every 5 s and reads `data/worker_stats.json`; writes `data/measurements/<timestamp>.json` (committed) plus a markdown table. Run: `launch.py start` with the 5 seeded active cameras; confirm real reads accumulate on cam06 in Search (daylight window); then `measure`.
*Acceptance:* the measurement table (sustained fps per camera with N active, detections per camera per minute, peak VRAM, peak RAM, motion-skip rate per camera, plate-read rate = full reads ÷ vehicle tracks) is pasted into `docs/progress.md` "Key measurements" with `[measured]`, replacing the blank rows; ≥ 5 real plate reads with crops exist with `provenance='live'`. **GATE B:** if reads are accumulating with sane confidence → continue; if not → do not tune models; reduce the active tier to the best cameras and continue (record the decision in the gate table).
*Write-off:* progress block with the table and the gate decision.

### S4.2 — HLS VOD reader + harvest for a real multi-camera route — time-boxed — GATE C `[ ]`
*Read first:* `docs/sandbox-findings.md` §2, §4; `docs/decisions.md` F15, §3 "Ingestion" (D1); old reference: `D:\projects\Sentinel_Repo\src\ingest\frame_source.py` class `FrameSource` (HLS mode), `src\tools\harvest.py`, `src\tools\measure.py` (AES decrypt validated).
*Build (stop at 3 h or Thu 20:00, whichever first):* `ml/ingest/hls_vod.py`: fetch the VOD playlist via `cdn_session`, pick segments by shared-timeline position, fetch + AES-128-CBC decrypt (key fetched through the session from `/enc.key`, IV 0), decode with an ffmpeg pipe, PTS = segment offset + in-segment PTS, `clock_source='hls-vod'`, **wrap: reset the last-yielded PTS and never busy-loop the CDN**, gentle pacing (the rate limiter), backoff + re-login. `ml/tools/harvest.py`: sweep the Junagadh (cam06/09/10) and Bilimora (cam26/27/28) clusters across the daylight tail of the recording, running the full pipeline with `provenance='harvest'`; print per-camera new-plate counts and **plates seen on ≥ 2 cameras**; `--from-sightings` seeds the watchlist with observed plates.
*Acceptance:* `.venv/Scripts/python -m pytest tests/test_hls_vod.py -q` (playlist parsing, segment selection by position, wrap handling with a synthetic playlist); on the laptop, if the CDN cooperates: harvest summary printed; if any plate appears on ≥ 2 cameras, `GET /api/plates/{plate}/route` returns ≥ 2 stops with `clock_source='harvest'` and the Route screen draws it. **GATE C at Thu 20:00:** a plate typed into the UI returns a timestamped route across ≥ 3 cameras — the demo vehicle satisfies this; a harvested real route is recorded as bonus. Either way, stop and go to Phase 5.
*Write-off:* progress block with the summary, or `CUT` with the reason.

### S4.3 — Pipeline 3 evidence clips — only if S4.2 finished on Thu and S5.1–S5.3 are done by Fri noon `[ ]`
*Read first:* `docs/reference/model-02-1-event-triggered-evidence.md` §3–§4; `docs/reference/model-02-1-promote.py`; `docs/decisions.md` F10, F16.
*Build:* the RTSP tee already is a ring buffer — raise `hls_list_size` to 450 for active cameras and add `program_date_time`; on a watchlist alert, a promote job copies the segments overlapping `[t−30 s, t+30 s]` (waits for the post-event window), concatenates with `-c copy`, writes SHA-256 + `alerts.clip_path/clip_sha256` + an audit row, serves the clip behind auth, and the alert card links it.
*Acceptance:* an alert produces a playable ~60 s clip starting ~30 s before the sighting; the tee directory stays flat in size; the audit row carries event id, trigger reason and hash. Otherwise `[-]` cut with the deck's existing "described, validated separately" wording.

---

## Phase 5 — Deliverables (Fri 25 Sep — GATE D: start by 09:00 whatever the code state)

### S5.1 — HLD corrections + PDF `[ ]`
*Read first:* `docs/architecture.md` Part C (the claim-by-claim list); `docs/progress.md` "Key measurements"; `deliverables/HLD.md`.
*Build:* edit `deliverables/HLD.md`: tracker described truthfully (F14); "never written to disk" → self-overwriting relay buffer; `[measured]` only for numbers from S4.1 (else `[model]`); audit table and API-key auth described as built; onboarding form + CSV as built; alert path = DB tail across processes; Pipeline 3 as built or described; add the one-time-base design and provenance labels; add the retention/DPDP note (decisions §3); if S4.2 was cut, say the HLS fallback exists for viewing only; keep every section of the ten dimensions. Render to `deliverables/HLD.pdf` (any clean markdown→PDF renderer; check the ASCII diagram survives).
*Acceptance:* every row of Part C is either fixed or explicitly retained with a reason; `grep -c "\[measured\]" deliverables/HLD.md` equals the number of measured rows in progress.md; the PDF opens and the diagram is intact.

### S5.2 — Deck with live screenshots, links, PDF; diagram PNG `[ ]`
*Read first:* `docs/reference/old-build/STATUS.md` entry "P6.5"; `deliverables/deck/build_deck.js`.
*Build:* replace `deliverables/deck/img/{dashboard,map,route,alerts,search,zones,reports}.png` with captures from the running fresh build (`data/screens/` from S3.2/S3.3 plus a live Command with playing tiles); fill slide 18's links; rewrite every caption that says "dev capture" / "development capture" / "test scenario"; correct any slide that states tracker/auth/relay claims per S5.1; `node deliverables/deck/build_deck.js` → pptx; export PDF; export `deliverables/Sentinel-Workflow-Integration-Diagram.png` from the SVG and add the image to the root `README.md`.
*Acceptance:* pptx opens; PDF opens; `grep -niE "dev capture|development capture|test scenario" deliverables/deck/build_deck.js` prints nothing; every image on slides 4, 6, 9, 10, 11 is from the fresh build; no credential visible in any capture.

### S5.3 — Reports, API doc, sample dataset, notes regenerated `[ ]`
*Build:* with the live DB (after S4.1, demo rows present and labelled): `deliverables/detection-report.{csv,html}` (provenance column present), `deliverables/route-GJ01AB1234.{csv,html}`, `deliverables/gap-analysis-report.html`, `deliverables/registry-api.json` (re-export; no stale endpoints), `deliverables/sample-camera-dataset.csv` (registry export with the disclosure line), and a one-page `deliverables/departmental-systems-unaffected.md` (read-only pull, no writes, no control-API calls — Model 2 deliverable; HLD §2.5 is the source).
*Acceptance:* each file opens; the detection CSV has ≥ 1 `live` row and the demo rows labelled `demo`; `registry-api.json` lists no `snapshot.jpg`.

### S5.4 — [Adi + Claude] Demo videos `[ ]`
*Read first:* `docs/demo-script.md` (both run sheets); `docs/decisions.md` C10.
*Build:* Video 1 (own feed, ≤ 3 min): the S3.4 walkthrough — wall with `local01` and sandbox tiles, map, "nothing is recorded", watchlist screen, the alert (demo vehicle or a live hit), route with departments crossed, report. Video 2 (government feed): onboarding (probe → registry → map, "the catalogue is the contract"), live tiles from the sandbox, ANPR reads with crops and timestamps on cam06, the exported detection report opened on screen. Several takes; keep the best; upload unlisted.
*Acceptance:* both files ≤ 3 min, play from a private window via the unlisted links, no credential visible in any frame (check the address bar and every terminal).

### S5.5 — Submission checklist walk-through, credential sweep, tag `[ ]`
*Read first:* `docs/submission-checklist.md` (its editor's note maps the old pointers).
*Build:* tick every box against an observation; sweep for credentials across the history, the deliverables and `data/screens` (`git log -p | grep -E "(rtsp|https?)://[^<{/ ]+:[^<{/ *]+@"` must print only the S1.1 example if anything); every document exported to PDF; numbers labelled; the 30-vs-50 note present; `frontend/dist` zipped to `deliverables/frontend-dist.zip` (decision F30 — `dist/` itself stays ignored); `git tag -a v2.0-submission` on `main`.
*Acceptance:* `docs/submission-checklist.md` fully ticked with a date; the tag exists on `main`; the sweep prints nothing unexpected.

---

## Phase 6 — Soak, rehearsal, submit (Sat 26 – Sun 27 Sep)

### S6.1 — Soak + fault injection; fix blockers only `[ ]`
*Build:* 2-hour live run (`python launch.py start`, detached — the session polls `/api/workers`, `data/worker_stats.json` and the logs; it never blocks a tool call on the run); inject, one at a time with ≥ 10 min between them: kill one ffmpeg child (`taskkill /PID <pid> /F` on a child recorded in the logs, not on an unrelated ffmpeg); **[Adi] pulls the network for 60 s** — Claude cannot, and the pull cuts Claude Code off too, so the session announces "pull now", Adi turns Wi-Fi off, waits 60 s, turns it on, and the session reads the logs and `/api/workers` afterwards (if Adi is absent, this injection is skipped and named in the progress block); corrupt a tee segment (overwrite one `data/hls/<cam>/seg*.ts` with zeros); `demo` + `demo-clear` twice; watch `/api/workers`, logs and RSS throughout. Fix only what blocks the demo; every fix gets its regression test; tag `v2.0.1` if anything changed. No features.
*Acceptance:* the run ends with all workers alive, no orphan processes, alerts still delivered after every injection (the network pull included, when Adi did it).

### S6.2 — [Adi] Rehearsal and fallback footage `[ ]`
Run the demo end to end twice with a timer; record fallback footage of every screen working; keep the insurance recording from S0.5.

### S6.3 — [Adi] Submit `[ ]`
Submit before the deadline, not on it; open every link from a private window afterwards; record the submission time and links in `docs/progress.md`.

---

## Definition of done — the submission

Every box in `docs/submission-checklist.md` ticked against an observation, every link verified from a private window, tag `v2.0-submission` on `main`, and `docs/progress.md` "Current state" saying so.
