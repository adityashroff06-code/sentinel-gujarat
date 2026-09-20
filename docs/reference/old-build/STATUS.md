# STATUS — append-only progress log

Append a block after **every** task. Record what was observed, not what was intended.
Never delete an entry; supersede it with a later one.

```
## <task id> — <status: DONE | BLOCKED | CUT>
When:      <UTC timestamp>
Observed:  <what actually happened — numbers, errors, counts>
Surprise:  <anything that differed from the plan>
Next:      <task id>
```

---

## Key measurements (fill these in — the HLD depends on them)

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

Anything not in this table and presented as a number in the HLD must be labelled an estimate.

---

## Gate decisions

| Gate | Decision | When | Rationale |
|---|---|---|---|
| A — transport | **HLS-only, with session-cookie auth.** All 14 live cameras carry `transport='hls'`; 16 unreachable carry `'none'`. Catalogue carries no department/coordinates → seed path taken: `data/camera_seed.csv` committed, DISCLOSED in submission. | 2026-09-13 ~14:30Z | RTSP (raw TCP :8554) unreachable from the cloud dev workspace; HLS is the guide's guaranteed-anywhere path. RTSP retest from the laptop queued for P2 — design does not depend on it. |
| B — ANPR viability | | | |
| C — route works | | | |
| D — documentation start | | | |

---

## Log

## P0.1 — DONE
When:      2026-09-13T13:40Z
Observed:  Skeleton created per contract §8 (flat-root variant: repo has no
           docs/ or plan/ subdirs, so src/ etc. sit beside the doc files).
           requirements.txt, src/config.py (env config + masked()),
           src/db.py (WAL + foreign_keys=ON, contract schema verbatim),
           package __init__ files, ui/ placeholder.
           Acceptance run: `python -c "from src.db import init; init()"`
           created data/sentinel.db; schema inspected — cameras(28 cols),
           sightings(13), watchlist(8), alerts(14), events(9) + 7 indexes,
           matching docs/03-data-contracts.md field for field.
Surprise:  (1) P0-bootstrap.md says "all six tables"; the binding contract
           defines five. Built the five; not inventing a sixth.
           (2) Dev environment: Claude's shell on the laptop is unavailable,
           so code is authored and CPU acceptance checks run in Claude's
           cloud workspace (Python 3.11.15, ffmpeg present), then committed
           into this repo. GPU work and the demo still run on the laptop.
           (3) The sandbox IS reachable from the cloud workspace.
Next:      P0.2

## P0.2 — DONE (with findings that reshape ingestion details)
When:      2026-09-13T14:20Z
Observed:  Probe run from cloud workspace with form login.
           - Auth: CDN rejects non-browser user agents (403). Sign-in is a
             plain form POST to /auth/login (fields: email, password, no
             CSRF); sets a 'sentinel' session cookie required on EVERY
             path: catalogue, playlists, segments, and /enc.key.
           - Catalogue: 30 cameras, list shape, fields = id + name ONLY.
             Names are real Gujarat locations (Ahmedabad, Junagadh, Rajkot,
             Navsari, Patan, Gandhidham...). Raw saved to
             data/cameras_raw.json.
           - Live: 14/30 over HLS. RTSP 0/30 from cloud (raw-TCP egress
             blocked in that environment — not evidence about the sandbox).
           - All live cameras h264. Resolutions mixed (see table).
           - HLS SHAPE SURPRISE: playlists are EXT-X-PLAYLIST-TYPE:VOD with
             ~7190 × 6 s segments ≈ the full ~12 h recording, AES-128
             encrypted (URI /enc.key, IV 0x0). "Live" pacing exists on
             RTSP/WHEP only; over HLS we choose the playback position.
             Consequence for design: our ingest defines a common
             wall-clock→segment-index mapping so all cameras advance on one
             shared timeline (the organisers state feeds are synchronised);
             hls.js in the browser cannot carry the session cookie
             cross-origin, so Pipeline 1 live view will RELAY HLS through
             our backend — which the one-pull-per-camera invariant wanted
             anyway.
           - Decrypt validated: segment → openssl aes-128-cbc (key from
             /enc.key, IV 0) → ffprobe counts frames. cam07: 150 frames /
             6 s = 25.0 fps measured, ~362 kbps encoded.
           - CDN throws INTERMITTENT 403s under load and appears to
             rate-limit (login itself 403'd after the probing burst);
             cooldown pending. All fetchers now retry with backoff.
Surprise:  VOD-not-live HLS, AES-128 encryption, cookie-gated key, and the
           rate limiter. None of it changes the architecture; it changes
           frame_source.py's HLS mode (segment-indexed reading + decrypt).
Next:      P0.3

## P0.3 — DONE (GATE A: seed path)
When:      2026-09-13T14:40Z
Observed:  Catalogue carries NO department, NO coordinates (only id+name).
           Created data/camera_seed.csv: departments assigned across the
           five named departments honoring name hints ("GRAM PANCHAYAT" →
           Panchayat, "Rajkot Bus Port" → GSRTC, "RLVD" → Police);
           coordinates approximate the real named Gujarat locations.
           ASSIGNMENT IS DISCLOSED in the submission as demonstration data.
           Applied via src/tools/seed_registry.py — 30/30 cameras carry
           department + coordinates; acceptance PASS.
Surprise:  Names are real, geographically meaningful locations spanning
           ~6 districts — better for the GIS story than expected.
Next:      P0.4

## P0.4 — DONE (transport decision)
When:      2026-09-13T14:45Z
Observed:  transport='hls' on all 14 live cameras, 'none' on 16 offline;
           GATE A row recorded above. WHEP dropped from the demo, kept in
           the HLD as the production low-latency path.
Surprise:  none.
Next:      P0.5

## P0.5 — DONE (tiering)
When:      2026-09-13T14:50Z
Observed:  8 cameras set active (= SENTINEL_ACTIVE_CAMERAS): cam07, cam08,
           cam10, cam11, cam24, cam25, cam26, cam28 — chosen live-only,
           cheap resolutions favoured, spanning ALL FIVE departments
           (Municipal, Police, GSRTC, Panchayat, Health). Junagadh cluster
           (08/10/11) and Navsari cluster (25/26/28) give physically
           plausible multi-camera routes. Acceptance PASS via
           seed_registry.py.
Surprise:  cam30 (1080p, isolated Gandhidham) dropped from active on second
           pass — 9 were initially marked.
Next:      P1.1 (per-camera fps/bitrate re-measure queued behind the CDN
           rate-limit cooldown; src/tools/measure.py is ready)

## P1 — DONE (backend fully validated; UI builds, browser-render pending on your laptop)
When:      2026-09-13T14:35Z
Observed:  P1.1 FastAPI service: /api/health, /api/stats, /api/cameras with
           filters (department, health, tier, q) — all pass via TestClient.
           30 cameras, 14 online, 8 active, 5 departments.
           P1.2 Onboarding: POST /api/cameras (manual), POST /import (CSV,
           per-row accept/reject, no partial commit — verified the bad row
           csv02 is absent while csv01/csv03 committed), PATCH — all pass.
           Validation rejects bad department (422), out-of-range lat (422),
           duplicate id (409).
           P1.3 OpenAPI export: deliverables/registry-api.json, 12/12
           operations documented. NAMED DELIVERABLE CLOSED.
           P1.4 GIS map (React+Leaflet, CARTO dark tiles): pins coloured by
           department, opacity by health, dept+online filters, click->full
           record side panel. Builds clean.
           P1.5 Live wall: hls.js tiles, 1/4/9 grid, paging mounts/unmounts
           (Tile.jsx destroys the hls.js instance on unmount — no leaked
           pull). Plays through the backend HLS RELAY.
           *** HLS RELAY validated end-to-end against the live CDN ***:
           GET /api/hls/cam08/live.m3u8 -> rewritten sliding-window playlist
           (proxied key URI + /seg/ paths); GET .../key -> 16 B; GET
           .../seg/segNNNNN.ts -> 530 KB video/mp2t; AES-128 decrypt with
           the relayed key -> 150 h264 frames 854x480. hls.js performs this
           decrypt itself in-browser. Pipeline 1 stores nothing — pure relay.
           P1.6 Health checker (src/ingest/health.py): playlist-head probe
           -> online/degraded/offline; one-shot + loop. Logic done; not
           run in a tight loop here to spare the CDN rate limiter.
           P1.7 Gap-analysis: GET /api/cameras/gap-analysis + printable
           HTML at deliverables/gap-analysis-report.html — names 16
           offline/degraded and 4 isolated cameras (cam07 nearest neighbour
           64.8 km, cam21 50 km). NAMED DELIVERABLE CLOSED. Discloses the
           dept/coords seeding in the report body.
           P1.8 Dashboard shell: nav (Map/Live Wall/Search/Route/Alerts/
           Reports), header counts from /api/stats (polled, not hard-coded).
           UI `npm run build` succeeds (85 modules).
Surprise:  CDN rate-limits the shared cloud-workspace IP hard under a
           probing burst (login itself 403s for a few minutes). Every
           fetcher now retries with backoff + one re-login; the shared
           SentinelSession centralises auth. This will not bite a single
           user on the laptop. NOT a code bug.
Blocked:   Visual browser render of map + wall not confirmable from the
           cloud workspace (no display). Data path fully proven; Adi to run
           `npm run dev` + uvicorn on the laptop and record the P1 screen
           capture the plan asks for before P2 touches ML.
Next:      P2.1 (frame_source.py) — HLS mode with segment-indexed reading +
           AES decrypt, per the P0.2 finding.

## P2.1–P2.5 — DONE (mechanically); P2.4 hit GATE B territory — see below
When:      2026-09-14T06:40Z
Observed:  All ANPR components built and validated in isolation:
           - src/anpr/plates.py (normalise + plate_match, contract §6):
             all rule cases pass incl. ambiguity map (B<->8, O<->0) and the
             ">=8 chars both" guard on Levenshtein. Partial reads never
             fuzzy-match.
           - frame_source.py (P2.1): HLS/VOD mode. Read 100 frames from
             cam08 with MONOTONIC wall_clock_utc; timing from segment index
             + in-segment PTS, never arrival. Emits stream_restart on loop
             wrap and on resync. Jittered backoff on the CDN's 403s
             (observed live, recovered). AES-128 decrypt via cryptography.
             ACCEPTANCE 1 (100 monotonic frames) PASS. 2/3/4 implicitly
             exercised; the dedicated PTS-span run deferred (rate limit).
           - motion.py (P2.2): MOG2 gate, resets on restart. Skip rate
             measured live: cam07 83%, cam24 47%, cam25 17%, busy junctions
             (cam08/10/11) 0% (constant traffic — correct behaviour).
           - detect.py (P2.3): YOLOX-S ONNX (Apache-2.0, NOT Ultralytics).
             CPU 116–300 ms/frame. Real detections on cam08: person 80,
             car 61, truck 24, motorcycle 19, bus 1 over 20 frames.
             Annotated JPEG confirms correct boxes. GPU path (CUDA/DML)
             coded, runs CPU here (no GPU in cloud workspace) — laptop GTX
             1650 will use it.
           - ocr.py (P2.4): PaddleOCR (Apache-2.0), OCR on vehicle crop
             only, never full frame. Reads synthetic 'GJ01AB1234' at 0.96.
             FIX: enable_mkldnn=False required — bundled oneDNN raises
             ConvertPirAttribute2RuntimeAttribute on CPU (paddle 3.3.1).
           - sightings.py (P2.5): 60 s per-plate-per-camera dedupe, saves
             ~2 KB crop, keeps plate_raw. Writes before any alerting.
Surprise / GATE B FINDING:
           End-to-end ANPR on 6 live cameras produced ZERO plate reads.
           Root cause is NOT a bug — it is the footage:
           * The live edge is NIGHT for every camera right now (burned-in
             timestamps all read 13-06-2026 ~21:00–21:46). These are wide
             PTZ traffic-OVERVIEW cameras, not ANPR lane cameras.
           * Vehicle bounding boxes at the live edge are tiny: motorcycles
             16–42 px tall; the biggest car (cam01) ~29% of frame height.
             A plate at that distance is a handful of pixels wide —
             unreadable, day or night.
           * OCR on the small crops returns stray glyphs ('X', 'TAI'),
             correctly rejected by the plate-shape filter.
           The recordings are ~12 h loops on a shared timeline, so they
           SHOULD contain daytime, where reads would be far better. Could
           not confirm: the CDN escalated its rate-limit on the cloud
           workspace IP to a multi-minute 403 ban after repeated probing,
           blocking the daytime-sampling test. Adi's laptop (single user,
           different IP) is not rate-limited and can run it.
Decision needed (GATE B): strategy for readable plates — see chat. Options:
           (a) harvest daytime segments across the recordings (legit: real
               footage, sampled off the live edge) to build sightings +
               route; (b) reduce to the few closest-camera / best angles
               and accept low recall; (c) confirm eval-day govt feed has
               proper ANPR cameras. NOT tuning the model per the gate rule.
Next:      P2.6/P2.7 (worker + measurements) blocked on GATE B; resolve
           readability first.

## P2 update — pipeline strengthened for small plates; harvest tool for the laptop
When:      2026-09-14T07:15Z
Observed:  Confirmed via careful sampling (gentle, to survive the CDN rate
           limit): recording spans ~21:00 -> ~09:00 next day. NIGHT at the
           live edge (all cams ~21:xx now); DAYLIGHT at the recording's END
           (positions 0.80-0.97, brightness 134-143 vs ~90 at night).
           Even in daylight, general OCR read ZERO plates off these wide
           overview cameras: vehicles are 70-420 px tall but the PLATE
           within is ~10-25 px wide — below reliable OCR.
           FIX (real ANPR practice, not model-tuning): ocr.py now
           super-resolves the crop — cubic upscale to ~400 px wide (cap 4x)
           + CLAHE contrast — before OCR. Validated: a 22 px plate in a
           90 px vehicle crop now reads GJ05JB432 @0.99 (dropped 1 trailing
           digit -> realistic partial). Small-plate recall materially up.
Decision:  GATE B strategy = "best 3-4 cameras, accept low recall" (Adi).
           The best cameras are chosen from real per-camera read counts,
           produced by the harvest tool below.
Built:     src/tools/harvest.py — sweeps each camera across its ~12 h
           recording, runs the full pipeline, writes deduped sightings on a
           SHARED synthetic timeline (RECORDING_EPOCH + segment offset), so
           a plate on cam08 then cam10 is a real cross-camera route. Prints
           per-camera new-plate counts + "plates seen on >=2 cameras
           (routeable)" — the number the route demo needs.
Constraint:CDN hard-rate-limits the cloud dev IP (multi-minute 403 bans
           after any burst), so a full multi-camera sweep is impractical
           here. It must run on the LAPTOP: not rate-limited (single user)
           and GPU-accelerated (GTX 1650 -> detector uses CUDA/DML path,
           ~10x faster than cloud CPU). All components individually
           validated against real footage; the sweep is unrun end-to-end
           only for that reason.
Next:      Adi runs the harvest on the laptop (see chat). Its per-camera
           counts pick the best 3-4 cameras and populate sightings, which
           unblocks P2.8 search, P3 watchlist/alerts and P4 route.

## P3 + P4 — DONE (built and validated end-to-end against synthetic sightings)
When:      2026-09-14T08:05Z
Why synthetic: real sightings await the laptop harvest (CDN rate-limits the
           cloud IP). Route/matcher/alerts/report/UI are pure logic over
           the sightings table, so they were validated with a controlled
           synthetic scenario (src/tools/synth_sightings.py) — a hero
           vehicle GJ01AB1234 crossing 5 active cameras + 1 fuzzy near-miss
           (GJ01A81234) + 40 noise plates. All synthetic rows purged after;
           repo DB is clean.
P4.1 route: GET /api/plates/{plate}/route returns the contract §7 shape —
           every required top-level and stop field present (asserted).
           Dwell-collapse works (10 raw hero sightings -> 5 stops).
           departments_crossed populated; implausible implied speeds flag
           suspect=True; coverage gaps computed.
P4.2 fuzzy: ambiguity-map / Levenshtein matches surface as match_type
           'fuzzy' (distinct from literal 'exact'); the near-miss
           GJ01A81234 appears as one fuzzy stop, not merged. Fixed a
           labeling bug (ambiguity matches were mislabeled exact).
P4.4 report: src/tools/report.py detection_report -> deliverables/
           detection-report.{csv,html}; timestamped vehicles+plates,
           filterable. Verified 54-row export.
P3.1 watchlist: seed_watchlist.py — 25 invented entries across all
           categories/severities + optional --from-sightings N to add real
           observed plates. (Run with --from-sightings after the harvest.)
P3.2 matcher: local cached matching (WatchlistCache), exact->ambiguity->
           Levenshtein. Validated: fires exactly once; 5-min per-plate-
           per-camera cooldown suppresses repeats; partial reads (<8) never
           alert. Sighting persisted before match (invariant held).
P3.3 alerts: in-process pub/sub + SSE at /api/alerts/stream; persist-
           before-broadcast. Confirmed an alert payload arrives on a
           subscribed queue after record+match.
P2.6 worker: src/ingest/worker.py — one thread per active camera + a
           supervisor that restarts dead workers, shares the detector+OCR
           across workers, never runs two on one camera, closes captures on
           stop. (Runs on the laptop for the live demo / P2.7 10-min
           measurement.)
UI: Search (plate/camera/time/conf + crops), Alerts (live SSE panel,
           severity-coded, ack, crops), RouteView (numbered pins, polyline
           dashed across gaps, timeline with crops, departments-crossed
           header) — all built; `npm run build` clean (86 modules).
API: full contract §7 surface live — 21 endpoints, all OpenAPI-documented;
           deliverables/registry-api.json refreshed. /crops mounted static.
Remaining before a full demo: run the harvest on the laptop to populate
           real sightings (unblocks GATE B camera choice + real route),
           then P2.7 (10-min measurement), then P5/P6.
Next:      Hand harvest + run instructions to Adi (chat); then P6 docs
           (GATE D: start morning of 15 Sep regardless).

## P6.3 — DONE: Technical Proposal (HLD) written + rendered to PDF
When:      2026-09-14T08:20Z
Observed:  deliverables/HLD.md + HLD.pdf (108 KB, renders cleanly — ASCII
           architecture diagram intact, all tables formatted). Covers all
           EIGHT required HLD elements and ALL TEN dimensions:
           1 Overall architecture · 2 Integration (incl. Model 3 connector
           ladder + department-side collector) · 3 AI analytics (ANPR,
           object, intrusion, tracking, FRS described w/ privacy controls)
           · 4 Cybersecurity (RBAC, segmentation, encryption, credential
           vaulting, audit) · 5 Deployment (edge/regional/central) · 6
           Infra sizing (GPU table + NVDEC decode ceiling named) · 7
           Cost-benefit (per-camera licensing ₹4cr/yr, cloud-egress trap,
           on-prem recommendation) · 8 Department questionnaire (10 items)
           · 9 Scalability (240 Gbps->2.1 Mbps = 3,750x edge reduction;
           crops-not-frames 15x; reconnect storms; split-brain; alert-path
           SPOF; day-2 health/drift) · 10 Future roadmap (sandbox->pilot->
           multi-district->statewide). Grounded in reference/architecture-
           review-80k; every capacity number labelled [model], the two
           anchor numbers marked [measured] (to be filled from the laptop
           run). Appendix notes the 30-vs-50 discrepancy and "what we don't
           do and why".
Next:      P6.5 deck + P6.1/6.2 videos need the laptop demo outputs
           (screenshots, measured fps/detection-rate, hero vehicle plate).
           P5 bonus: object-detection events are code-ready (events table +
           /api/events); intrusion zone editor is the remaining P5 build.

## SESSION SUMMARY (2026-09-14)
Built & validated this session: P0 (probe/registry/GATE A), P1 (API+GIS+
wall+gap report+OpenAPI), P2 (full ANPR pipeline — frame_source HLS/AES,
motion, YOLOX, PaddleOCR+super-res, sightings), P3 (watchlist+matcher+SSE
alerts), P4 (route+report), P6.3 (HLD). 21 API endpoints, all documented.
Two named Model-1 deliverables + the detection report + the HLD are on
disk. GATE B decision = best 3-4 cameras + low recall + a confirmed real
hero vehicle (Adi). The ONE blocker to a full live demo is the laptop
harvest (CDN rate-limits the cloud IP; laptop has GPU + no limit). Guide:
RUN.md.

## REPO SYNC — full push of the cloud workspace into the local repo
When:      2026-09-14T09:00Z
Observed:  65 files synced into C:\Users\Sai\Downloads\Sentinel_Repo:
           root docs (README rewritten to match the flat layout + RUN.md/
           PRD.md pointers), .gitignore, requirements.txt, data/camera_seed
           .csv + raw catalogue + probe results, deliverables/ (registry-
           api.json, gap-analysis-report.html, HLD.md, HLD.pdf), src/**
           (33 modules), ui/** (13 files, no node_modules/dist).
           NOT synced by design: .env (credentials), data/sentinel.db
           (rebuild via probe+seed_registry), data/crops, models/ (fetch
           with src.tools.fetch_models), ui/node_modules (npm install).
           Removed deliverables/detection-report.* — they had been generated
           from the synthetic test scenario; the laptop run regenerates
           them from real sightings (python -m src.tools.report detections).
Surprise:  Laptop was unreachable at first attempt (link dropped); bundle
           prepared and pushed on reconnect.
Next:      Adi: git add/commit locally (no shell from here), then run RUN.md
           §1-§3 (probe, seed, measure, harvest) and report per-camera plate
           counts + a hero plate. Then P2.7, P5, P6.5 deck, P6.1/6.2 videos.

## GAP-CLOSURE PASS — bugs fixed, P5 built, Command dashboard built (2026-09-14)
When:      2026-09-14T10:30Z
Fixed:     (1) TIMELINE BUG — harvest, live worker and HLS relay were on
           three different clocks. New src/ingest/timeline.py is the one
           mapping (recording offset <-> timestamp, anchored to the
           footage's own ~21:00 IST start; live edge = (now + offset) %
           length). frame_source, harvest and the relay all use it, so
           harvested + live sightings align on the route and the wall shows
           what the detector reads. SENTINEL_PLAYBACK_OFFSET_S lets the demo
           play the daylight window (documented in RUN.md / .env.example).
           (2) Health checker now starts with the API (background thread,
           SENTINEL_HEALTH_INTERVAL_S; 0 = off). (3) stats: 'sightings_today'
           was meaningless on a recording timeline -> sightings_total,
           plates_unique, events_total, zone_events. (4) Relay caches the
           static upstream playlists (10 min) — fewer CDN hits, less
           rate-limit exposure. (5) Leaflet CSS was loaded from unpkg — a
           venue without internet would have had no map; now bundled.
           (6) Percentage-height maps collapsed inside the flex layout ->
           absolute page containers; maps fit their points automatically.
Built:     P5.1 object events — pipeline writes throttled object_detected
           events (per camera per class, ≥5 s apart) with counts;
           GET /api/events/summary aggregates; shown on Command + Reports.
           P5.2 intrusion — src/analytics/zones.py (polygon entry, line
           crossing with direction) driven by a new light IoU+centre tracker
           (src/anpr/track.py; ByteTrack stand-in, stated honestly). Zone
           editor page (/zones) draws on a live still (GET /cameras/{id}/
           snapshot.jpg) and saves normalised coords to cameras.zones_json;
           high-severity zone hits broadcast on the alert SSE.
           VALIDATED (synthetic tracks): one moving object keeps one track
           id; intrusion fires once on entry; line_cross fires once
           downward and ignores upward.
           P2.6/P2.7 — worker now records sustained fps, motion-skip rate,
           detections/min, sightings per camera and writes
           data/worker_stats.json every 10 s; GET /api/workers serves it;
           Command shows it. This is where the P2.7 measurements come from.
           Reports — GET /api/reports/detections?format=csv|html and
           /api/reports/gap-analysis generate on request; Reports page wired.
           API also serves the built UI (ui/dist) as a single process.
           COMMAND DASHBOARD (/dashboard, default route) — the video screen:
           4 live tiles (active tier) · GIS mini-map · live alert feed ·
           latest plate reads · object/intrusion counters · worker status.
           Rendered in headless Chromium here against a synthetic scenario
           and inspected: layout, map pins, alert card, route timeline all
           correct. Tiles show a codec error ONLY in headless Chromium (no
           H.264 decoder in that build); the relay->decrypt->frames path was
           validated separately and your Chrome has H.264.
           26 API operations, all OpenAPI-documented (registry-api.json
           refreshed). Synthetic test data purged from the DB afterwards.
Still open (need the laptop): real plate reads (harvest), P2.7 numbers
           from a 10-min GPU run, P6.5 deck + demo videos. Pipeline 3
           evidence clips remain HLD-described, per the cut order.

## P6.5 — DONE: Solution presentation built (deck/build_deck.js -> .pptx + .pdf)
When:      2026-09-14T11:30Z
Observed:  deliverables/Sentinel-Solution-Presentation.pptx (+ .pdf), 18
           slides, pptxgenjs; OOXML validation PASSED; rendered and
           visually inspected (one caption/card collision found on slide 8
           and fixed). Covers every P6.5 checklist item: proposed model +
           justification (Hybrid 1+2+evidence, Model 3 path, Model 4
           rejected by physics) · overview/objectives/innovations ·
           architecture + end-to-end workflow · AI analytics approach (ANPR,
           objects, intrusion, tracking; FRS described) · watchlist
           correlation + alerting methodology · technologies WITH licensing
           rationale · scalability/interoperability/security/deployment ·
           operational benefits. The three "disproportionate" slides are in:
           edge-vs-centralised (240 Gbps -> 2.1 Mbps, 3,750x; GPU + NVDEC
           tables), storage honesty (3.46 TB vs 0.23 TB/day; clips), and
           "what we do not do, and why". Speaker notes on every slide.
           Images: REAL sandbox frames (cam01 feed, cam08 YOLOX detections)
           and UI captures. Every figure labelled [measured]/[model].
TO DO before submitting (Adi, on the laptop):
           - Slides 4, 6, 9, 10, 11 use dev UI captures taken on the
             synthetic test scenario (captions say so). Replace them with
             live-demo screenshots (Command view with playing tiles, real
             plate reads, a real alert, the hero vehicle's route) — drop the
             PNGs into deliverables/deck/img/ with the same names and run
             `node deliverables/deck/build_deck.js` (pptxgenjs is on npm).
           - Fill the [link] fields on slide 18 (videos, repo, HLD).
           - Export the final PDF (File > Export) and open every link from a
             private window.
Next:      P6.1/P6.2 videos (needs the laptop run), then P6.7 submit.

## LAUNCHERS — one-click demo start (no .exe by design)
When:      2026-09-14T12:10Z
Observed:  START_SENTINEL.bat (checks Python/ffmpeg/.env; creates .venv;
           installs deps once; fetches YOLOX; probes + seeds the registry on
           first run; builds the UI only if ui/dist is missing; starts the
           API and the workers in two titled windows; opens
           http://localhost:8000/dashboard). STOP_SENTINEL.bat kills both.
           HARVEST.bat runs the sweep + watchlist seeding. CRLF endings.
           ui/dist (prebuilt, 960 KB) is now committed (gitignore
           negation) so the platform runs without Node installed.
Why not an .exe: PyInstaller-bundling PaddleOCR + ONNX Runtime + OpenCV +
           ffmpeg is a multi-hour, fragile build with no scoring value; the
           launcher gives the same double-click experience on the demo
           laptop, and the judges' optional hosted-URL path is served by
           the same API. Decision recorded, not deferred.
Next:      Adi runs START_SENTINEL.bat, then HARVEST.bat; record the
           harvest summary + P2.7 numbers here; swap deck screenshots;
           record videos; submit.

## LAUNCHER FIX — windows closed instantly on the laptop ("nothing happens")
When:      2026-09-14T13:00Z
Observed:  Adi reported double-clicking START/HARVEST did nothing visible.
           Cause class: the console closed before an error could be read
           (and/or non-ASCII characters in echo lines). Fix: every launcher
           now relaunches itself inside `cmd /k` so the window ALWAYS
           stays open; all output is ASCII; START logs to launcher.log;
           Python is located via `py -3` first, then `python`; each check
           prints an explicit [X] line naming the missing prerequisite.
           Added CHECK_SETUP.bat to diagnose Python / ffmpeg / .env /
           ui\dist presence in one click.
Next:      Adi re-runs CHECK_SETUP.bat then START_SENTINEL.bat.

## LAUNCHER FIX 2 — root cause found: ffmpeg not installed on the laptop
When:      2026-09-14T13:40Z
Observed:  `python launch.py check` on the laptop: Python 3.13.9 (Anaconda,
           D:\Anaconda\python.exe), ffmpeg NOT FOUND, .env present, ui/dist
           present, .venv/model/db not yet created. So the .bat files were
           stopping at the ffmpeg check (and the window closed too fast to
           read it) — nothing was wrong with the platform itself.
Fix:       launch.py now removes the prerequisite instead of asking for it:
           when ffmpeg/ffprobe are absent it downloads the BtbN portable
           win64 build (~190 MB, one time) into tools/ffmpeg/ and prepends
           its bin/ to PATH for every child process (uvicorn, workers,
           probe, harvest). Verified in the cloud: zip fetch + extract
           yields tools/ffmpeg/<build>/bin/{ffmpeg,ffprobe}.exe. tools/ is
           gitignored. The four .bat files are now one-line wrappers
           around `python launch.py <mode>` (single code path).
Python:    3.13 is fine — checked PyPI: paddlepaddle 3.3.1, onnxruntime
           1.30, opencv-python 5.0 all ship cp313 win_amd64 wheels;
           paddleocr is pure-python. Pinned paddlepaddle==3.3.1 and
           paddleocr==3.7.0 (the versions validated in the cloud) so the
           laptop install matches. No need for a separate 3.11 env.
Next:      Adi runs `python launch.py` (first run ~5-10 min: ffmpeg + pip +
           YOLOX + probe), then `python launch.py harvest`.

## LAUNCHER FIX 3 — ffmpeg download dropped at 181/195 MB (WinError 10054)
When:      2026-09-14T14:25Z
Observed:  First laptop run: portable-ffmpeg fetch reached 181.4/195 MB
           then ConnectionResetError; launcher deleted the partial and
           stopped. Everything before it (Python 3.13, .env, ui/dist)
           checked out.
Fix:       launch.py download is now resumable: writes to <name>.zip.part,
           keeps the partial across attempts AND runs, retries up to 8x
           per URL with an HTTP Range header (falls back to a full restart
           if the server answers 200 instead of 206), verifies the length,
           and only then renames + extracts. Second URL (gyan.dev
           release-essentials, ~90 MB) as fallback. Cloud test: seeded a
           50 MB partial, resumed to 194,539,427 bytes, zip testzip() OK.
Next:      Adi re-runs `python launch.py`; it picks up from the bytes
           already on disk.

## LAUNCHER RUN 1 ON THE LAPTOP — platform up, zero workers; ROOT CAUSE + FIX
When:      2026-09-14T14:30Z
Observed:  (read from the repo folder) tools/ffmpeg present, .venv + deps
           installed, yolox_s.onnx fetched, probe ran, sentinel.db built,
           API + workers spawned (launcher_pids.txt), worker_stats.json
           updating — but `"workers": {}`. probe_results.json from the
           laptop: RTSP OK on 27/30 cameras (h264, 1920x1080 / 1280x720 /
           2560, 25-30 fps declared; cam08/cam11/cam30 timeout); HLS via
           the CDN FAILED on all 30 (22 timeouts, 6 "invalid data" =
           limiter). The exact inverse of the cloud (HLS ok, RTSP blocked).
           Registry therefore has transport=rtsp for 27 cameras, and the
           worker only selected transport='hls' -> nothing to run. Also
           two of the seeded active cameras (cam08, cam11) are offline
           from the laptop.
Fix (code):
  - src/ingest/frame_source.py: new RtspFrameSource — one ffmpeg process
    per camera (-rtsp_transport tcp), CFR-sampled BGR frames on stdout
    (pts = index/target_fps from the fps filter, wall clock = pull start
    + pts), reader thread keeps only the latest frame so a slow pipeline
    never back-pressures the pull; the same process TEES a stream-copied
    local HLS window (data/hls/<cam>/, 10 x 2 s) for the Live Wall — so
    the wall shows the exact pull the detector reads and there is still
    one pull per camera. Backoff/restart/stream_restart/kill-in-finally
    as per 04-feed-rules. for_camera() dispatches on transport.
  - src/ingest/worker.py: selects transport IN ('rtsp','hls').
  - src/tools/probe.py: RTSP preferred over HLS when both work (RTSP is
    the primary transport per 02-hard-constraints).
  - src/api/routes_hls.py: /api/hls/{cam}/live.m3u8 serves the worker's
    local window when fresh (<20 s), else the CDN relay; new
    /api/hls/{cam}/local/{seg}.
  - data/camera_seed.csv: active tier cam08->cam09 (Police), cam11->cam06
    (GSRTC); still 8 active across 5 departments.
  - launch.py: re-applies the seed on every start; stops the previous
    instance first; refuses to start if :8000 is busy; [2b/4] installs
    onnxruntime-directml on Windows (verified via provider list, falls
    back to CPU); new `status` mode; harvest explains the CDN sweep is
    optional now that live workers harvest.
Verified (cloud, against a local mediamtx RTSP server replaying real
           sandbox footage on stream/cam07 + cam10, laptop's own DB):
           supervisor starts 6 workers; cam07/cam10 pull, HLS tee rolls
           (seg000043 after ~85 s), detector fires (134/151 vehicle
           detections in ~25 frames), 107 object events written; API
           serves the local playlist + valid h264 segments; cameras
           without a worker fall back to the relay. Sightings 0 on the
           480p CDN copy (known); the laptop's RTSP is native 1080p.
Next:      Adi: `python launch.py` (re-seeds, restarts) -> dashboard;
           after 10 min `python launch.py status` and paste it.

## GAP-CLOSURE PASS 2 — "final demo isn't working" root causes found and fixed (laptop session)
When:      2026-09-14T17:50Z
Observed (live state before fixes):
           - API DEAD: src.api.main import raised RuntimeError — python-multipart
             missing (CSV-import Form endpoint needs it). uvicorn died instantly
             in a console that closed; launcher still said "running".
           - Workers alive but ~0 fps; sightings never accumulated.
           - The ONLY sightings ever written were the burned-in caption
             ("oad Fix-2(Fr" -> OADFIX2FR @0.99) read as a plate.
           - watchlist EMPTY (seeding only ran inside the harvest flow).
           - 29/30 cameras flipped health='offline' by a health pass that
             probed the CDN (flaky from this laptop) even for RTSP cameras
             -> next start would have had ZERO workers again.
Root causes + fixes (all verified by running code):
           1) requirements.txt lacked python-multipart -> added; installed.
              launch.py deps stamp now hashes requirements.txt so future
              edits actually reinstall (.deps_ok previously froze forever).
           2) fps collapse was NOT the RTSP pipe: PaddleOCR default
              "medium" models cost ~6 s PER VEHICLE CROP on this CPU, and
              the one shared PlateReader was called unlocked from 6-8
              threads (not thread-safe; init race). Fixed: switched to
              PP-OCRv5_mobile det/rec (measured 0.45 s/crop, 13x), added a
              lock around init+predict, and a per-track OCR budget in the
              pipeline (skip tracks with a complete read; >=1.5 s between
              OCR per track; max 2 crops per frame, largest first).
              Detector confirmed fast on DirectML (46-55 ms/frame).
           3) Caption-as-plate: dets whose box starts in the top 5% of the
              frame are skipped, and plate acceptance now requires Indian
              plate STRUCTURE (plates.plate_like: full = SS DD LLL NNNN
              with ambiguity-map coercion, partial = structural prefix, NO
              coercion). OADFIX2FR/DFIX2F etc. all rejected; GJ01A81234
              (B->8 misread) still accepted. Garbage rows purged from DB.
           4) plate_bbox scale bug: OCR boxes were in 4x-upscaled crop
              coords; now mapped back to source pixels (contract §2).
           5) Watchlist: seeded at every launch (idempotent, 25 entries,
              BEFORE workers start); worker matcher cache now refreshes
              every supervisor poll (10 s) so plates added mid-demo alert;
              seed_watchlist --from-sightings now structure-gates plates.
           6) SSE alerts crossed processes only in theory: the bus is
              in-process but alerts fire in the worker PROCESS. The API's
              /api/alerts/stream now tails the alerts TABLE (2 s poll) —
              alerts reach the dashboard regardless of which process fired.
           7) Health checker no longer touches RTSP cameras via the CDN:
              active RTSP cams are judged by their local tee freshness;
              others keep probe-derived health. Reset the 29 wrongly-
              offline cameras back to online.
           8) crop thumbnails 404'd: crop_path stored with backslashes,
              URL built by splitting on 'crops/' -> normalised (3 sites).
           9) launch.py: children spawned via `cmd /k` (window STAYS OPEN
              on crash — raw string, not list, to survive cmd quoting);
              launcher now polls :8000 for 30 s and fails loudly if the
              API never binds; pip re-run no longer silently clobbers
              onnxruntime-directml (force-reinstall + re-check).
          10) Active tier re-picked from laptop evidence (cam07/cam25
              pulled ZERO frames over RTSP; suspected ~6-session cap):
              now 6 cameras = Junagadh cluster (cam06 GSRTC, cam09 Police,
              cam10 Municipal) + Bilimora cluster (cam26 Panchayat, cam27
              Municipal, cam28 Health). 5 departments, two tight
              geographic clusters -> best odds of cross-camera routes.
              SENTINEL_ACTIVE_CAMERAS=6 in .env/.env.example.
Also observed: CDN (cctv.corp8.cloud) IS reachable from the laptop right
           now (earlier all-30 failure was transient rate-limiting), so
           `python launch.py harvest` is a viable route-insurance path.
           Live edge is DAYLIGHT during working hours (burned-in clock
           runs ~3 h behind IST; recording day 17-06-2026 at the edge).
Next:      verify workers ramp (fps, sightings), then harvest for the
           hero plate + route, then deck screenshots + videos (P6).

## ROOT CAUSE of the worker-process deaths: DirectML session not thread-safe
When:      2026-09-14T18:05Z
Observed:  With the OCR fixes in, the worker process still died — exit
           code 139 (native segfault). Captured the precursor in
           data/workers_debug.log: onnxruntime DmlExecutionProvider
           DmlCommandRecorder.cpp 80004005 on concurrent Run() from
           several camera-worker threads sharing the one Detector
           session. This (not code in our modules) is what killed the
           launcher-spawned worker process silently earlier.
Fix:       Detector now serialises session.run() behind a lock
           (pre/post-processing stays parallel; Run() is ~50 ms on the
           GTX 1650, so 6 workers x 3 fps fits). OCR predict() was
           already serialised for the same reason.

## FULL END-TO-END VERIFIED ON THE LAPTOP + demo-plate flow (2026-09-14T18:30Z)
When:      2026-09-14T18:30Z
Decision:  Per Adi — "just use demo plates and make them appear in the full
           application flow." Rationale: a genuine cross-camera route needs
           the CDN's shared-timeline recordings (harvest), but the CDN
           hard-rate-limits this laptop's IP (403 on every fetch after
           login), and live RTSP cameras sit at DIFFERENT loop positions
           (cam06 daytime road, cam09 night, cam28 indoor pedestrian
           corridor) so the same vehicle never appears on two live cameras.
           Cross-camera route from live RTSP is therefore physically
           impossible here; demo plates are the right call.
Built:     src/tools/demo_seed.py — injects a hero vehicle THROUGH THE REAL
           pipeline: every sighting via anpr.sightings.record_sighting
           (dedupe + crop save), every alert via alerting.matcher.
           match_sighting (watchlist match + cooldown + persist). So a demo
           plate behaves exactly like a live read. Rows tagged track_id
           'DEMO-*' -> `python launch.py demo-clear` removes only them.
           Hero GJ01AB1234 (already on the watchlist, stolen/high) crosses
           cam06(GSRTC) -> cam10(Municipal) -> cam09(Police): 3 departments,
           ~7.8 km, plausible 55/61 km/h, + a fuzzy near-miss GJ01A81234
           (B<->8) shown as a distinct fuzzy stop. 28 background reads.
           Wired as `python launch.py demo` / `demo-clear`.
Verified (browser, localhost:8000, all real HTTP):
           - Live Wall: real RTSP video on all 4 tiles (cam06 daytime road,
             cam10 evening road w/ van+auto, cam09/cam26 night) via the
             RTSP->local-tee->relay->hls.js path. Grid 1/4/9 + paging.
           - Command dashboard: 36 sightings, 34 plates, 4 alerts, live
             alert cards w/ crops, latest plate reads w/ crops, mini-map.
           - Route (THE scored view): type GJ01AB1234 -> 4 stops, 7.8 km,
             12 min, departments GSRTC/Municipal/Police, numbered pins +
             polyline + timeline w/ per-stop speeds and crops.
           - Search: auto-loads recent reads on mount (was blank before the
             fix); 36 rows w/ crops + per-row route click-through.
           - Alerts: 4 severity-coded HIGH stolen_vehicle cards w/ crops,
             ack + route buttons.
           - Reports: detection CSV (clean columns) + HTML (200) +
             per-camera object table from REAL live detections.
LIVE ANPR PROVEN: while verifying, the live workers read REAL plates off
           cam06 with real plate crops — e.g. GJ188R5253 (0.92),
           GJ11BHO117 (0.87) — structurally validated via the new
           ambiguity-coercing filter. Live detection + ANPR + demo flow
           coexist in one DB.
Fixes this pass (beyond gap-closure pass 2): DirectML detector session is
           not thread-safe under 6 workers (segfault, exit 139) -> Run()
           serialised behind a lock. SQLite 'database is locked' under 6
           workers + API + stats -> busy_timeout=30s + connection timeout
           30s + supervisor poll wrapped so one lock never kills the
           process. Map tiles CARTO->OpenStreetMap (both need internet;
           venue-offline still shows pins+route, no basemap). Search
           auto-loads on mount. launcher spawns children via `cmd /k`
           (window stays open on crash) and fails loudly if :8000 never
           binds; requirements.txt hash gates the deps reinstall;
           onnxruntime-directml force-reinstalled after the plain wheel
           clobbers it.
Remaining for Adi: (1) venue internet for OSM basemap tiles (else pins
           render without a map). (2) demo screenshots for the deck (swap
           into deliverables/deck/img, rerun build_deck.js). (3) record the
           two demo videos per 05-demo-script.md. (4) if the CDN cools
           down, `python launch.py harvest` can add a real multi-camera
           route on top of the demo one.

## STABILITY FIX — the platform was dying after ~10 min (root cause found)
When:      2026-09-15T00:10Z
Symptom:   API + workers vanished ~10 min after launch; earlier this looked
           random because launch.py spawned children in consoles that
           closed on crash, leaving no log.
Fix 1 (visibility): launch.py now spawns the API and workers as DETACHED
           children with stdout+stderr redirected to data/api.log and
           data/workers.log (not cmd/k windows that swallow the trace).
Root cause (now visible in workers.log): workers crash-looped on
           'database is locked'. Six workers each opened a fresh SQLite
           connection and wrote an object-event PER inferred frame; that
           write churn beat WAL + busy_timeout and, because CameraWorker.run
           wrapped the whole loop in one try/except, a single locked write
           killed the entire camera pull. Enough simultaneous
           crash/restarts + the supervisor's own queries eventually
           cascaded the process down.
Fix 2: db.connect adds PRAGMA synchronous=NORMAL (safe under WAL, far
           fewer fsyncs -> the write lock is held briefly).
Fix 3: object-event writes are best-effort (swallow OperationalError) —
           analytics, not evidence.
Fix 4: the worker loop guards EACH frame, so a transient lock logs
           'frame skipped' and continues instead of ending the pull.
Verified: clean restart -> all 6 workers hold UNIFORM 152 s uptime (no
           restart), 0 'frame skipped', detections flowing (cam06 298),
           API stable. Demo scenario + 10 real live reads coexist.

## P7 — ENHANCEMENT REVIEW & PLAN (post-submission)
When:      2026-09-20T14:30Z
Observed:  Full-codebase multi-agent review completed: 9 subsystem/security/
           correctness reviewers + 4 strategy lenses + 7 adversarial
           feasibility checks (several MEASURED on this laptop) + a
           completeness critique. 15-entry defect register produced; worst:
           (D1) HLS source silent ~12h after recording wrap
           (frame_source.py:237), (D3) RTSP vs HLS sightings on two
           incompatible time bases -> cross-camera route breaks when
           transports mix, (D4) COUNT-based alert IDs collide permanently
           after demo-clear, (D5) zone alerts never reach the dashboard
           (bus has no subscriber in the worker process), (D2) zero auth +
           SSRF/XSS cluster. Feasibility measurements on this machine:
           NVDEC decode works on the GTX 1650/driver 512.78 (~6x decode-CPU
           cut per camera, ~129MB VRAM/session, no session cap); batched
           YOLOX = 3.0x at batch 4 (needs DML free-dimension override or it
           crashes); FP16 under DirectML REFUTED (1.5-1.8x SLOWER);
           fast-plate-ocr = 9.5ms/crop CPU but India absent from its
           training regions (side-by-side gate mandatory); one OSRM /table
           call returned the full 30x30 road-distance matrix in 1.28s
           (median circuity 1.19, Junagadh->Navsari 2.00 — flat 1.3 factor
           refuted); open-image-models YOLOv9 plate weights and ByteTrack's
           kalman_filter.py rejected on GPL provenance.
Surprise:  (1) The sandbox CDN may be decommissioned any day — footage
           archive + local replay stack is the only time-critical work and
           gates everything (new Phase 0). (2) The repo is not a git
           repository and has zero tests; three found bugs are regressions.
Next:      Full phased plan written to P7-enhancements.md (Phase 0: archive
           footage + git init + logging fix; then correctness batch ->
           migration wave -> first real end-to-end harvest -> measured
           accuracy work). Execute Phase 0 first.
