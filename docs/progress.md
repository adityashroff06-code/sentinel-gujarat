# Progress — session handoff

Append a block after **every** task, in the format at the bottom. Record what was observed, not what was intended. Never delete an entry; supersede it with a later one. The top section is rewritten each session so the next session can start from it.

---

## Current state (25 Sep 2026 — Phase 3 validated complete; S4.1 code half done, its live run is the laptop's)

- **Phase 3 stands validated** (this session re-checked the ledger, the gate table, the tree and the suite): S3.0, S3.7, S3.1a, S3.1b, S3.2, S3.3, S3.3b, S3.4 all `[x]` with acceptance runs and commits; **GATE C PASS** (labelled demo vehicle); the only open Phase 3 items are physically Adi's — **S3.5 go-live** (runbook §0: Funnel trial, accounts, `SENTINEL_PUBLIC_HOST`, ~15 min) and **S3.6 filming**. Neither blocks Phase 4/5.
- **S4.1 is PARTIAL — the build half is done and tested** (this cloud session, branch `claude/sentinel-progress-check-rrtp9n`, draft PR): `python launch.py measure --minutes 10` now runs the F18 window sampler ported from the old build (`ml/tools/measure_run.py`), the worker counts `ocr_attempts` / `full_reads` / `vehicle_tracks` for the plate-read rate, `GET /api/workers` documents them, and 13 new tests cover it. **The run half is the laptop's**: probe → `launch.py start` (demo tier, F55) → ≥ 10 min warm-up → `launch.py measure --minutes 10` → paste the printed table into "Key measurements" → zone check → fill **GATE B**. Steps are in the S4.1 Log block below.
- **Suites:** this container **240 passed, 5 skipped, 0 failed** (the 5 are Windows-only mediamtx/PATHEXT; parity with the laptop's 232). After merging, the laptop should show **245 passed, 0 skipped**.
- **Git:** merge the S4.1 PR into `main` before the laptop run. The evidence files the sampler writes (`data/measurements/<ts>.{json,md}`) are committed on purpose.
- **[Adi] queue (unchanged plus one):** ① S3.5 go-live — `docs/runbook-hosting.md` §0 (~15 min). ② S3.6 — film the one-vehicle route. ③ The S2.2 20 s Wi-Fi pull. ④ `SENTINEL_ACTIVE_CAMERAS=6` in `.env`. ⑤ [Adi verify] the five hero screens in Chrome. ⑥ Merge the S4.1 PR, then run the S4.1 run half on the laptop (or hand it to a laptop Claude session).
- **Next Claude session: S5.1** (HLD corrections — GATE D says documents start whatever the code state; nothing waits on S4.1's numbers, the HLD's `[measured]` rows are filled when the laptop run lands). The laptop lane owns the S4.1 measure run.
- **Blockers:** none.

## Previous state (25 Sep 2026, ~08:00 UTC / 13:30 IST — PHASE 3 COMPLETE except the [Adi]-physical steps)

- **Phase 3 was completed in one autonomous overnight run on the laptop** (Adi's direction, 24 Sep — decisions F58, F59; the F57 lanes are collapsed, their reason gone with Phase 2 closed). Done, each with its acceptance run, its own commit and its Log block below: **S3.0** (login/roles/sessions/hardening, schema v2), **S3.7** (catalogue adapter + new-feeds runbook), **S3.1a** (analytics API + route + SSE), **S3.1b** (reports, relay, health, OpenAPI re-export), **S3.2** (frontend foundation + login hero + Playwright smoke), **S3.3** (all seven operations screens, smoke 43), **S3.3b** (design pass + the F53 review gate: /security-review 0 findings; /code-review high 7 findings — 6 fixed, 1 answered; smoke 67), **S3.4** (launcher + second system + a 26-min live end-to-end walkthrough). **S3.5 is PARTIAL** (runbook written; the Funnel trial, accounts and checks are [Adi]). **S3.6 waits on Adi's filming** (GATE C is already passed by the labelled demo vehicle — see the gate table).
- **The sample-footage feeds are integrated** (F58): Adi's 28 stock CCTV clips were scored by the real detector+OCR (`scripts/analyze_footage.py` — 24 distinct full Indian plates), the best 4 transcoded to 1080p30 and published over mediamtx with the new copy mode as `local01..local04` (registered in `sentinel.db` with disclosed seeded coordinates). A verification run on `footage.db` produced 21 live-path sightings and **3 real alerts (2 exact + 1 ambiguity fold)**; the S3.4 walkthrough then ran **both systems in one worker set** — 5 live sandbox cameras + local01 — for 26 min: 0 restarts, 137 sightings (13 REAL reads on live cam06), clean stop, no orphans.
- **Suites:** laptop full suite grew 146 → **232 passed, 0 failed** through the night (final run 330.97 s, 25 Sep ~13:45 IST). The smoke is 67 browser assertions against the real API. `main` is pushed at every task boundary — each commit is a fallback demo (rule 10).
- **The evidence DB (`data/sentinel.db`)** now holds real live sandbox reads + the labelled demo route; back it up before experiments (`data/backup/`, gitignored).
- **[Adi] queue (everything left needs your hands):** ① S3.5 go-live — `docs/runbook-hosting.md` §0: Tailscale Funnel trial from mobile data, create the evaluator+admin accounts, set `SENTINEL_PUBLIC_HOST`, reboot check (~15 min). ② S3.6 — film the one-vehicle route (10–15 min at 3-4 locations, plate ≥ 100 px, 1080p30); the sample feeds cover the wall/feed role but NOT the real multi-camera route. ③ The S2.2 20 s Wi-Fi pull (unchanged). ④ Consider `SENTINEL_ACTIVE_CAMERAS=6` in `.env` so `local01` joins without a per-process override. ⑤ [Adi verify] the five hero screens in Chrome (S3.2/S3.3/S3.3b note) — `python launch.py start` and look.
- **Next Claude session: S4.1** (probe + pick the demo tier + the formal 10-minute measurement — **GATE B**), then Phase 5 documents (GATE D was 09:00 Fri — the code state it starts from is now complete Phase 3, so S5.1 can begin immediately).
- **Blockers:** none.

## Previous state (23 Sep 2026, 21:05 UTC — Phase 2 complete, GATE A' passed)

- **Phase 2 is closed.** This session (a Claude Code cloud container: Linux, python 3.11.15, no GPU, no `.env`, no sandbox reach) completed **S2.3, S2.4 and S2.5** and passed **GATE A'** (the 10-minute replay soak: 614.9 s, 0 worker restarts, 1843 frames on each of 3 replay cameras, RSS +0.6 MB, stats every 10 s, 10 wrap ticks per camera). Whole suite here: **141 passed, 5 skipped** (the 5 are the mediamtx harness cases, Windows-zip only; the laptop unskips them). The full pipeline now exists end to end: frame source -> motion gate -> YOLOX-S -> tracker -> PaddleOCR consensus -> sightings with dedupe -> watchlist match -> alerts with table-derived cooldowns -> object/zone events -> single-writer supervisor with stats.
- **The demo vehicle runs through the whole architecture** (Adi's ask, 23 Sep): `backend/tools/demo_seed.py` (S3.1a's seeder, pulled forward) injects hero `GJ01AB1234` through the real `record_sighting -> find_match -> create_alert` path — 3 stops cam06/cam10/cam09 + ambiguity near-miss, 4 alerts, 20 background plates, every row `provenance='demo'`. The Phase-3 windows (route, alerts, search, dashboard) will read these same rows; nothing on the data side blocks them.
- **Git:** this cloud session works on branch **`claude/relaxed-dijkstra-qx8j24`** (pushed; draft PR #1 on GitHub). `main` on the laptop was at `92fa02a`+R5 when the session started; **merge the PR (or fast-forward) before the next laptop session** so S3.0 starts from Phase-2 code. Commits: S2.3 `71fefeb`, S2.4 `2e2b277`, S2.5 code `112051a`, demo seeder `3970c8a`, then the write-off commit.
- **On first laptop run after merge:** `models/yolox_s.onnx` (36 MB) and the PP-OCRv5 mobile weights download once and verify against the committed `CHECKSUMS.txt` pin; Paddle models land in repo-controlled `models/paddle/` (`PADDLE_PDX_CACHE_HOME`, set in `ml/anpr/ocr.py`). Two new env defaults: `SENTINEL_MOTION_MIN_RATIO=0.002`, `SENTINEL_DETECT_CONF=0.4` (`.env.example`).
- **Deferred to the laptop** (ride the next laptop session): DirectML detector latency (~50 ms expected; CPU here measured 95-135 ms), laptop OCR latency (~0.45 s expected; here 176-198 ms), and the S2.2 20 s Wi-Fi pull ([Adi], Thu 24, on the best-working camera after a fresh all-camera probe — F49).
- **Next task: S3.0** (login, roles, sessions, hardening — schema v2), then S3.7, S3.1a (analytics API + route; its demo seeder is already built — see the editor's note in the task block), S3.1b, S3.2, S3.3 per the Wed 23 column. GATE B/C are Thu 24.
- **[Adi] queue:** ⑥ Tailscale Funnel trial (gates S3.5); ⑦ Thu 24: film the S3.6 clips — **10 recordings of 60-90 s** with coordinates (Adi confirmed 23 Sep they arrive tomorrow; they become local01..local10 replay rows through this pipeline); ⑧ Thu 24: the S2.2 Wi-Fi pull.
- **Blockers:** none.
- **Timing notes:** full suite ~3 min in this container and ~3.5 min on the laptop (paddle/cv2 imports). The soak supervisor is `python -m ml`; stop it with Ctrl-C or `data/stop`.

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
| **Sustained inference fps per camera, N active** | **[measured]** cam06 0.67 · cam09 1.31 · cam26 0.6 · cam27 0.76 · cam28 1.47 (N=5 live sandbox cameras, 5 alive at end, 0 restarts) | S4.1 measure 20260925-084754Z (14:18–14:28 IST, daylight; 600 s window after 10 min warm-up) |
| **Real detection rate (vehicles/camera/min)** | **[measured]** cam06 15.6 · cam09 0.1 · cam26 0.0 · cam27 3.3 · cam28 0.5 (unique vehicle tracks; raw boxes/min 125.1 · 0.2 · 0.0 · 48.8 · 33.0) | S4.1 measure 20260925-084754Z (14:18–14:28 IST, daylight; 600 s window after 10 min warm-up) |
| Peak VRAM used | **[measured]** 119 MiB (baseline 119 MiB; YOLOX-S on DirectML). Cross-checked with Windows GPU counters: the worker holds 120 MB dedicated on the adapter that exposes the `cuda` engine (the GTX 1650, not the Vega iGPU), engine load 41 % | S4.1 measure 20260925-084754Z (14:18–14:28 IST, daylight; 600 s window after 10 min warm-up) |
| Peak RAM used | **[measured]** 1749 MB (API tree 102 + worker tree 1672). RSS on Windows is the working set: the last ~25 s show a trim to ~220 MB by the OS memory manager, which also skews the Q1→Q4 trend (−17.2 %) | S4.1 measure 20260925-084754Z (14:18–14:28 IST, daylight; 600 s window after 10 min warm-up) |
| Motion-skip rate per camera | **[measured]** cam06 0.0 · cam09 0.245 · cam26 0.542 · cam27 0.026 · cam28 0.0 | S4.1 measure 20260925-084754Z (14:18–14:28 IST, daylight; 600 s window after 10 min warm-up) |
| Plate-read rate (full reads ÷ vehicle tracks) | **[measured]** 0.062 overall (12/195); cam06 0.077, the other four 0.0 | S4.1 measure 20260925-084754Z (14:18–14:28 IST, daylight; 600 s window after 10 min warm-up) |

Superseded by the laptop: RTSP **is** reachable from the laptop (27/30, `data/probe_results.json`); a 61-second stats snapshot from 18 Sep gives per-camera sustained fps 0.46–1.43 and detections/min 0–67.9 with 5 active (`docs/sandbox-findings.md` §8). **The four previously blank rows are now filled from the formal S4.1 10-minute run on 25 Sep** (evidence committed: `data/measurements/20260925-084754Z.{json,md}`); the HLD may cite only these as `[measured]`.

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
| A′ — replay soak (S2.5): 10 min, zero restarts; live RTSP frames with correct timing (S2.2) | Tue 22 | **PASS** | 2026-09-23T20:55Z | Soak: 614.9 s, 0 worker restarts, 1843 frames on each of 3 replay cameras (3.0 fps each), RSS +0.6 MB over the run, stats every 10 s, 10 wrap ticks/camera. Live RTSP timing: S2.2's cam06 smoke, 134 frames monotonic (23 Sep) |
| B — ANPR viability on the live sandbox (S4.1): real reads with sane confidence | Thu 24 | **PASS — continue on the current tier (no model tuning)** | 2026-09-25T08:58Z | 10-minute window (20260925-084754Z): 9 sightings, 12 full consensus reads, 0 restarts; cam06 carries the plates — 55 `provenance='live'` reads with crops over the afternoon run (conf 0.78–0.99, e.g. GJ11S7924 0.96, GJ03MH7800 0.96 seen twice, GJ32AG2883 0.97); cam09/26/27/28 contribute detections, motion and zone analytics but no plate reads (small/oblique plates, quiet end of the looped recording). The cam06 crossing line fired 53 `line_cross` events on the live feed — the first zone event ever on a real feed. Late vs the Thu 24 due: the run needed the laptop and daylight, both available Fri 25 afternoon |
| C — route across ≥ 3 cameras from a plate typed into the UI (S4.2; demo vehicle qualifies) | Thu 24 20:00 | **PASS — demo vehicle (labelled)**; own-footage upgrade pending Adi's S3.6 filming | 2026-09-25T05:35Z | The smoke types GJ01AB1234 into the real UI (headless Chromium against `python -m backend.app`): Route renders 4 timeline entries incl. the ambiguity near-miss, numbered pins on 3 cameras, 3 departments in the header — asserted on two consecutive runs (S3.3), and re-checked at both viewports in S3.3b. Late vs the Thu 20:00 due: the plan's Wed/Thu columns compressed into the overnight run (F59) |
| D — documents start whatever the code state (S5.1) | Fri 25 09:00 | **PASS (late)** — S5.1 done, S5.2/S5.3 running | 2026-09-25T10:50Z | Documents started once the S4.1 laptop run had landed (it needed daylight and the laptop); the HLD cites only the six S4.1 [measured] rows |

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
## S2.3 — DONE (motion gate, YOLOX-S detector, tracker, fetch_models; 18 tests)
When:      2026-09-23T20:20Z (cloud container)
Observed:  Environment first: this session is a fresh Claude Code cloud
           container (Linux, python 3.11.15, no GPU, no .env). ffmpeg
           6.1.1 apt-installed; .venv rebuilt from requirements.txt +
           requirements-dev.txt — every pin resolved, pip check clean
           (Linux markers put plain onnxruntime 1.24.4 in, never the
           directml wheel). Baseline before S2.3: 78 passed, 5 skipped
           (the mediamtx-harness cases skip without the Windows zip;
           laptop equivalent was 83 passed).
           Built: ml/tools/fetch_models.py (yolox_s.onnx from the Megvii
           0.1.1rc0 release, SHA-256 pinned in CHECKSUMS.txt on first
           download — c5c2d13e59ae... committed — later runs verify and
           ChecksumMismatch refuses a tampered file); ml/anpr/motion.py
           (MOG2 on a 320-wide downscale, 5-frame warm-up, per-camera
           threshold from notes JSON via gate_for_camera, reset());
           ml/anpr/detect.py (ONNX Runtime, DirectML-then-CPU provider
           pick logged, one lock around session.run(), YOLOX letterbox +
           grid decode, per-class NMS via cv2.dnn.NMSBoxes, 8 COCO
           classes kept, superclass() car/truck/bus/motorcycle->vehicle,
           ROI mask applied BEFORE inference, caption-band drop);
           ml/anpr/track.py (greedy IoU + centre-distance fallback on
           superclass, PTS-delta velocity, max_age 3 s, ids never reused
           — reset() keeps the counter, per ml/CLAUDE.md zone rule).
           Config: SENTINEL_MOTION_MIN_RATIO=0.002, SENTINEL_DETECT_CONF
           =0.4 added to config.py + .env.example.
           Acceptance observed: pytest tests/test_detect.py
           tests/test_track.py -> 18 passed in 1.19s. feed_cam01.jpg ->
           5 vehicles of 5 detections (bus, car, truck) on
           CPUExecutionProvider; black frame -> 0; sliver ROI -> 0,
           full-frame ROI -> still >= 3 vehicles; identical frames ->
           <= 10 of 100 pass the gate (>= 90 % skipped); moving box
           passes >= 80 %; tracker holds one id over 30 frames and
           across a car->truck flip; tampered model refused.
           Measured here (CPU): 95-135 ms/frame warm — inside the
           116-300 ms cloud-CPU band sandbox-findings §7 predicts.
Deferred:  DirectML latency (~50 ms expected) is a laptop measurement —
           record it when the laptop runs the suite next (S4.1 at the
           latest).
Surprise:  none; the sliver-ROI test doubles as the caption-band guard
           (band drop verified by inspection — top-centred boxes are
           dropped in detect()).
Next:      S2.4 (OCR cascade, consensus, sightings) in this session.
```

```
## S2.4 — DONE (OCR cascade, consensus voting, sightings dedupe; 20 tests)
When:      2026-09-23T20:25Z (cloud container)
Observed:  Built: ml/anpr/ocr.py (PaddleOCR PP-OCRv5_mobile det /
           en_PP-OCRv5_mobile_rec, enable_mkldnn=False, one lock around
           init + predict, crop -> cubic upscale to ~400 px (<= 4x) +
           CLAHE on LAB-L, plate_like gate, quads mapped back to
           source-frame [x, y, w, h], caption-band rejection);
           ml/anpr/pipeline.py (gate -> detector -> tracker -> OCR
           budget -> per-track confidence-weighted per-character
           consensus; commit on >= 2 agreeing reads, or on track death /
           restart with >= 1 structurally full read; never a first-read
           latch); ml/anpr/sightings.py (record_sighting with the B13
           bounded dedupe — same plate_canonical + camera + clock_source
           within 60 s of seen_at AND wall_time within 10 min -> update
           confidence if better, never insert; ~2 KB crops under
           data/crops/<cam>/ with forward slashes; provenance is the
           caller's, stored verbatim).
           MODEL PATH: PADDLE_PDX_CACHE_HOME is set (setdefault) to
           models/paddle/ before paddleocr imports, so the PP-OCRv5
           weights land in the repo-controlled path, NOT ~/.paddlex —
           verified: "models under /home/user/sentinel-gujarat/models/
           paddle". models/ is gitignored; the laptop will download
           there on first OCR use (~30 MB, needs network once).
           Acceptance observed: pytest tests/test_ocr.py
           tests/test_sightings.py -> 20 passed in 3.20s.
           - 22 px GJ01AB1234 inside a 90 px crop reads as 'GJ01AB1234'
             conf=1.00; caption-band placement (top of a 1080 px frame)
             rejected, lower placement reads; bbox maps to source pixels
           - consensus [GJ01AB1234, GJ01A81234, GJ01AB1234] ->
             GJ01AB1234; one 0.95 read outvotes two 0.3 reads; length
             groups vote separately; [] -> None
           - budget: <= 2 crops/frame largest-first, 1.5 s per-track gap,
             full-consensus tracks skipped (stub-driven pipeline tests)
           - dedupe matrix: 30 s later -> 1 row conf raised to 0.95 (and
             never lowered); 61 s -> 2 rows; wall_time 20 min apart ->
             2 rows; different clock_source -> 2 rows; ambiguity
             GJ01A81234 dedupes into GJ01AB1234 via canonical
           - partial GJ05JB432 stored, find_match -> None (F21)
           - crop file data/crops/testcam/1.jpg, 1.2 KB, forward slashes
           Measured here (CPU): OCR warm 176-198 ms/crop (first call
           2.3 s includes model load) — this box is faster than the
           laptop's measured 0.45 s/crop; budget maths unchanged.
Deferred:  laptop OCR latency re-measure rides the next laptop suite run.
Surprise:  none.
Next:      S2.5 (alerts, events + zones, worker + supervisor, soak).
```

```
## S2.5 — DONE (alerts, zones, events, worker + supervisor; GATE A' PASSED)
When:      2026-09-23T20:55Z (cloud container)
Observed:  Built: backend/core/alerts.py (create_alert; 5-min cooldown per
           (plate_canonical, camera) / (zone_id, camera) derived from the
           alerts table IN THE SAME clock_source, never memory; alert_id
           ALERT-YYYYMMDD-NNNN derived from the AUTOINCREMENT alert_seq);
           ml/analytics/zones.py (canonical shape validation for PATCH,
           2-consecutive-frame confirmation for intrusion, line crossing
           against the last CONFIRMED side, downward (+y) only, vertical
           lines never fire, hot reload keeps state for surviving zone
           ids); ml/analytics/events.py (per-class 5 s throttle on
           stream time, batched best-effort object events, awaited zone
           events so alerts can reference event_id); ml/worker.py
           (CameraWorker thread + process_read — the single-connection
           sighting -> commit -> find_match -> create_alert path shared
           with tests and demo_seed; DB errors guard each frame, never
           the loop); ml/supervisor.py (single DbWriter thread with
           BEGIN IMMEDIATE + lock retry; active tier = transport IN
           (rtsp, replay) AND fps_tier=active capped at
           SENTINEL_ACTIVE_CAMERAS; never two workers per camera;
           damped restart; watchlist + zone refresh every 10 s; atomic
           data/worker_stats.json; SIGINT / data/stop graceful stop;
           psutil own-tree kill only); ml/__main__.py.
           Fix en route: seed_registry --replay rows now seed
           fps_tier='active' (the soak supervisor would otherwise never
           pick them); test extended.
           Unit acceptance: pytest tests/test_alerts.py tests/test_zones.py
           -> 22 passed. Highlights observed: watchlisted plate -> exactly
           one alert, four repeats within 5 min suppressed; +5:01 alerts
           again; partial never alerts; GJ01AB1235 fuzzy never alerts by
           default; ambiguity GJ01A81234 alerts; PURGE then new sighting
           -> new alert with a FRESH alert_seq (D4 regression); zone
           inside,inside,outside,inside -> exactly 1 fire; inside,outside,
           outside -> 0; line fires downward only, once, confirmed side;
           high-severity zone -> kind='zone' alert with event_id set and
           sighting_id NULL; zone cooldown per (zone_id, camera).
           GATE A' — the 10-minute replay soak, observed:
           - SENTINEL_DB=data/soak.db, 3 replay cameras
             (seed_registry --replay synthetic_60s.mp4 replay01..03)
           - uptime 614.9 s, ZERO worker restarts
           - frames 5529 total, EXACTLY 1843 per camera (uniform),
             fps_sustained 8.99 = 3.0 fps per camera
           - rss_mb 309.2 (first write) -> 309.8 (final): +0.6 MB
             growth over the run (< 100 MB required)
           - stats file rewritten every 10 s (30 trace samples)
           - 10 restart (wrap) ticks handled per camera (>= 2 required)
           - sightings: 0 (testsrc2 has no vehicles - nothing to read;
             "every sighting provenance='test'" holds vacuously), so the
             pipeline-to-DB path is instead proven by test_alerts/
             test_demo_seed through the same process_read functions
           - data/sentinel.db untouched (does not exist on this box)
           Whole suite after Phase 2: 141 passed, 5 skipped in 186 s
           (the 5 skips are the mediamtx harness cases, Windows-only
           zip; laptop unskips them).
Surprise:  timeout -s INT exits 130, which reads as "failed" in the
           harness — the soak itself shut down gracefully (all workers
           joined, final stats written, 0 restarts).
Next:      S3.0 (login + hardening) — the Wed 23 column. Laptop items
           deferred from today: DirectML detector latency (~50 ms
           expected), laptop OCR latency, S2.2 Wi-Fi pull (Adi, Thu 24).
```

```
## S3.1a-partial — demo seeder pulled forward (Adi's ask, 23 Sep)
When:      2026-09-23T20:58Z (cloud container)
Observed:  backend/tools/demo_seed.py (inject / purge) built to the
           S3.1a spec, a day early, so the demo vehicle exercises the
           whole Phase-2 architecture the day it closed: hero GJ01AB1234
           through record_sighting -> find_match -> create_alert
           (ml/worker.process_read — the same code path a live read
           takes) with provenance='demo', clock_source='demo', DEMO-
           track ids; stops on cam06 (GSRTC) t, cam10 (Municipal) t+7,
           cam09 (Police) t+15, ambiguity near-miss GJ01A81234 on cam09
           t+21 (elapsed 420/480/360 s exactly as the S3.1a route
           acceptance expects); 20 invented background plates chosen not
           to match the seeded watchlist; inject purges first so it is
           idempotent; purge deletes ONLY provenance='demo' rows and
           their alerts. pytest tests/test_demo_seed.py -> 6 passed:
           route shape, 24/24 rows labelled demo, 4 alerts (3 exact +
           1 ambiguity), inject-twice no duplicates, purge leaves
           non-demo rows and alerting still fires with a fresh
           alert_seq, background plates never alert.
           The F49 pick hook: route_cameras stays the pinned fallback
           (cam06/cam10/cam09) until S3.7's --pick-active exists; the
           S3.1a session wires the pick and keeps these tests green
           (editor's note added to the task block).
Surprise:  none.
Next:      S3.0. The 10 sample clips Adi films Thu 24 (60-90 s, with
           coordinates) feed S3.6: local01..local10 replay rows through
           this same pipeline, and the S3.6 real hit replaces the demo
           route as the headline route (demo stays the labelled
           fallback, rule 12).
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
Merged:    while R6 was being written, Phase 2 closed on main (PR #1:
           S2.3, S2.4, S2.5 with GATE A' passed, and the demo seeder
           pulled forward from S3.1a). This branch was merged with that
           main; the only conflict was the end of this file.
Next:      S3.0, as Current state says. With S2.5 on main, every
           cloud-lane task is unblocked (S3.0, S3.7, S3.2, then S3.1a,
           S3.1b, S3.3, S3.3b).
```

```
## R6a — DONE (review of PR #2 after merge; Current state is stale for Thu 24)
When:      2026-09-23T21:15Z (24 Sep 02:45 IST), cloud session, branch
           claude/eloquent-hypatia-kdhdnq — docs only, this block only.
Observed:  PR #2 (R6, plan v2.5) reviewed and merged into main as f9f9667:
           no conflict markers, main already merged into the branch;
           tasks.md S3.1a's pinned cameras (cam06/cam10/cam09) match
           backend/tools/demo_seed.py. Full suite on this branch in a
           Linux cloud container (python 3.11.15, requirements.txt +
           requirements-dev.txt, apt ffmpeg 6.1.1): 141 passed, 5 skipped
           (1 Windows-only PATHEXT, 4 mediamtx harness - the fetch is
           blocked here), the same count Phase 2 recorded.
           Current state was NOT edited: F57 reserves it for the laptop
           lane. It is stale in three places, for the first laptop
           session to fold in:
           1. [Adi] queue item 7 still says "10 recordings of 60-90 s".
              v2.5 (tasks.md S3.6) says: 10-15 minute recordings of one
              vehicle at three or four real locations visited in order,
              plate ~100 px wide or more, daylight, 1080p30 H.264 (iPhone:
              Most Compatible), steady, plate >= 3 s in frame per pass;
              note coordinates, clip start times and a department; copy
              by cable or Drive originals, never WhatsApp. FILM TO S3.6,
              NOT TO CURRENT STATE.
           2. The Git line still names draft PR #1 as unmerged; PR #1
              (ea2ebc9) and PR #2 (f9f9667) are both on main - pull main
              on the laptop before S3.4.
           3. The Next-task line predates the lanes (F57): cloud S3.0,
              S3.7, S3.2, then S3.1a, S3.1b, S3.3, S3.3b; laptop S3.4 ->
              S4.1 (GATE B) -> S3.6 (GATE C, Thu 20:00); S4.2/S4.3 cut.
Surprise:  (1) demo_seed.py's docstring and comment (lines 15-17, 36) still
           say S3.7's pick will replace the pinned cameras (F49); F55 cut
           the pick, so the pinned cameras are final. Behaviour is right,
           only the comment is stale - fix it in the next session that
           edits that file.
           (2) tasks.md S2.2 (line 279, v2.4) still runs the Thu 24 Wi-Fi
           pull on "the best-working camera" the probe reports (F49); F55
           fixes the demo tier to cam06 + up to four live sandbox cameras
           but does not say which camera the S2.2 pull uses. Not a
           conflict - flagged so the laptop session picks deliberately.
Next:      unchanged - S3.0 (cloud), S3.4 (laptop).
```

```
## Phase-2 laptop verification — DONE (first laptop run after the merges)
When:      2026-09-24T18:00Z (24 Sep 23:30 IST), laptop, main fast-forwarded
           to f601147 (PR #1, #2, #3 all in).
Observed:  models/yolox_s.onnx fetched and checksum-verified against the
           committed pin; PaddleOCR PP-OCRv5 mobile weights downloaded to
           models/paddle/ during the suite run; mediamtx v1.21.1 present
           with its recorded zip. Whole suite on this laptop:
           **146 passed, 0 skipped, 0 failed in 368.6 s** — the 5 cases
           the cloud container skips (mediamtx harness + PATHEXT) run and
           pass here. Phase 2 is now proven end to end on the demo machine.
Surprise:  none.
Next:      Adi's direction (24 Sep, in chat): ingest the sample CCTV
           archive as live feeds AND complete the whole Phase 3 in one
           autonomous overnight run (recorded as F58, F59).
```

```
## S3.0 — DONE (login, roles, sessions, hardening; schema v2) [commit 60062ee]
When:      2026-09-24T19:15Z (25 Sep 00:45 IST), laptop, wave-1 subagent
           (F59) + orchestrator review.
Observed:  Everything the task block names, built and green: 0002_auth.sql
           (users/sessions/login_attempts), scrypt passwords, session
           cookie + key resolving to (actor, role), viewer<evaluator<admin,
           5-fail/15-min lock surviving restart, /api/users CRUD, users
           CLI via getpass, five security headers, /docs behind login,
           TrustedHost from SENTINEL_PUBLIC_HOST, CSV caps via pure-ASGI
           middleware, reusable RateLimiter (wired to route/reports/relay
           in S3.1b). Acceptance: test_auth + test_registry_api +
           test_schema -> 36 passed (agent run); the whole-suite run is
           logged under "Wave-1 full suite" below.
           Interpretation recorded: the Origin check is CSRF defence on
           session-authenticated mutations only; X-API-Key mutations are
           exempt (the acceptance itself demands the old key path
           unchanged). /docs alone carries a relaxed CSP (Swagger UI
           cannot boot under the strict one).
           Orchestrator follow-ups, each with a regression test:
           audit.actor now stores the resolved username (or key:<role>),
           never the bare role; POST /api/cameras moved admin->evaluator
           (api.md §7 grants the evaluator the onboarding form; PATCH
           stays admin). test_auth 20 passed, +registry 32 passed.
Surprise:  FastAPI parses multipart before dependencies, so the CSV cap
           became ASGI middleware; FastAPI 0.141.1 include_router keeps
           _IncludedRouter wrappers (route walk flattens them); the
           parallel S3.1a agent and this one cross-edited
           routes_analytics.py deps mid-run and converged on
           require_evaluator for ack + watchlist (F41) without conflict.
Next:      S3.7/S3.1a (same wave).
```

```
## S3.7 — DONE (catalogue adapter + new-feeds runbook) [commit 37d40af]
When:      2026-09-24T19:20Z, laptop, wave-1 subagent (F59).
Observed:  fetch_catalogue() accepts cameras.json {id,name} AND the
           /api/ingest record shape, normalises to registry columns,
           catalogue verbatim wins, seed CSV only fills gaps (F45);
           SENTINEL_CATALOGUE_URL overrides the source. Runbook written
           with the five onboarding commands + the local demo-feed path.
           Acceptance: test_catalogue + test_seed_tools -> 8 passed.
           The --pick-active pick stays cut (F55).
           Consequence to know: for the sandbox flow the catalogue's raw
           location_name ('06 Timbavadi gate-Junagadh') now wins over the
           seed's label — UI copy shows raw names; deliberate (F45),
           one-line reversal in apply_seed if Adi prefers labels.
Deferred:  seed_registry against the live sandbox (expect ACCEPTANCE:
           PASS, 30 rows) rides the next probe run (S4.1).
Next:      S3.1a (same wave).
```

```
## S3.1a — DONE (analytics API + route service + SSE) [commit c01fbcd]
When:      2026-09-24T19:25Z, laptop, wave-1 subagent (F59).
Observed:  Ported from src/api/routes_analytics.py + src/analytics/
           route.py (F52), adapted to seen_at/clock_source/provenance and
           session auth; defects D3 (boundary timestamps), D4 (SSE cursor
           = alert_seq + Last-Event-ID), D8 (pagination total shares the
           WHERE) fixed in the port. Route response validates
           field-for-field against api.md for the seeded demo: 4 stops /
           3 cameras, elapsed 420/480/360 s, 3 departments, near-miss as
           ambiguity, fuzzy stop flagged, mixed clock_source -> warnings[]
           and no cross-group speed. SSE: subscribe->insert->receive
           < 4 s; purge does not reset the tailer (alert_seq is
           AUTOINCREMENT); Last-Event-ID replays from the table.
           Acceptance: test_analytics_api + test_demo_seed -> 19 passed.
           api.md §7 updated in the same commit (alerts kind filter, ack
           semantics, workers/events-summary shapes).
Surprise:  starlette 1.6 TestClient runs the ASGI app to completion, so
           unbounded SSE deadlocks client.stream — the SSE tests drive
           the raw ASGI protocol in-process; S3.3's smoke should test SSE
           through a real port, not TestClient.
Next:      wave 2 (S3.1b + S3.2).
```

```
## F58 footage integration — DONE (S3.4-partial: 4 sample feeds through
##                                the whole live path) [commit 31890fa]
When:      2026-09-24T18:56Z (25 Sep 00:26 IST), laptop, orchestrator.
Observed:  Adi's archive.zip -> 28 stock CCTV clips (Indian traffic,
           mostly 4K30 H.264, 7-120 s), extracted OUTSIDE the repo to
           D:\projects\sentinel-footage\raw. scripts/analyze_footage.py
           scored every clip through the real detector+OCR at 1080p:
           24 distinct structurally-full plates across 8 clips; best
           clip 13270133 (10 plates, 20.8 vehicles/frame). Top 4 clips
           transcoded once to 1080p30 H.264 g=60 -> local01..local04,
           published over mediamtx with the NEW copy mode
           (replay_publish --copy; ~zero publish CPU), registered in
           BOTH data/footage.db (the run DB) and data/sentinel.db
           (integration; tier active, seeded Gandhinagar-cluster
           coordinates, disclosure inside location_name - Adi approved
           seeded coordinates in chat, F58).
           Verification run (footage.db; looped feeds are F56-legal on a
           test DB): supervisor 582 s, 4/4 workers, 0 restarts, 380
           frames sampled, 2949 detections, **21 sightings with
           provenance='live', clock_source='rtsp-live'** (conf 0.81-0.99,
           crops on disk), watchlist seeded FROM observed sightings
           mid-run (cache refresh <=10 s, no restart), and **3 real
           alerts through record_sighting->find_match->create_alert:
           ALERT-20260924-0001 exact MH04JH3316 local03,
           -0002 exact MH47AU0099 local02,
           -0003 ambiguity MH04GN2055~MH046N2055 (G<->6) local03** —
           the ambiguity machinery fired on a live read.
           Shutdown clean via data/stop: no orphan ffmpeg/mediamtx.
Surprise:  (1) ~85 s of zero frames at start - four concurrent ffprobe
           size-probes + ffmpeg spawns serialised under load before the
           first ticks; it cleared on its own, watchdogs never fired.
           (2) With 4 dense 1080p feeds the shared OCR lock is the
           bottleneck (~0.5-1 fps/camera effective while wave-1 agents
           also ran; sampler drops by PTS as designed). Detector/OCR
           latency numbers tonight are load-contaminated - S4.1 owns the
           clean 10-minute measurement.
           (3) Same physical plate OCR-misreads differently pass to pass
           (MH04MA4386 -> MH042A4386 / MH04A4386), so watchlist hits
           want the -from-sightings seeding, which is exactly what it is
           for.
Next:      wave 2; the S3.4 session proper wires launch.py replay-start
           over these feeds; S3.6 (real filmed route) stays [Adi].
```

```
## Wave-1 full suite — PASS (cross-task integration after S3.0+S3.7+S3.1a)
When:      2026-09-24T19:45Z (25 Sep 01:15 IST), laptop.
Observed:  .venv/Scripts/python -m pytest -q -> **186 passed, 0 failed in
           358.5 s**, run while the wave-2 agents (S3.1b, S3.2) were
           already working on this machine. 146 Phase-2 tests + the 40
           wave-1 tests hold together: schema v2, auth, catalogue,
           analytics, mediamtx harness, all green in one run.
Next:      wave 2 (S3.1b + S3.2), then S3.3, S3.3b, S3.4.
```

```
## S3.1b — DONE (reports, HLS relay, health checker; OpenAPI re-export)
##          [commit 584860d]
When:      2026-09-24T20:15Z (25 Sep 01:45 IST), wave-2 subagent (F59).
Observed:  Ported (F52) from src/api/routes_hls.py, routes_reports.py +
           report.py, ingest/health.py — with the old build's worst habit
           FIXED: the health checker never touches the CDN (regression
           test asserts zero CdnSession calls; paced RTSP ffprobe 2-at-a-
           time, -timeout per F44). Reports render in memory with a
           provenance column, HTML-escaped, CSV formula-prefixed.
           Relay: playlist-membership check on /seg, boundary-exact CDN
           origin, 16-byte key check, 20 s tee freshness; policy recorded
           in api.md — transport='rtsp' cameras NEVER fall to the CDN
           (fresh tee -> stale tee <= 24 h -> 503): their live view is our
           own pull; the CDN copy is a different source. RateLimiter
           wired: route 120/min, reports 60/min, relay 600/min per
           identity. /api/health counts.workers now reads the stats
           snapshot (was hardcoded 0). OpenAPI re-exported.
           Acceptance: test_reports+test_relay+test_health+test_openapi
           -> 28 passed.
Surprise:  starlette normalises dot-segments before routing, so '..'
           traversal names die client-side as 404; the real guard (no CDN
           fetch for off-playlist names) is what the tests assert.
Next:      S3.2 (same wave).
```

```
## S3.2 — DONE (frontend foundation; a real backend defect found by the
##          smoke) [commit b0925d7]
When:      2026-09-24T20:20Z (25 Sep 01:50 IST), wave-2 subagent (F59).
Observed:  Vite 6 + react 18.3.1 (pinned back from the React-19 scaffold),
           ported ui/src (F52): api.js -> lib/api.js on the session cookie
           (no key dialog; 401 -> /login; typed errors to the status
           strip), Header/Tile/FitBounds/MapView, styles.css -> tokens.css
           (the token system). Login built as a hero screen. Pages: Map,
           Cameras (onboarding form, CSV import with per-row results),
           Watchlist. scripts/smoke_frontend.py drives the real
           `python -m backend.app` on a random free port with a temp DB
           and per-run secrets that never touch argv or logs.
           SMOKE PASS 13 assertions (login redirect, viewer sign-in,
           30 pins == 30 cameras, viewer-hidden forms + 403s, CSV
           2-accepted/1-rejected, watchlist round-trip, sign-out).
           REAL DEFECT found by the smoke and fixed in backend/core/db.py:
           FastAPI runs a sync dependency's teardown in a different anyio
           worker thread under concurrent requests, so get_db's close()
           crossed threads -> sqlite3.ProgrammingError 500s on random
           requests (3/4 runs before the fix, 0/3 after).
           check_same_thread=False + regression test tests/test_db.py.
Surprise:  create-vite@6 scaffolds React 19 — pinned back per F28.
Next:      S3.3.
```

```
## Wave-2 follow-ups + full suite — PASS [commits 2365968, 27b91cd]
When:      2026-09-24T21:20Z → 25 Sep 04:10 IST (interrupted by the
           account's usage-limit window ~02:00-02:50 IST; both waves
           relaunched clean after the reset — nothing was lost, the
           interrupted attempts had written no files).
Observed:  Review follow-ups with tests: GET /api/reports/route/{plate}
           now audited like /api/plates/* (B12); cdn_session origin
           check boundary-exact (startswith admitted
           https://<cdn-host>.evil.tld). Two auth-test interactions with
           the new main.py fixed (late-registered fixture route shadowed
           by the SPA catch-all; the route walk now treats the SPA shell
           as the open login page it is, rule 11).
           Full suite: **217 passed, 0 failed in 342 s**.
Next:      wave 3 (S3.3), S3.4 build.
```

```
## S3.3 — DONE (all seven operations screens; smoke 43 assertions)
##          [commits 0b30b57, 8b8e8b8]
When:      2026-09-25T05:35Z (11:05 IST), wave-3 subagent (F59).
Observed:  Command, Live Wall, Search, Route, Alerts, Zones, Reports
           ported from ui/src/pages (F52) onto the S3.2 tokens, with the
           F46 additions: Start here panel (names GJ01AB1234 and real
           local-feed plate MH04JH3316), feed-status strip (no-traffic /
           feed-down / pipeline-dead; stale >90 s heartbeat counts as
           dead), provenance badges everywhere, vehicle-class filter,
           person count. Tile owns ONE retry policy (hls.js internals
           disabled). SMOKE PASS 43 assertions, identical on two runs:
           route/GJ01AB1234 -> 4 timeline entries incl. the ambiguity
           near-miss on 3 cameras/3 departments; SSE card < 3 s through
           a real port; ack persists reload; wall 4 playlist requests
           then 0 after paging destroys the players; class filter;
           viewer gating; pipeline-down strip.
           Follow-up committed same hour: the class filter is now
           server-side in GET /api/sightings (was client-side over one
           page) — api.md + test.
Surprise:  react-leaflet v4 lets a second <Tooltip> silently replace the
           first bindTooltip — caught by the smoke's pin-count assertion.
Next:      S3.3b.
```

```
## S3.3b — DONE (design pass + the F53 review gate) [commit 6f2e120]
When:      2026-09-25T07:20Z (12:50 IST), design pass by a subagent,
           review gate + fixes by the orchestrating session.
Observed:  Design pass BY HAND against frontend/CLAUDE.md — no front-end
           design plugin is installed on this machine (recorded per F53:
           a missing skill is recorded, never a blocker). Applied:
           --text-faint contrast 3.1:1 -> >= 4.5:1; the wall now fills
           1366x768 and 1920x1080 exactly; operator-worded tile errors;
           Route tiles-offline note; pluralisation; route-level
           code-splitting (993 kB -> 212 kB entry + on-demand chunks, no
           new dependency). Smoke extended to **67 assertions**: five
           heroes at both viewports no-horizontal-scroll, designed empty
           states on a fresh DB, status-strip error states with the API
           killed mid-session, hero-*.png at 1920x1080 for the deck.
           Review gate: **/security-review — 0 findings** (parameterised
           SQL, no unsafe React sinks, smoke secrets never in argv).
           **/code-review at high effort — 7 findings, 6 fixed**: landing
           now /command (the Start-here panel is the first screen a judge
           sees — it was /map), Search 'unknown' class no longer queries
           a literal the server cannot match, Safari native-HLS tiles get
           an error overlay + the retry ladder, dead 'auto' class ->
           'bicycle' (+ 'buses'), applyAck coerces alert_seq, a
           background poll's success no longer wipes an unrelated
           status-strip error. 1 answered: DEPT/ROUTE colour literals
           stay in api.js (Leaflet paints SVG attributes where CSS var()
           does not resolve — documented in-file). Build + lint clean,
           smoke 67/67 after the fixes.
Next:      S3.4 walkthrough.
```

```
## S3.4 — DONE (launcher + second system; end-to-end walkthrough on the
##          real platform) [commit 51e1569]
When:      2026-09-25T06:40Z (12:10 IST), build by a subagent, walkthrough
           by the orchestrating session.
Observed:  launch.py ported from the old launcher (F52) — resumable
           ffmpeg fetch, req-hash reinstall stamp, DirectML guard, PID
           file, friendly steps — with the old blanket
           `taskkill /IM ffmpeg.exe` deliberately NOT ported: stop
           touches only recorded PID trees (repo-cmdline guard), after a
           graceful data/stop window. replay_publish --many publishes one
           path per clip, ONCE-through by default with --offsets real
           gaps (F56), --loop explicit, copy mode default. 17 launcher/
           publisher tests green.
           WALKTHROUGH, observed live (11:20-12:10 IST):
           `python launch.py start` -> 9 steps, port bound, browser
           opened; login page serves at :8000 with the audit disclosure;
           `replay-start` -> local01..04 on mediamtx; with
           SENTINEL_ACTIVE_CAMERAS=6 one worker set ran BOTH systems —
           cam06/09/26/27/28 pulled LIVE from the sandbox + local01 from
           mediamtx. 26-min run: 0 restarts, 7,284 frames, 17,565
           detections, **137 sightings (13 REAL live reads on sandbox
           cam06, 124 on local01, 107 unique plates)**; `demo` -> 24
           labelled rows + 4 alerts; `stop` + `replay-stop` -> ZERO
           ffmpeg/mediamtx processes left (tasklist), only recorded PID
           trees touched. sentinel.db now holds real live sandbox reads —
           S4.1's formal 10-minute measurement still owns GATE B.
Surprise:  the .env cap is 5, so local01 only joined at cap 6 (set per
           process for the run). S4.1 should pick the tier deliberately;
           consider SENTINEL_ACTIVE_CAMERAS=6 in .env [Adi].
Next:      S4.1 (GATE B measurement), S3.5 go-live ([Adi] Funnel trial),
           S3.6 ([Adi] filming).
```

```
## S3.5 — PARTIAL (runbook written; go-live gates on Adi's Funnel trial)
When:      2026-09-25T07:40Z (13:10 IST), orchestrating session.
Observed:  docs/runbook-hosting.md written: the 15-minute [Adi] go-live
           block (Tailscale Funnel, mobile-data check, reboot check),
           account creation via backend.tools.users (passwords prompted,
           never in argv/logs; the evaluator password goes ONLY in the
           submission form), SENTINEL_PUBLIC_HOST wiring, the Windows
           power/update/Task-Scheduler settings, a symptom table and the
           one-minute daily check.
Done so far: the runbook and everything S3.0/S3.4 built that it relies
           on. NOT done (physically Adi's): the Funnel trial itself, the
           evaluator + admin accounts, the mobile-data + reboot checks,
           `SENTINEL_PUBLIC_HOST` in .env.
Next:      [Adi] runs runbook §0; then S6.1b adds the watchdog + backups.
```

```
## Phase-3 final suite — PASS (the phase's closing verification)
When:      2026-09-25T08:15Z (13:45 IST), laptop, ports free, platform
           stopped.
Observed:  .venv/Scripts/python -m pytest -q -> **232 passed, 0 failed
           in 330.97 s**. 146 Phase-2 tests + 86 added tonight (auth 24,
           catalogue 4, analytics 14, reports/relay/health 28, db 1,
           cdn_session 3, launcher 9, replay-publish +7 incl. --many),
           including the mediamtx harness. Phase 3 closes verified.
Next:      S4.1 (GATE B measurement); Phase 5 documents (GATE D).
```

```
## S4.1 — PARTIAL (F18 sampler ported, wired and tested; the probe, the
##                 live 10-minute run and the GATE B decision are laptop-only)
When:      2026-09-25T06:45Z per this cloud container's clock — NOTE this
           box reads ~1.5 h EARLIER than the laptop blocks above (clock
           skew between machines); blocks stay in append order.
Observed:  Cloud container (Linux, python 3.11.15, no GPU, no .env, no
           sandbox reach), branch claude/sentinel-progress-check-rrtp9n.
           Phase 3 first validated against the ledger, the gate table and
           the tree: all eight build tasks [x] with acceptance runs and
           commits, GATE C recorded PASS (labelled demo vehicle), S3.5
           [~] runbook-only and S3.6 open — both [Adi]-physical; nothing
           blocks Phase 4. S4.2/S4.3 stay cut (F54), so Phase 4 = S4.1.
           Built (the F52 port): ml/tools/measure_run.py ported from the
           old build's src/tools/measure_run.py (cloned the GitHub mirror
           read-only; the D:\ path is unreachable here). Adaptations and
           defect fixes, each named in the module docstring: samples the
           ALREADY RUNNING platform via data/launcher_pids.txt + psutil
           process trees (launch.py start owns spawning since S3.4; the
           old tool spawned its own and read Windows tasklist CSV);
           deltas over the measurement WINDOW only (the old aggregate
           divided whole-run counters by whole-run uptime, so warm-up
           dragged every sustained number down — F18 wants the
           post-warm-up window); restarts from the supervisor's
           cumulative counter delta, with per-camera counter regressions
           flagged "restarted — unreliable" (the old per-sample uptime
           regression missed restarts between samples). Refuses to run
           cold (< --warmup-min, default 10 min) unless --allow-cold,
           refuses stale stats (> 60 s), exits 2 if a process dies
           mid-window (partial evidence still written). Writes
           data/measurements/<ts>.json + <ts>.md (verified NOT gitignored
           — the evidence commits) and prints the Key-measurements table
           with [measured] tags; VRAM prints "unmeasured (nvidia-smi
           unavailable)" when absent, never invented (rule 8).
           Wired: launch.py measure now takes arguments (--minutes 10
           --sample-s 5 forwarded to .venv -m ml.tools.measure_run);
           usage text updated; _measure_cmd split out for tests.
           New counters for the plate-read-rate denominator (S4.1
           acceptance: full reads / vehicle tracks): worker.stats gains
           ocr_attempts (from FrameResult), full_reads (committed
           consensus reads with kind='full'), vehicle_tracks (unique
           vehicle-superclass tracks via a high-water mark on track ids —
           ids are never reused (S2.3), new tracks appear in matches on
           their creation frame (verified in track.py update()), so each
           counts exactly once in O(1) memory). Supervisor totals +
           snapshot carry the three plus derived plate_read_rate;
           docs/api.md GET /workers updated in the same commit (rule §6.7).
           Acceptance observed here: tests/test_measure_run.py — 10 tests
           (window maths incl. the regression clamp, markdown rows incl.
           the unmeasured-GPU and cold-run wording, refusal paths, a real
           sampled window against this process's own PID writing
           json+md, exit-2 on a killed worker process, the worker-counter
           harness through CameraWorker.run with stub source/pipeline);
           tests/test_launch.py reworked for the argument-taking measure
           (12 tests). Whole suite in this container: **240 passed,
           5 skipped, 0 failed in 199.72 s** (the 5 are the known
           Windows-only mediamtx-harness/PATHEXT skips; laptop parity
           before this session was 227+5 here = 232 there).
Done so far: everything above, committed. The sampler is exercised end
           to end against a fake platform; no live number exists yet and
           none is claimed.
Next:      Laptop (Adi or the next laptop session), the S4.1 run half:
           (1) .venv/Scripts/python -m backend.tools.probe — every
           camera, health for the map; (2) python launch.py start with
           the demo tier (F55: cam06 + up to four live sandbox cameras;
           consider SENTINEL_ACTIVE_CAMERAS=6 so local01 joins);
           (3) confirm real reads accumulate in Search during daylight;
           (4) after >= 10 min warm-up: python launch.py measure
           --minutes 10; (5) paste the printed table over the blank
           "Key measurements" rows above, draw one zone on the busiest
           camera and record whether it fires; (6) fill the GATE B row.
           Phase 5 (S5.1, GATE D) does not wait on any of this — the
           documents can start immediately from complete Phase 3.
```


```
## S4.1 — DONE (the laptop run half: 10-minute live measurement, zone
##          event on a live feed, GATE B PASS)
When:      2026-09-25T08:38Z-08:58Z (14:08-14:28 IST), laptop, orchestrating
           session.
Observed:  The platform found running since 13:48 predated the S4.1 merge
           (stats had no full_reads/vehicle_tracks), so it was restarted on
           main (launch.py stop + start; same tier: cam06/09/26/27/28 live
           over RTSP, SENTINEL_ACTIVE_CAMERAS=5 from .env). A crossing line
           was PATCHed onto cam06 through the real API (admin key read by
           config, never printed; audited): z-cam06-line, medium, points
           [[0.12,0.55],[0.98,0.55]] across the carriageway, traffic moving
           toward the camera (downward — the direction the engine counts).
           After uptime >= 615 s: `python launch.py measure --minutes 10`.
           Window 600 s, 5/5 alive, 0 restarts — the table is in "Key
           measurements" above ([measured]); evidence committed
           data/measurements/20260925-084754Z.{json,md}.
           Live reads: 55 provenance='live' cam06 reads with crops between
           08:37Z and 10:00Z (conf 0.78-0.99). Zone: 53 line_cross events,
           provenance live, clock rtsp-live, 08:44Z-10:01Z — line crossing
           fired on a real feed for the first time (S2.5 proved only the
           geometry).
           VRAM check: nvidia-smi showed 119 MiB / 2 %, which looked like
           DirectML on the Vega iGPU; Windows GPU counters settled it — the
           worker's 120 MB dedicated + 41 % engine load sit on the adapter
           exposing the 'cuda' engine, i.e. the GTX 1650. YOLOX-S is simply
           small.
           Defect found and fixed (regression test
           test_measure_run.py::test_plate_read_rate_is_unmeasured_when_
           worker_predates_read_counters): against a pre-S4.1 worker the
           window maths defaulted the missing counters to 0 and printed a
           plate-read rate "0.0 (0/0)" — a number no code measured (rule 8).
           Now "unmeasured (worker predates the read counters)". 11 passed.
Surprise:  (1) Sustained fps is 0.6-1.5 per camera, well under the 3 fps
           target: the shared OCR lock (F58 surprise 2) is the bottleneck,
           not the GPU. (2) Stored plates keep OCR confusions that the
           structural coercion already resolves for classification only:
           6J23H1548 beside GJ23H1548, GJ1157924 beside GJ11S7924 — search
           and dedupe see two plates. Folded into the ANPR-search work.
           (3) Windows trimmed the worker's working set in the last 25 s
           (1152 -> 187 MB) with no process change — RSS on Windows is not
           a leak signal by itself.
GATE B:    PASS (table above). Continue on this tier; no model tuning.
Next:      the demo fixes Adi asked for (every camera on the relay wall,
           GIS map, ANPR search with demo plates, 28 stock feeds), then
           Phase 5 (S5.1 onward).
```

```
## Demo fixes (Adi's 25 Sep ask) — DONE: every camera on the relay wall,
##          the GIS map, ANPR search with demo plates, 28 stock feeds
##          [merges 563c6ca a173deb 8bf0a86 78f04dd; fixes d94c97b 58a8566
##          9091174, smoke 43cb62b]
When:      2026-09-25T10:00Z-12:00Z (15:30-17:30 IST), laptop, orchestrating
           session + five worktree lanes (Workflow, one branch each).
Ask:       "the demo [should] show live feeds on relay which are stored on
           laptop in archive.zip (give them any coordinates); the map isn't
           proper — load a proper map and GIS; the search window should have
           ANPR and results based upon that with demo plates; I am not able
           to view the cams which we actually got from the sentinel" and
           "make sure the cams (from local and sentinel) run on relay in the
           live wall; GIS should be picture perfect with a MAP".
Root causes found first (orchestrator, before any lane):
           (1) CSP img-src '*.tile.openstreetmap.org' never matches the bare
           'tile.openstreetmap.org' host every TileLayer used -> every map
           tile blocked (the blank map). (2) No media-src/worker-src -> the
           blob: MediaSource URL hls.js attaches to <video> was blocked ->
           NO wall tile could play in a real browser. The smoke never
           noticed: it counted pins and playlist requests, never painted
           tiles or played frames. Fixed in d94c97b with tests/test_csp.py
           (scans frontend/src for tile URLs; fails on the old policy: 2
           failed, passes on the new). (3) The relay refused the CDN for
           every RTSP camera, so 25 of 30 sandbox cameras (no worker) could
           never play. (4) Demo sightings had no crop -> Search showed no
           image for demo plates. (5) Stored plates kept OCR confusions.
Built (five lanes, merged; decisions F60-F67):
           RELAY (F60-F62): tee -> mediamtx HLS (local) -> stale tee < 120 s
           -> organisers' CDN VOD window; single-flight 48 MB segment/key
           cache; breaker; 3,000/min limit; source badge per tile; 1/4/9/16
           grid; filters All/Analysed/Sandbox/Local; ?cam deep link; H.265
           worded where the browser lacks hvc1. scripts/smoke_playback.py.
           GIS (F63-F64): Esri Canvas dark/light + OSM + Esri imagery,
           department layers, FOV wedges, activity (new
           GET /api/cameras/activity), 15 km cluster hulls, gaps, legend,
           scale, cursor readout, camera search, record panel.
           ANPR (F65-F66): plates.coerce() stored at the commit point;
           renormalise_plates applied to sentinel.db (129 rows, 147 -> 134
           live plates; backups data/backup/sentinel-pre-demo-fixes-
           20260925.db and sentinel-pre-renormalise-20260925T110545Z.db);
           GET /api/sightings match=exact|contains|anpr with match types;
           GET /api/plates/suggest; Search rebuilt as ANPR search; DEMO-
           marked rendered crops for every demo row.
           FEEDS (F67): data/local_feeds.csv (28 rows, seeded Ahmedabad/
           Gandhinagar clusters, disclosure in every name) +
           scripts/prepare_feeds.py (all 28 transcoded: 343 MB outside the
           repo; libx264 - NVENC failed "Invalid argument"); mediamtx HLS on
           127.0.0.1:8888; replay_publish --register; launch.py start/stop/
           status run the feeds; seed_registry upserts them; the supervisor
           picks catalogue cameras first. Orchestrator override: every stock
           feed fps_tier='registered' (view-only) - a looped clip analysed
           on the platform DB would re-store its plates as 'live' each loop.
Integration observed (merged tree, platform stopped):
           pytest 344 passed, 0 failed (351.9 s). frontend lint clean, build
           OK. smoke_playback.py in real Edge 153: 28/28 PASS — local feed
           plays (readyState 4, +4.01 s), ?cam 1-up plays, the CDN branch
           (local stand-in with the sandbox's contract) plays in two pages
           with 4 upstream segment fetches for 12 browser requests, key and
           playlist once, H.265 worded, 0 CSP violations. smoke_frontend.py
           first FAILED "fresh registry seeded with 30 cameras (got 58)" -
           the lanes each passed alone; the seeder now adds the register -
           fixed to 30 + register rows -> 87/87 PASS.
Live platform (launch.py start, real sentinel.db, real Edge, viewer via
           the X-API-Key script path routed to 127.0.0.1:8000 only):
           28/28 feeds publishing; map 80 tiles painted, 0 CSP messages;
           Local-feeds wall 4/4 playing (+2.2..+4.0 s over 4 s); cam09 and
           cam27 play from their tees; cam06/cam26 (H.265) worded in Edge;
           ANPR search GJ11S7924 -> 8 reads, 9 crop images loaded; Route
           GJ01AB1234 renders with DEMO crops.
Surprises: (1) the organisers' CDN origin went DOWN at ~16:40 IST - every
           login answers Cloudflare HTTP 521 (one credential-free curl of
           the root: 521); the relay backs off (jittered, capped) and tiles
           say "Organisers' CDN not answering". Non-analysed sandbox tiles
           cannot play until it returns; nothing on our side to fix.
           (2) cam26 (H.265, 2560x1440) drops its gateway pull every ~2 min
           and earlier got RTSP 401 for ~30 min; health passes alternate
           "26 online" with "0 online, 25 offline" - the gateway, not us.
           (3) Health slept 300 s before its first pass -> "1/58 online"
           for 5 min after every start (fixed, F69, regression test).
           (4) Command's Start here called the stock clips "our own filmed
           feeds" and named MH04JH3316, which this DB never held - rewritten;
           the plate to try is now the top live read from /plates/suggest.
           (5) Two of Command's four tiles were H.265 -> "open in Chrome" in
           Edge; tiles are now ranked by what this browser can play (F62).
           (6) The feed publisher once died at birth (rc 0xC000013A) after a
           stop+start while a smoke ran; not reproducible alone; start now
           retries it once (regression test).
Next:      review gate (F53) over d94c97b..HEAD; S5.2 deck + S5.3 reports.
```

```
## S5.1 — DONE (HLD corrected against architecture Part C/Part D;
##          PDF re-rendered) [lane commit a9be422, merged 3518e00]
When:      2026-09-25T10:50Z, HLD lane (worktree), checked by the
           orchestrator after the merge.
Observed:  deliverables/HLD.md rewritten against every S5.1 bullet and the
           session's additions; `grep -c "\[measured\]" deliverables/HLD.md`
           -> 6 = the six [measured] rows in Key measurements (all in HLD
           §7.1). Part C: 15 rows, each fixed or retained with a reason
           (tracker = IoU not ByteTrack; "never written to disk" -> self-
           overwriting 20 s relay window; audit + login/roles as built;
           Pipeline 3 described, not built; HLS fallback for viewing only;
           retention/DPDP note; ffmpeg GPL disclosed as a separate binary -
           libx264 only in prepare_feeds/--reencode). §8 gains an
           estimated implementation + operating cost, all [model] (F68).
           Two internal inconsistencies of the 15 Sep HLD fixed: the WAN
           2.1 Mbps / 3,750x pair, and matching described as plain
           Levenshtein (contradicting F21). Rendered with pandoc 3.8 ->
           HTML -> Playwright PDF: 19 pages, diagram on page 2 checked by
           eye. Orchestrator follow-up: the basemap licensing line named
           CARTO, which the GIS no longer uses - corrected (58a8566).
Next:      re-render the PDF if later tasks change what the HLD describes.
```

```
## S5.3 — DONE (reports, OpenAPI, sample dataset, Model 2 note regenerated
##          from the live DB) [commit dd18db2]
When:      2026-09-25T11:45Z (17:15 IST), deliverables agent; checked and
           committed by the orchestrator.
Observed:  scripts/export_deliverables.py (new; one command) wrote, from
           data/sentinel.db read-only through the platform's own report
           services: detection-report.{csv,html} 263 rows (239 live/rtsp-
           live: cam06 115 + local01 124; 24 demo), route-GJ01AB1234.
           {csv,html} 4 stops (3 exact cam06/cam10/cam09 + the ambiguity
           near-miss), gap-analysis-report.html (58 cameras, 9 isolated),
           registry-api.json (OpenAPI 3.1, 35 paths / 41 operations incl.
           /api/hls/{cam}/source, /mtx/{name}, /api/cameras/activity,
           /api/plates/suggest, sightings match=; no snapshot.jpg),
           sample-camera-dataset.csv (58 rows with a first-line disclosure),
           departmental-systems-unaffected.md (722 words). Credential sweep
           of every output: no userinfo URL, no sandbox IP or CDN host.
Surprise:  the organisers' sandbox went down mid-generation (CDN 521 from
           16:44 IST; RTSP 401 on all five cameras 16:59-17:14 IST), so the
           gap report shows 28 online / 30 offline-or-degraded and carries
           a note saying why. Re-run `.venv/Scripts/python
           scripts/export_deliverables.py` (without --gap-note) once the
           sandbox is back for a clean snapshot.
```

```
## S5.2 — DONE (deck rebuilt from live captures; PDF via PowerPoint)
##          [commit 8bc9ca8]
When:      2026-09-25T12:10Z (17:40 IST), deliverables agent; checked and
           committed by the orchestrator.
Observed:  Fresh 1920x1080 captures of the running platform (viewer via the
           X-API-Key script path routed to 127.0.0.1:8000 only; admin key
           for the Zones/Reports page views only; H.265 walls in headless
           Chrome, the rest in Edge): Command with four playing tiles
           (cam09/27/28 over RTSP + local01), GIS default + zoom-15 record
           panel with FOV sectors, Local-feeds wall, Analysed wall, ANPR
           search (top live plate, GJ11S7924 on cam06, the GJ01A81234 typo
           finding the hero), Route, Alerts, Reports, Cameras, Zones.
           build_deck.js: captions describe live captures (the dev-capture
           grep prints nothing); claims follow the corrected HLD (IoU
           tracker; login/roles/audit built; relay not recorded; Pipeline 3
           not built; every camera on the relay wall; GIS; ANPR search; 28
           disclosed stock feeds; WAN ~23 Mbps [model]; [measured] only for
           S4.1). Slide 18: repo link; hosted URL and video links "to be
           added at submission". pptxgenjs 4.0.1 installed locally under
           deliverables/deck (node_modules ignored). 18 slides; pptx
           10.4 MB; PDF 18 pp exported through PowerPoint (LibreOffice is
           not on this laptop). The workflow diagram SVG text was corrected
           to the HLD (it still said NOTHING SAVED, RT-DETR, Levenshtein,
           2.1 Mbps/3,750x) and exported to PNG, shown in README.md.
Next:      when S3.5 gives the hosted URL and S5.4 the videos, fill slide 18
           and rebuild (node deliverables/deck/build_deck.js).
```

```
## Review gate F53 over the day's diff — 19 findings, 17 confirmed, 2
##          refuted; the critical one fixed at once [commit 69b2e4b]
When:      2026-09-25T12:15Z-14:30Z, workflow: three finders (security /
           backend / frontend) over d94c97b..HEAD, one skeptic per finding
           told to refute by default.
Observed:  CRITICAL (pre-existing since S3.1b, found by two finders
           independently): GET /api/hls/%2E%2E/local/sentinel.db returned
           the database - raw session ids included - to any viewer
           credential (_SAFE_NAME admitted '..', uvicorn percent-decodes,
           local_segment never looked the camera up). Reproduced by the
           verifier on TestClient and a real uvicorn. Fixed: camera id must
           match CAMERA_ID_PATTERN and exist, name must be a .ts segment,
           the resolved path must stay inside the tee folder; regression
           test fails on the old code, passes on the new (31 relay tests).
           The platform is bound to 127.0.0.1 and not yet published (S3.5),
           so no exposure beyond this laptop.
           The other 16 (one a duplicate of the above): relay - CDN segments
           not limited to the served window (rule 6), redirects bypassing
           the origin guard, pacing waits while the breaker is open, re-
           login not single-flight; backend - health filled the sandbox
           credentials into ANY template host (an evaluator-registered
           camera could harvest them), activity counted demo alerts as live,
           launcher trusted a stale replay pid; frontend - 8 low/medium UI
           defects. Refuted: seed_registry overwriting admin edits of the
           register rows (by design: the register is the source of truth
           for local feeds), a hull tooltip reappearing.
Next:      the 15 fixes run in three worktree lanes (relay, backend,
           frontend), each with a regression test.
```

```
## Review fixes — DONE (all 17 confirmed findings fixed, + 2 more credential
##          paths closed) [69b2e4b; lanes 36bba23 e21087e 26d0fae merged
##          f884be0 79c657e 22d09eb; ebb1167; dbc2f90]
When:      2026-09-25T14:30Z-16:10Z, three worktree lanes + orchestrator.
Observed:  relay (36bba23): CDN /seg and /key refuse anything outside the
           window actually served to a viewer in the last 60 s (rule 6 - the
           relay was an authenticated 12 h download proxy); CdnSession checks
           EVERY redirect hop against the CDN origin; an open breaker never
           queues behind the playlist pacer; CDN re-login is single-flight.
           backend (e21087e): the health probe fills sandbox credentials only
           for the sandbox gateway host; /cameras/activity splits alerts by
           provenance (demo alerts never count as live); the launcher checks a
           recorded replay pid's command line. frontend (26d0fae): honest
           cluster tooltips (distinct plates not summed), hulls follow the
           department toggles, Tile stall-vs-retry overlay, HEVC gating only on
           real codec errors, the real hls.js 1.7 loadPolicy keys, no live dot
           on a blocked tile, an iOS/iPadOS HEVC probe, Search's match-mode
           re-run from a non-normalised ?plate= link.
           Orchestrator, beyond the list (ebb1167): the WORKER's resolve_url
           also filled the credentials into any template host, and POST
           /api/cameras let an evaluator create an active catalogue camera the
           worker picks first - together an evaluator account could steer the
           organisers' credentials to its own server. One shared gate,
           config.is_sandbox_gateway(); non-admins get 403 for active/catalogue
           onboarding. The old resolve_url test ASSERTED the leak (10.0.0.5
           filled) - it now asserts the opposite. (dbc2f90) Command's plate to
           try named a stock clip's read as "a real live read": suggest's
           top_live now carries camera_ids and Command prefers - and names - a
           read on an organisers' camera.
           Every fix has a regression test shown to fail on the old code (the
           four frontend defects a browser can show are smoke assertions; the
           other four are reasoned against the hls.js 1.7.3 source).
           Final verification, platform stopped: pytest **360 passed, 0
           failed** (392 s); smoke_frontend **92/92**; smoke_playback **28/28**
           in real Edge; registry-api.json re-exported (35 paths, camera_ids,
           the live-window wording).
Next:      Current state (below); [Adi] items.
```
