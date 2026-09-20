# P7 — Enhancement Plan: multiplying Sentinel

**Produced:** 2026-09-20 · **Method:** 9-agent deep code review of every subsystem (ingest, ANPR, API/storage, analytics/alerting, UI, ops, docs, plus dedicated security and correctness passes), followed by 4 strategy lenses (demo impact, pilot readiness, ML accuracy, solo-dev pragmatics), 7 adversarial feasibility checks (several **measured on this laptop**, not guessed), and a completeness critique. Every defect below was verified against code with file:line references. Where a number says *measured*, code actually ran on this machine; everything else is labelled modelled/estimate, per CLAUDE.md rule 8.

**Verdict on the current system:** a genuinely working, unusually disciplined 2-day build — PTS timing, credential masking, persist-before-alert and one-pull-per-camera are real, not aspirational. But it carries ~10 high-severity latent bugs that detonate exactly during long runs and demos, its accuracy is capped by four removable ceilings, and it has zero version control, zero tests, and an unfinished deliverable layer. The multipliers are real and cheap; the order matters more than the list.

---

## 0. The defect register (fix-me-first facts)

Cross-corroborated by at least two independent reviewers each.

| # | Sev | Defect | Where |
|---|-----|--------|-------|
| D1 | CRIT | HLS source goes **silent ~12 h** after the recording wraps (`last_yield_pts` never reset) + CDN re-fetch busy-loop at the wrap instant | `src/ingest/frame_source.py:237,248-250` |
| D2 | CRIT | **Zero auth** on every endpoint incl. watchlist add/delete, camera registry, alert ack; plate crops (PII) served openly; no CSRF/DNS-rebinding defense | `src/api/*` |
| D3 | HIGH | **Two incompatible time bases**: RTSP sightings stamped `now()`, HLS/harvest stamped RECORDING_EPOCH (June 2026, set in UTC though the footage clock is IST). Cross-camera route — the one scored feature — breaks whenever transports mix; per-camera loop-length drift adds skew every wrap | `frame_source.py:391,436`, `timeline.py:37-67` |
| D4 | HIGH | Alert IDs allocated `COUNT(*)+1`: thread race loses alerts; after `demo-clear` the PK collision **permanently kills all later alerts that day**. SSE cursor uses reusable implicit rowid → missed alerts after purge | `matcher.py:106-110`, `routes_analytics.py:186-200` |
| D5 | HIGH | High-severity **zone/intrusion alerts never reach the dashboard** — broadcast on an in-process bus with no subscribers in the worker process; API tails only the alerts table | `worker.py:72-75`, `routes_analytics.py:170-219` |
| D6 | HIGH | Route reconstruction is **O(entire sightings table)** with per-row Python Levenshtein; watchlist match is a linear scan per sighting. Also *semantic*: plain Levenshtein≤1 merges neighbouring real registrations (GJ01AB1234 vs …1235) into one route | `route.py:56-79`, `matcher.py:64-77`, `plates.py:122-124` |
| D7 | HIGH | SSRF/open relay (arbitrary `hls_url` fetched server-side; segment `name` un-validated → `urljoin` escape), reflected **XSS** in detection report params, unconstrained `camera_id` flows into filesystem write paths | `routes_hls.py:200`, `report.py:148-149`, `schemas.py:17` |
| D8 | HIGH | API correctness: pagination `total` ignores filters; time-range filters compare mixed-format ISO strings lexicographically (silently wrong results); `events` (highest-write table) has **zero indexes**; sync SSE + blocking relay can starve the ~40-thread pool | `routes_analytics.py:51-53,43-45`, `db.py:100-110` |
| D9 | HIGH | Ops: Windows children write **no log files** though errors point at `data/api.log` (regression of a fixed bug); health checker holds a SQLite **write txn across minutes of network probes**; no RTSP stall watchdog (half-open TCP hangs a camera forever, supervisor blind); WMIC sweep dead on Win11 24H2; `stop()` kills every ffmpeg.exe machine-wide | `launch.py:305-315,383-387,379`, `health.py:67-95` |
| D10 | MED | OCR **first-read latch**: one confident wrong read permanently poisons a track (never re-read); global OCR lock ≈450 ms/crop caps the fleet at ~2.2 crops/s; detector lock caps ~20 inferences/s | `pipeline.py:104-136`, `ocr.py:49-52` |
| D11 | MED | Plate grammar **rejects BH-series** (`##BH####LL`) → an entire national registration class is invisible; no state-code whitelist; regex duplicated in two files | `plates.py:76`, `ocr.py:30` |
| D12 | MED | `roi_json` dead code end-to-end; dedupe window has no upper time bound (out-of-order writers swallow real sightings); object-event throttle not reset on stream restart (hours of silent suppression); zone edits need a worker restart; cooldowns keyed on wall clock not PTS; `elapsed==0` hides the cloned-plate teleport signal | `pipeline.py`, `sightings.py:85`, `zones.py`, `route.py:107` |
| D13 | MED | UI: `critical` severity renders unstyled on the Alerts page; failed zone save reports “saved”; **all timestamps shown as raw UTC** to IST operators (RouteView even drops the date); `.catch(()=>{})` everywhere — no way to tell “quiet night” from “pipeline dead”; Alerts list grows unbounded; OSM attribution disabled on Dashboard (ODbL violation, live today) | `ui/src/pages/*`, `ui/src/api.js:36-38`, `Dashboard.jsx:91` |
| D14 | MED | Supply chain unpinned: ffmpeg “latest” zip and YOLOX weights downloaded with **no checksum**; requirements mostly unpinned (DirectML pip dance is a symptom); credentialed RTSP URLs visible in process argv | `launch.py:41-44`, `fetch_models.py:22`, `requirements.txt` |
| D15 | MED | Deliverable integrity: HLD claims `[measured]` anchors that were **never measured** and claims ByteTrack while the code is an IoU stand-in; demo videos never recorded; deck ships synthetic screenshots; harvest (the only true end-to-end run of the scored path) **never executed**; repo has **no git and no tests** | `deliverables/HLD.md`, `STATUS.md:28-31` |

---

## 1. Phase 0 — Preserve the ability to work at all (days, do first)

The completeness critic's sharpest finding: **the sandbox CDN can be decommissioned any day now that the challenge has closed.** Every verification below — wrap fix, timeline fix, harvest, eval harness, demo videos — depends on that footage. This is the only time-critical work in the plan.

- **0.1 Footage archive (URGENT).** While the CDN is alive, bulk-download hours of HLS segments + `enc.key` for at least the 6–8 route-plausible cameras (respect the rate limiter: sequential, throttled, overnight). Store under `archive/` (gitignored).
- **0.2 Local replay stack.** Static HLS server over the archived segments + `mediamtx` RTSP replay (already used once, per STATUS.md). Deterministic: fixed epoch, controllable loop length → this becomes the substrate for wrap-simulation, soak and fault-injection tests. After this, Sentinel develops forever without the sandbox.
- **0.3 `git init`** with a PII/secret-safe `.gitignore` (`.env`, `data/`, `archive/`, `tools/`, `.venv/`, `models/`, `Claude outputs/`, `__pycache__/`) — **verify `.env` is excluded before the first commit** — then tag `v1.0-submission`. Three of the bugs found are regressions of things that once worked; unversioned surgery caused that.
- **0.4 Fix the Windows logging regression** (`launch.py` spawn: detached children with stdout/stderr appended to rotating `data/logs/*.log`; keep `cmd /k` as a `--windows` debug mode). Every later fix is verified through logs.
- **0.5 Regression-test scaffolding** (pytest): seed only with tests for bugs being fixed — plate-grammar table, dedupe matrix, alert-ID hammer, wrap simulation against the replay stack, SSE cursor across deletes, route fixtures. Rule from here: **one fix, one test, one commit**; smoke-run before every stopping point.

## 2. Phase 1 — Correctness: the system stops silently degrading (week 1)

The WS1/WS2 batch. ~14 small fixes; land individually, not as a mega-commit (an honest week of evenings, not an afternoon).

- **Ingestion:** reset `last_yield_pts` on wrap/resync + fix the wrap wait-branch (D1); RTSP stall watchdog (no frame for N s → kill ffmpeg → existing backoff) + `-rw_timeout`; health checker probes first, writes after, in one short transaction (D9); motion-gate and object-event-throttle reset on `stream_restart` (D12); dedupe upper time bound; atomic `worker_stats.json` writes.
- **Alerts:** `alert_seq INTEGER PRIMARY KEY AUTOINCREMENT` (display id derived from it, never from `COUNT`); SSE cursor on `alert_seq` with `id:` frames + `Last-Event-ID` replay; **one background tailer** in the API that also tails high-severity zone events (fixes D4 + D5 in one pass); cooldowns keyed on stream time.
- **API:** pagination totals reuse the row-query WHERE; one timestamp-canonicalisation helper at the boundary (parse any ISO form → stored `+00:00` form); `events` indexes (`occurred_at`, `(camera_id, occurred_at)`); route exact-first pass in the matcher; `elapsed==0` between different cameras → `suspect=true, elapsed=0` (turns a bug into the cloned-plate headline feature later).
- **UI truthfulness minimum:** unify the SEV map (critical unstyled), check `r.ok` in `api.js` (zone save lying), one `formatTs()` in IST via `Intl.DateTimeFormat` replacing every `slice()` call, restore OSM attribution.

**Acceptance for the phase:** a soak on the local replay stack across ≥2 simulated wraps with zero silent camera deaths; alert fired → purge → alert fired again, both delivered over SSE.

## 3. Phase 2 — One migration wave + the first real end-to-end run (weeks 2–3)

Schema changes get an order of magnitude harder once real data accumulates. Do them as **one coordinated migration** (add a `schema_version` table + ordered migration scripts — the repo has none):

- **Timeline unification (D3):** every sighting gets `stream_time`, `wall_time`, `clock_source` (`rtsp-live | hls-vod | harvest | demo`); RTSP mapped through `timeline.py`; RECORDING_EPOCH anchored to the footage's burned-in IST clock so displayed times match the pixels; route orders within a clock domain and **refuses cross-domain speed math with an explicit warning field**. Update `03-data-contracts.md` in the same commit (binding).
- **`plate_canonical` column + index** on sightings and watchlist (ambiguity-fold at write time) → route and watchlist matching become index probes instead of table scans (D6). Add a SymSpell-style deletion index for Levenshtein candidates second. Replace binary Levenshtein with **confusion-weighted distance** (ambiguity-class subs cheap, arbitrary subs expensive) — this is the fix for the neighbouring-registration merge, a precision bug at any scale.
- **Provenance labels** (`live|harvest|demo`) surfaced in Search, RouteView, and both report exports — demo rows can never masquerade as real detections again.
- **Then run the real thing:** harvest v2 (checkpointed per-camera segment index, prefetch next segment while GPU infers, `--range` targeting the daylight tail, fix the shadowed skip-rate gate at `harvest.py:105/143`) across the archived footage → a genuine plate on ≥2 cameras. Run the 10-minute measurement (instrumentation exists), fill the four blank anchor rows in STATUS.md, and **reconcile the HLD**: `[measured]` claims become true or relabelled, the ByteTrack claim becomes an honest paragraph. One caught fabrication multiplies the whole submission by ~zero; this closes that exposure for a day of work.

## 4. Phase 3 — Security & institutional surface (parallel slices, weeks 2–4)

The demo runs on loopback, so this doesn't outrank Phase 1 — but it is a hard gate for any pilot, and most of it is S-effort.

- **Minimal auth:** one FastAPI dependency, `X-API-Key` header (forces CORS preflight → kills the CSRF hole), roles `viewer`/`admin`; `/crops` behind auth; `TrustedHostMiddleware`.
- **Close the injection cluster:** pin relay fetches to `config.CDN` origin + `_SAFE_NAME` on `hls_segment` name + playlist-membership check; `_esc()` the two report interpolations (XSS); `camera_id` pattern `^[A-Za-z0-9_-]{1,64}$` + path-containment asserts; 16-byte check on the proxied AES key; CSV formula-prefix escaping.
- **Audit + governance (the police-grade differentiator):** append-only audit table (actor, action, entity, before/after, ts) via middleware for every mutation **and every plate/route query** — operator-misuse lookups are the documented ANPR scandal pattern and a headline procurement control. Watchlist entries get reason/authority/expiry (auto-lapse job).
- **Supply chain:** `requirements.in` + environment markers (`onnxruntime-directml; sys_platform == "win32"`) + hash-locked lockfile (kills the DirectML pip dance permanently); SHA-256 pins for the ffmpeg zip and `yolox_s.onnx`, verify before extract/use.
- **Retention/DPDP posture:** configurable TTL purge per data class (sightings N days; non-hit crops much shorter; watchlist-hit evidence longer, under case reference), storage watermark eviction, one-page data-protection note in the HLD. Cheap on SQLite; a genuine differentiator in a government evaluation.

## 5. Phase 4 — Accuracy multipliers (weeks 3–5, harness-gated where marked)

The value chain is `detection recall × track stability × OCR accuracy × consensus × matching semantics`. These compound. Verified recipes in the appendix.

**Safe to ship blind (provably monotone):**
- **A1. Kill the first-read latch → track-level consensus voting** (~100 lines in `pipeline.py`): keep OCR-ing on the existing budget until N agreeing reads or track death; per-character majority vote weighted by confidence; update the deduped sighting to the consensus. The single worst accuracy mechanism in the codebase, removed.
- **A2. BH-series grammar + state-code whitelist + position-aware ambiguity coercion** in `plates.py` (export the regexes; delete the `ocr.py` duplicates). An invisible vehicle class becomes visible — infinite relative recall gain for an hour's work.
- **A3. Tracker superclass match** (~5 lines): stop fragmenting tracks on YOLOX car↔truck flips — the highest value-per-line change available. Per-class NMS in the detector alongside it.
- **A4. Wire `roi_json` end-to-end** (the parameter already exists on `detect()`): mask detection + motion gate per camera; replace the hard-coded caption band with a per-camera exclusion zone. Redirects the scarce OCR budget at plate-bearing pixels.

**Build the instrument, then iterate measured:**
- **A5. Ground-truth eval harness:** label ~300 harvested frames (pre-labelled by the current pipeline to cut tedium), script plate-level precision/recall/CER + ID-switch metrics. Every model change below promotes only on measured parity-or-better. This also discharges the measured-vs-modelled debt permanently.
- **A6. Plate localisation + rectification.** *Rejected by feasibility check:* `open-image-models` YOLOv9 plate weights (GPL-3.0 provenance — fails the same test the project applies to Ultralytics). **Primary:** `Topurrra/rtdetr-license-plate-detection-onnx` (Apache-2.0, RT-DETRv2 — already the whitelisted alternate family in `02-hard-constraints.md`). **Zero-cost fallback that ships value regardless:** PaddleOCR's DB detector already returns 4-point quads (`rec_polys`, parsed in `ocr.py:155-172`) — perspective-warp the quad and **upscale the plate sub-region instead of the whole vehicle crop** (lift the 4× cap for it). At 10–25 px plates the binding constraint is resolution, not localisation.
- **A7. Fast plate OCR cascade** (*measured on this machine*): `fast-plate-ocr` cct-xs-v2 = **9.5 ms/crop p50 CPU** (vs 450 ms Paddle) — but recognition-only; with localisation it's ~6× per-crop end-to-end, and **10–25× fleet-wide once the global lock is dropped** (ONNX CPU sessions are thread-safe). Mandatory gates: India is **absent from the model's 65 training regions** → side-by-side eval vs PaddleOCR on harvested GJ crops before promotion; two-line plates need an aspect-ratio split (verified: whole two-line crop reads garbage, split halves read perfectly); install with `pip install --no-deps` to protect `onnxruntime-directml`; keep Paddle as low-confidence arbiter.
- **A8. Kalman tracker (BYTE-style)** — honestly ~200–250 lines plus `detect.py` changes (the 0.1–0.35 low-score band is currently discarded at `detect.py:123`; the second association stage needs it), variable `dt` from PTS (reference impls assume dt=1 and MotionGate makes sampling irregular). **Do not copy ByteTrack's `kalman_filter.py`** — it descends textually from GPL-3.0 `nwojke/deep_sort`; reimplement from equations or reference filterpy (MIT). Promote on measured ID-switch reduction. Value cashes through A1's consensus.

## 6. Phase 5 — Capacity (selective; after accuracy is measured)

*Measured verdicts — the guesswork is gone:*

- **C1. NVDEC decode (VERIFIED FEASIBLE on this GTX 1650, driver 512.78, stock BtbN build):** decode CPU drops **~6× per camera measured** (36% → 5.8% of a core); ~129 MB VRAM/session; **no NVDEC session cap** (that cap is NVENC-only, and the TU117 “Volta engine” caveat is NVENC-only too); 8 concurrent 1080p sessions = 1 029 MiB VRAM, GPU 9% busy. Exact command in the appendix. Hidden cost: **+~200 MB system RAM per camera** — budget it. Ship behind `SENTINEL_HWACCEL=cuda|d3d11va|none` (hard-coded `hwdownload` dies if decode falls back to software; the knob + existing backoff-restart is the safety story). Gate rollout on one live camera surviving the GOP-replay join garbage.
- **C2. Batched detector (VERIFIED: 3.0× at batch 4, measured 21.5 → 7.1 ms/frame; 287 MiB VRAM):** dynamic-batch patch of `yolox_s.onnx` is a 50-line offline script (bit-exact, no retraining) — but on DirectML the session **must** be created with `add_free_dimension_override_by_name('batch', 4)` and every batch padded to 4 (it crashes at batch>1 otherwise, measured 80070057). Single consumer thread + ~40–50 ms batch-formation timeout replaces the run-lock. Keep YOLOX-S at 640 — batch-4 capacity (140 fps) is ~6× worst-case demand; don't pay YOLOX-Tiny's small-object accuracy cost.
- **C3. ~~FP16 on DirectML~~ — REFUTED by measurement:** 1.5–1.8× *slower* than FP32 on this GPU under the DML EP (37.4 vs 20.4 ms at batch 1). The 2× Turing figure is only reachable via CUDA/TensorRT, which the 512.78 driver rules out. Move FP16/TensorRT to the production HLD only.
- **C4.** HLS `grab()`-only decode of non-sampled frames; single-writer DB thread with `BEGIN IMMEDIATE` (kills the lock class at its root and makes dedupe/cooldown atomic); event write batching + hourly rollups + retention.
- **Deferred deliberately:** repository layer/Postgres port (premature until a pilot's concurrency is real — indexes + single-writer solve the measured pain on SQLite), central inference *service* beyond C2.

## 7. Phase 6 — Evidence, analytics & operator experience (weeks 4–8, demo-facing)

- **E1. Pipeline 3 made real:** on alert, copy last N + next M segments of the camera's existing HLS tee (stream-copy, no re-encode), concat, SHA-256, fill `alerts.clip_path/clip_sha256` (schema exists, unpopulated), serve + play from the alert card. Closes the largest claim-vs-code gap; the most police-relevant demo beat. Add the rolling frame ring buffer → `sightings.frame_path` backfill on hits.
- **E2. Case/FIR linkage + evidence certificate:** an investigation entity tagging searches/routes/alerts/exports with an FIR/CCTNS reference; exports carry a hash manifest + a **Bharatiya Sakshya Adhiniyam s.63 certificate template** — the difference between “analytics demo” and “tool an IO would use”.
- **E3. Road distances (VERIFIED: one OSRM `/table` call returned the full 30×30 matrix in 1.28 s, 0 nulls):** store all 870 ordered cells in `camera_distances` with `freeflow_duration_s` as the physical lower bound for impossible-transit checks. Measured circuity: median 1.19, **p90 1.92, Junagadh→Navsari 2.00** (the road rounds the Gulf of Khambhat) — a flat haversine×1.3 fallback is refuted; label fallbacks `modelled`. Add ODbL/OSRM attribution.
- **E4. Analytics wow pack** (only after the timeline fix — on mixed clocks these launder errors into confident-looking intelligence): journey-time baselines per camera pair → impossible-transit/cloned-plate flags; convoy/companion detection (pure SQL self-join — a one-evening feature with outsized demo impact); per-camera read-rate/confidence trending → degradation alerts + ranked maintenance worklist (the sandbox's 16 dead cameras make this demonstrable immediately).
- **E5. UI, in this order:** shared data layer + connection-status strip (kills the silent-failure class; one poller instead of Header+Dashboard double-polling); alerts ops console (sound + Web Notification on critical, filters, capped/virtualised list, detail drawer, `<Link>` routing with encoded plates, no route link on zone alerts); **route timeline playback** (animated marker along the polyline, step keys, enlarged crops, printable one-pager export) — the 60 seconds that decides any demo; live wall DVR seek + jump-to-alert-time (the VOD relay already supports it) + self-healing tiles (`recoverMediaError` + jittered retry) + periodic camera refresh; investigative search (expose the filters the API already accepts, pagination, CSV export); zone editor v2 (naming, drag-edit, snapshot underlay, hot-reload push to workers via the supervisor poll — removes the “restart the worker” instruction).
- **E6. Offline dark basemap (VERIFIED path):** `pmtiles extract` of Gujarat (est. 0.3–1.2 GB — record the real size as measured) served by the existing FastAPI `StaticFiles` (installed Starlette 1.6.0 handles Range requests — verified in source); `protomaps-leaflet@5.1.0` (BSD-3-Clause, dark flavor, Canvas/CPU so zero VRAM) via a ~20-line `useMap()` wrapper. *Do not* implement `leaflet.offline` pre-seeding — explicitly prohibited by the OSMF tile policy; CARTO is an online-only stopgap that now requires an API key.

## 8. Phase 7 — Productisation & handoff (month 2+)

- Real supervisor: psutil process-tree sweep (WMIC is dead on Win11 24H2; stop killing every ffmpeg on the machine), crash-loop damping, desired-state reconcile (stop workers whose cameras leave the active set), interruptible sleeps (`event.wait()` not `time.sleep()`) + Windows Job Objects so ffmpeg children never orphan.
- `doctor` preflight (env, ffprobe, DML provider, model SHA, AES decrypt, CDN/replay reachability, DB writability) — fold counters here and into the UI status strip rather than building a Prometheus endpoint nobody scrapes on a single box.
- Backup/DR: scheduled `VACUUM INTO` snapshots + evidence-dir sync + a tested restore drill + documented RPO/RTO — the SQLite file *is* the chain of custody.
- Soak/fault harness on the Phase-0 replay stack: accelerated-wrap soak, full-fleet load run (produces the RAM/VRAM/CPU envelope), fault injection (kill ffmpeg mid-GOP, black-hole TCP, corrupt segments, kill -9 mid-write, disk-full). Note: unit tests would not have caught either CRITICAL bug — both are soak-class.
- Offline venue bundle (wheelhouse + models + tiles + Paddle models pre-fetched); in-process AES in `measure.py` (drop the undeclared `openssl` dependency); `pyproject` + `sentinel` CLI entry point; as-built architecture doc, operator runbook, ADRs (why not Ultralytics, why SQLite, why PTS-only…).
- TCO section for the HLD from the measured envelope: cameras-per-node, what a used RTX 3060 12 GB buys over the GTX 1650, edge-vs-central topologies, 100/1000-camera BOM.

---

## 9. Explicit do-NOT-do list (agreed across lenses)

- **FP16 under DirectML** — measured slower; production-HLD material only.
- **TypeScript migration of the UI** — high effort, zero user-visible value solo; generate types for the new data layer only.
- **Postgres/PostGIS port now** — SQLite + indexes + single-writer carries a 10–30 camera pilot comfortably; build only the seam.
- **Full Gujarati i18n now** — the actual operator pain is the UTC display bug (fixed in Phase 1); translate once a pilot commits.
- **YOLOX-Tiny** — capacity is no longer the constraint after C1/C2; the small-object accuracy cost lands exactly where ANPR hurts.
- **Copying ByteTrack's `kalman_filter.py` or using `open-image-models` YOLOv9 plate weights** — GPL lineage in a state-owned stack.
- **`leaflet.offline` pre-seeding of OSM tiles** — prohibited by the OSMF tile policy.
- **Training or fine-tuning any model** — standing rule; it is also why LPRNet-class (Chinese-plate) candidates are rejected.
- **Refactor-for-elegance of working modules; a test suite for its own sake** — the constitution's rules still hold.

## 10. Sequencing at a glance (solo developer)

| When | What | Why it's first |
|---|---|---|
| **Now (days)** | Phase 0: footage archive + replay stack, git init + tag, logging fix, test scaffold | Sandbox may die any day; everything else is unverifiable without it; no rollback exists |
| **Week 1** | Phase 1 correctness batch (wrap stall first), alert integrity, UI truth minimum | Stops silent degradation; the demo-reset alert bomb is defused |
| **Weeks 2–3** | Phase 2: one migration wave (timeline + canonical plate + provenance) → harvest end-to-end → measurements → HLD reconciliation | Schema changes before data accumulates; the scored path finally runs for real; integrity debt closed |
| **Weeks 2–4 (parallel slices)** | Phase 3 security/audit/retention; A1–A4 safe-blind accuracy fixes | Additive middleware = good context-switch filler; consensus + BH fix benefit the harvest re-run |
| **Weeks 3–5** | A5 eval harness → A6/A7/A8 measured model upgrades | Never swap two engines in the same week; promote only on numbers |
| **Weeks 4–8** | Phase 6 evidence + analytics + UI (route playback, clips, convoy, DVR, offline map); C1/C2 capacity if measurements show need | Demo-facing multipliers on a now-trustworthy substrate |
| **Month 2+** | Phase 7 productisation, soak/fault harness, backup/DR, runbook, TCO | Makes it operable by someone other than Adi |

**Keep main demoable at every point.** Never demo anything built in the final 48 hours before any evaluation.

---

## Appendix — verified technical recipes

**NVDEC ffmpeg invocation (measured working end-to-end on this machine; byte-identical pipe contract, reader thread unchanged):**
```
ffmpeg -nostdin -hide_banner -loglevel warning -rtsp_transport tcp \
  -hwaccel cuda -hwaccel_output_format cuda -i <url> \
  -map 0:v:0 -an -vf "fps=3,hwdownload,format=nv12" -pix_fmt bgr24 -f rawvideo pipe:1 \
  -map 0:v:0 -an -c:v copy -f hls -hls_time 2 -hls_list_size 10 \
  -hls_flags delete_segments+omit_endlist+independent_segments \
  -hls_segment_filename .../seg%06d.ts .../index.m3u8
```
`fps` **before** `hwdownload` so only 3 fps crosses PCIe (plain `-hwaccel cuda` halves the benefit). Fallback knob: `SENTINEL_HWACCEL=cuda|d3d11va|none` where d3d11va uses `-hwaccel_output_format d3d11` + the same chain (13× realtime measured; plain d3d11va is the slowest path tested — don't use it bare).

**Batched detector:** patch `yolox_s.onnx` — input/output dim0 → `dim_param='batch'`, rewrite the 3 Reshape initializers `[1,85,-1] → [0,85,-1]` (bit-exact, verified); create the DML session with `so.add_free_dimension_override_by_name('batch', 4)` (mandatory — crashes at batch>1 without it); single consumer thread drains a queue of `(tensor, Future)`, collects ≤4 frames or ~40–50 ms, pads short batches, one `session.run` per batch. Measured: 46.6 → 140.6 fps at batch 4, 287 MiB VRAM.

**OCR cascade:** RT-DETRv2 plate ONNX (Apache-2.0) or PaddleOCR DB quads → perspective warp → **upscale the plate sub-region** → `fast-plate-ocr` cct-xs-v2 (MIT, 9.5 ms/crop measured) with aspect-ratio<2.0 → split-and-concat for two-line plates → Paddle fallback when no `plate_like` read or min char_prob < 0.6. Install: `pip install --no-deps fast-plate-ocr open-image-models && pip install rich tqdm` (protects `onnxruntime-directml`). Promotion gate: side-by-side CER vs Paddle on harvested GJ crops (India absent from training regions).

**Road distances:** `src/tools/precompute_distances.py` — one GET to `https://router.project-osrm.org/table/v1/driving/{30×lon,lat}?annotations=duration,distance` (descriptive User-Agent, 60 s timeout, one retry; measured 1.28 s, 0 null cells) → `camera_distances(camera_a, camera_b, road_m, freeflow_duration_s, source, retrieved_at)`; ORS Matrix API (free key, 900≪3500 routes/request) as backup; haversine × measured-median-circuity 1.19 labelled `modelled` only for unknown cameras, never for Saurashtra↔South-Gujarat pairs (measured circuity up to 2.00).

**Offline map:** `pmtiles extract https://build.protomaps.com/<latest>.pmtiles data/gujarat.pmtiles --bbox=68.1,20.0,74.5,24.75 --maxzoom=15` (drop to 14 if >1 GB; record real size as measured) → `app.mount("/tiles", StaticFiles(...))` → `protomapsL.leafletLayer({url:'/tiles/gujarat.pmtiles', flavor:'dark'})` in a `useMap()` wrapper replacing the three `<TileLayer>`s → restore `© OpenStreetMap` attribution on all three maps (mandatory, and currently violated).
