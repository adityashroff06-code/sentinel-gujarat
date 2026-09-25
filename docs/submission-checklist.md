> **Editor's note (fresh build):** copied verbatim from the previous build's `06-submission-checklist.md`. Read `plan/P6-submission.md` as `docs/reference/old-build/P6-submission.md`, `docs/04-feed-rules.md` as `docs/feed-rules.md`, and "before 15 September" as the deadline in `docs/brief.md` §0. Ticked in task S5.5 — first walk-through 25 Sep 2026 (cloud session); each box carries its observation, and each open box its owner.

# 06 — Submission checklist

Tick against an observation, never an intention.

## Four required deliverables

- [x] **Solution presentation** (PPT/PDF) — model + justification, overview, architecture, analytics approach, watchlist correlation methodology, technologies, scalability/interoperability/security, operational benefits — *25 Sep: deck 18 slides, `.pptx` + `.pdf` (18 pp): model + justification s3, overview s2/s4, architecture s5, analytics s8/s11, watchlist correlation s9, technologies s8 + s18, scalability/interoperability/security s12–s15, operational benefits s17. Slide 18's three links are filled at submission (`SENTINEL_DECK_VIDEO1/_VIDEO2/_URL`, then `node build_deck.js` + PDF via PowerPoint)*
- [x] **Technical proposal (HLD)** — all eight required elements, see `plan/P6-submission.md` §6.3 — *25 Sep: all eight §6.3 elements: architecture + diagram §1; heterogeneous cameras/NVR/VMS incl. Model 3 connector ladder §2.3; dispersed ingest §3; edge-cached watchlist §4.1; ANPR/FRS (described)/objects/tracking §5.1–5.4; alert workflow §4.3; scalability/security/performance §6–7; prerequisites, assumptions and information from departments §7 note + §9. **HLD.pdf must be re-rendered on the laptop** after tonight's §7.3/§7.5 edits*
- [ ] **Demo video on own feed** — max 2–3 min: onboarding, AI detection, watchlist correlation, automatic alert — *25 Sep: open — S5.4 recording (Adi), run sheet `docs/demo-script.md` v2.6 video 1*
- [ ] **Live demo on Government feed** — onboarding, viewing, analytics output, **plus timestamped detection report** — *25 Sep: open — S5.4 recording (Adi), video 2; the report half exists (`deliverables/detection-report.html`)*

## The ten dimensions

- [x] Overall Architecture — *25 Sep: HLD §1*
- [x] Integration Strategy — *25 Sep: HLD §2*
- [x] AI & Video Analytics — *25 Sep: HLD §5 (+ §4)*
- [x] Cybersecurity Architecture — *25 Sep: HLD §6*
- [x] Deployment Architecture — *25 Sep: HLD §3*
- [x] Infrastructure Sizing — *25 Sep: HLD §7.3, §8.1*
- [x] Cost-Benefit Analysis — *25 Sep: HLD §8 (`[model]`, F68)*
- [x] Department-wise Information Requirements — *25 Sep: HLD §9*
- [x] Scalability Strategy — *25 Sep: HLD §7*
- [x] Future Roadmap — *25 Sep: HLD §10*

## Model 1 deliverables (mandatory model)

- [x] Working registry portal with GIS map view — *25 Sep: Map screen (deck s6, `deck/img/gis.png`); smoke_frontend 92/92 on the laptop*
- [ ] Bulk + manual onboarding demonstrated — *25 Sep: built (Cameras → Add camera, Bulk import (CSV), `POST /api/cameras`); **demonstrated** only once video 1 beat 2 is recorded (S5.4)*
- [x] Sample onboarded camera-metadata dataset — *25 Sep: `deliverables/sample-camera-dataset.csv`: 58 cameras, disclosure line on seeded values*
- [x] Registry API documentation (`deliverables/registry-api.json`) — *25 Sep: `deliverables/registry-api.json`: OpenAPI 3.1.0, 35 paths, valid JSON*
- [ ] Sample gap-analysis report — *25 Sep: file exists but was captured during the organisers' 25 Sep CDN outage — re-run `.venv/Scripts/python scripts/export_deliverables.py` on the laptop once the sandbox is steady*

## Model 2 deliverables

- [x] Unified viewer connected to feeds from **at least two different systems** — *25 Sep: Live Wall: sandbox RTSP + organisers' CDN + our mediamtx (HLD §2.7; `deck/img/wall.png`, `wall-local.png`; cam01 via CDN proven 25 Sep 20:34 IST)*
- [x] ANPR demonstration on live or recorded feeds — *25 Sep: S4.1 / GATE B: live reads with crops on cam06 (`deck/img/search.png`)*
- [x] Searchable metadata dashboard — *25 Sep: Search screen, exact / OCR-ambiguity / fuzzy (F66, `tests/test_anpr_search.py`)*
- [x] **Architecture note proving departmental systems remain unaffected** — *25 Sep: `deliverables/departmental-systems-unaffected.md` (PDF: render on the laptop, see 'exported to PDF' below)*

## Scalability section (~80,000 cameras)

- [x] Central, regional and edge compute requirements — *25 Sep: HLD §3.1, §7.3, §8.1*
- [x] GPU / accelerator requirements — **with the NVDEC decode ceiling named** — *25 Sep: HLD §7.3: decode table and the NVDEC ceiling named (edit 25 Sep)*
- [x] Expected network bandwidth and low-bandwidth strategies — *25 Sep: HLD §7.2 (240 Gbps vs ~23 Mbps `[model]`), §8.1 72-hour metadata queue for WAN outages, §9 row 8 site bandwidth*
- [x] Hot / warm / cold storage assumptions based on retention periods — *25 Sep: HLD §7.4, §6.2*
- [x] Load balancing, horizontal scaling, monitoring, logging, health checks — *25 Sep: HLD §7.7, §7.6*
- [x] High availability, backup, disaster recovery, cybersecurity controls — *25 Sep: HLD §7.5 (backup bullet added 25 Sep), §6*
- [x] Estimated implementation and operational costs — *25 Sep: HLD §8.2–8.3*
- [x] Phased statewide rollout plan — *25 Sep: HLD §10*

## Feed compliance (official pre-submission list)

- [x] Every client forces RTSP over TCP — *25 Sep: `ml/ingest/rtsp.py:110,132`, `backend/services/health.py`, `backend/tools/probe.py` (`-rtsp_transport tcp`)*
- [x] No timing logic depends on `CAP_PROP_FPS` or arrival time — *25 Sep: no `CAP_PROP_FPS` anywhere; `ml/ingest/rtsp.py:308` stamps pull_start + PTS; `test_100_frames_strictly_monotonic`, `test_pts_sampler_drops_on_pts`*
- [x] Inter-frame gaps don't crash or stall the pipeline — *25 Sep: stall watchdog `rtsp.py:321`; `test_watchdog_kills_a_pull_that_never_delivers_a_frame`*
- [x] Reconnect with backoff implemented **and tested by restarting a feed** — *25 Sep: `test_frames_resume_after_child_killed_mid_read`, `test_rtsp_signals_restart_on_reconnect_and_stays_monotonic`, `test_backoff_bases_double_with_jittered_delays`; live: cam26 drops every ~2 min on 25 Sep and recovers. S6.1 repeats it on the running platform*
- [x] Decoder warnings on join logged, not fatal — *25 Sep: `rtsp.py:160-162` drains stderr at DEBUG, never fatal*
- [x] Camera list and properties read from the catalogue — *25 Sep: `seed_registry` from the organisers' catalogue (S1.3b, S3.7, `tests/test_catalogue.py`)*
- [x] Mixed H.264/H.265 and mixed resolutions handled — *25 Sep: S4.1 live run: cam06 (H.265) with H.264 cameras, 5/5 alive, 0 restarts; wall decodes H.265 in Chrome (F62)*
- [x] Behaviour sane across a scene discontinuity — *25 Sep: `test_scene_cut_detector_fires_on_hard_cut_only`, `test_loop_emits_restart_ticks_and_stays_monotonic`; GATE A′ soak, 10 wrap ticks per camera*

## Before hitting submit

- [ ] Every link opened from a **private window** and confirmed working — *25 Sep: open — S6.3*
- [ ] Videos unlisted (YouTube) or "anyone with the link — Viewer" (Drive/OneDrive) — *25 Sep: open — S5.4*
- [ ] No credentials anywhere: not in the repo, not in history, not in a video frame, not in a screenshot — *25 Sep: repo, full history (`git log -p --all`: only test placeholders), deliverable text (PDF, PPTX, HTML, CSV, JSON) and all 15 tracked images swept clean 25 Sep; **still open: every video frame (S5.4) and S0.5's insurance recording (Adi)***
- [ ] Every document exported to PDF and opening cleanly — *25 Sep: HLD, deck and diagram PDFs open (19/18/1 pp); open — re-render `HLD.pdf` after the 25 Sep edits and render `departmental-systems-unaffected.pdf` on the laptop (`scripts/render_hld.py`, see progress.md)*
- [x] Numbers labelled: measured vs modelled — *25 Sep: HLD: 6 `[measured]` (exactly the S4.1 rows, §7.1), 51 `[model]`, 9 `[estimate]`; deck s12–s13 `[model]`*
- [x] The 30-vs-50 camera discrepancy noted rather than quietly assumed — *25 Sep: HLD Appendix A*
- [ ] Submitted **before** 28 September, not on it — *25 Sep: open — S6.3*

## Hosted demo and credentials (added 22 Sep — decisions F41, F42)

- [ ] The hosted URL opens over HTTPS from **another network** (mobile data) in a private window — *25 Sep: open — S3.5 (Adi)*
- [ ] The evaluator credentials sign in, and the account can do what it is meant to and nothing more — *25 Sep: open — S3.5*
- [ ] The alert stream, a crop image and a live tile all work through the tunnel — *25 Sep: open — S3.5*
- [ ] The URL survives a laptop reboot with no manual step — *25 Sep: open — S3.5 / S6.1b*
- [ ] The credentials are in the submission form only — never in the repo, a screenshot or a video frame — *25 Sep: open — S3.5 creates them; none in the repo as of 25 Sep*
- [ ] `/docs` and every `/api/*` path refuse an unauthenticated request; the five security headers are present — *25 Sep: enforced and tested on the platform (S3.0, `tests/test_auth.py`); open — `curl -sI` against the hosted URL (S3.5)*
- [x] The evaluator's first screen says what to click, which plates to try, and which rows are demonstration data — *25 Sep: Command's *Start here* panel: what it is, plates to try, where feeds come from, what is demonstration data (`deck/img/dashboard.png`)*

## Demonstration content (added 22 Sep)

- [ ] Video 1 shows **onboarding our own camera**, then a **real** watchlist hit and a **real** multi-camera route from our own footage (S3.6); anything injected is visibly labelled — *25 Sep: open — S5.4; per F70 the own camera is a stock clip onboarded on camera and the multi-camera route is the labelled demo vehicle (demo-script v2.6)*
- [ ] Video 2 shows ANPR **plus** vehicle, person and intrusion or line-crossing output on the government feed (FAQ 31), then the exported report — *25 Sep: open — S5.4*
- [x] The detection report carries timestamps and a provenance column — *25 Sep: `deliverables/detection-report.csv` header: `seen_at_utc … clock_source,provenance`*

## Architecture names and the demo (added 24 Sep — decision F54, `docs/architecture.md` Part D)

- [ ] The HLD, the deck and both narrations name the proposal **Model 1 + Model 2 + Pipeline 3 (hybrid)**, and use the brief's names: live view = **Pipeline 1**, live streams = **Model 2**, Model 3 = VMS federation (described only) — *25 Sep: HLD line 7 and §1.3, deck s3/s5 verified 25 Sep; open — the two narrations (S5.4; demo-script v2.6 uses the names)*
- [x] Pipeline 3 is stated as **designed and validated separately, not built**, in HLD §1, its pipeline table and Appendix B — nowhere claimed as running — *25 Sep: HLD §1.5 table, Appendix B; deck s3/s5/s16; diagram*
- [x] Every row of `docs/architecture.md` Part D matches what the HLD says — *25 Sep: S5.1's row-by-row pass, re-walked 25 Sep: four rows still promised filmed own footage and an own-footage route — amended to F70 (stock feeds, labelled demo route), now matching HLD §1.5 rows 115/117, §2.7 and Appendix C*
- [x] The own-footage cameras are disclosed as replayed footage filmed on a named date; cam06 is disclosed as a live pull from the organisers' gateway — *25 Sep: per F70 there is no filmed footage: the local feeds are disclosed as stock footage with seeded coordinates in every registry row, HLD §2.7 and Appendix C, deck s7; cam06 as a live pull from the organisers' gateway (HLD §2.7)*
