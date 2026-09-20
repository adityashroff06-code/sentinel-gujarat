# Sandbox findings — what the grid and this laptop actually do (measured)

**Editor's note (20 Sep 2026).** Every fact here was observed by code that ran during the previous build (13–15 Sep 2026). Quoted blocks are **verbatim from `docs/reference/old-build/STATUS.md`**, the append-only findings log, with the entry named so it can be checked. Nothing in this file is an assumption; where the previous build could not confirm something, that is stated. Read this before designing ingestion, timing, storage or the demo — every one of these facts cost hours to discover.

---

## 1. Access and authentication

- Catalogue: `GET https://cctv.corp8.cloud/cameras.json` — a flat list of `{"id","name"}`, **30 cameras, no other fields**. `/api/ingest` does not exist on this host (`docs/reference/sandbox-access-spec.md`).
- The CDN requires a **session cookie** on every path (catalogue, playlists, segments, the AES key) and rejects non-browser user agents. From P0.2:

> - Auth: CDN rejects non-browser user agents (403). Sign-in is a
>   plain form POST to /auth/login (fields: email, password, no
>   CSRF); sets a 'sentinel' session cookie required on EVERY
>   path: catalogue, playlists, segments, and /enc.key.

- RTSP needs the credentials **in the URL**, email percent-encoded (`@` → `%40`); no cookie. WHEP likewise. Only approved emails connect.
- **The CDN rate-limits hard.** A probing burst earns a multi-minute 403 ban, including on login. From P0.2 and the P2 update:

> - CDN throws INTERMITTENT 403s under load and appears to
>   rate-limit (login itself 403'd after the probing burst);
>   cooldown pending. All fetchers now retry with backoff.

> Constraint:CDN hard-rate-limits the cloud dev IP (multi-minute 403 bans
>            after any burst), so a full multi-camera sweep is impractical
>            here.

  The laptop was also rate-limited on 14 Sep evening (`harvest_run.log`: every login 403 or timed out), and reachable again later the same night ("CDN (cctv.corp8.cloud) IS reachable from the laptop right now (earlier all-30 failure was transient rate-limiting)"). Treat the CDN as *sometimes* available; never as the only path.

## 2. HLS is not live — it is a 12-hour encrypted recording

From P0.2:

> - HLS SHAPE SURPRISE: playlists are EXT-X-PLAYLIST-TYPE:VOD with
>   ~7190 × 6 s segments ≈ the full ~12 h recording, AES-128
>   encrypted (URI /enc.key, IV 0x0). "Live" pacing exists on
>   RTSP/WHEP only; over HLS we choose the playback position.
>   Consequence for design: our ingest defines a common
>   wall-clock→segment-index mapping so all cameras advance on one
>   shared timeline (the organisers state feeds are synchronised);
>   hls.js in the browser cannot carry the session cookie
>   cross-origin, so Pipeline 1 live view will RELAY HLS through
>   our backend — which the one-pull-per-camera invariant wanted
>   anyway.
> - Decrypt validated: segment → openssl aes-128-cbc (key from
>   /enc.key, IV 0) → ffprobe counts frames. cam07: 150 frames /
>   6 s = 25.0 fps measured, ~362 kbps encoded.

Consequences that held all the way through: the browser cannot play the CDN directly (cookie), so the live wall plays an HLS playlist **relayed by the backend** (rewritten sliding window, proxied key, proxied segments; hls.js decrypts in-browser). The relay caches upstream playlists to spare the rate limiter.

## 3. RTSP: blocked from the cloud, works from the laptop

From the cloud workspace (13 Sep): RTSP 0/30, HLS 14/30. From the laptop (14 Sep) — **the exact inverse**:

> probe_results.json from the
> laptop: RTSP OK on 27/30 cameras (h264, 1920x1080 / 1280x720 /
> 2560, 25-30 fps declared; cam08/cam11/cam30 timeout); HLS via
> the CDN FAILED on all 30 (22 timeouts, 6 "invalid data" =
> limiter). The exact inverse of the cloud (HLS ok, RTSP blocked).

`data/probe_results.json` is that laptop run (checked 14 Sep 12:32–12:34 UTC; credentials masked): 27 RTSP-live cameras at 1920×1080 ×16 · 1280×960 ×4 · 1280×720 ×5 · 960×576 ×1 · 2560×1440 ×1, declared 10–30 fps. RTSP from the laptop is **native resolution, live-paced**; the CDN's HLS copy of the same camera can be much smaller (cam08 relayed at 854×480 over HLS; STATUS: "Sightings 0 on the 480p CDN copy (known); the laptop's RTSP is native 1080p").

**Suspected per-account RTSP session cap.** With 8 active workers, two cameras pulled zero frames:

> 10) Active tier re-picked from laptop evidence (cam07/cam25
>     pulled ZERO frames over RTSP; suspected ~6-session cap):

The final active set was 5–6 cameras. Budget for **≤6 concurrent RTSP pulls** until measured otherwise, and remember the relay/live wall must not add pulls of its own (one pull per camera — the worker tees a local HLS window for the wall).

## 4. The recordings loop on one shared timeline; night at one end, day at the other

From the P2 update:

> Confirmed via careful sampling (gentle, to survive the CDN rate
> limit): recording spans ~21:00 -> ~09:00 next day. NIGHT at the
> live edge (all cams ~21:xx now); DAYLIGHT at the recording's END
> (positions 0.80-0.97, brightness 134-143 vs ~90 at night).

And from gap-closure pass 2 (laptop, 14 Sep evening):

> Live edge is DAYLIGHT during working hours (burned-in clock
> runs ~3 h behind IST; recording day 17-06-2026 at the edge).

The organisers state the feeds are synchronised on a common timeline. The previous build mapped wall-clock ↔ recording position in one module (`src/ingest/timeline.py`) and shifted the "live" window with `SENTINEL_PLAYBACK_OFFSET_S` (≈34000 s puts the HLS live edge in daylight). **Over RTSP the position is whatever the gateway is serving — you cannot choose it.**

**Live RTSP cameras sit at different loop positions from each other.** From the demo-plate decision (14 Sep 18:30Z):

> live RTSP cameras sit at DIFFERENT loop positions
> (cam06 daytime road, cam09 night, cam28 indoor pedestrian
> corridor) so the same vehicle never appears on two live cameras.
> Cross-camera route from live RTSP is therefore physically
> impossible here; demo plates are the right call.

This is the single most important finding for the scored test: **a genuine cross-camera route needs the same vehicle on ≥2 cameras, which the live RTSP feeds did not provide.** The previous build's answer was a demo vehicle injected through the real pipeline (`docs/decisions.md`). A harvest of the CDN recordings across cameras is the only path to a real one, and it needs the CDN to cooperate.

## 5. What the cameras show, and what plates look like

From the GATE B finding (P2.1–P2.5) and the P2 update:

> * The live edge is NIGHT for every camera right now (burned-in
>   timestamps all read 13-06-2026 ~21:00–21:46). These are wide
>   PTZ traffic-OVERVIEW cameras, not ANPR lane cameras.
> * Vehicle bounding boxes at the live edge are tiny: motorcycles
>   16–42 px tall; the biggest car (cam01) ~29% of frame height.
>   A plate at that distance is a handful of pixels wide —
>   unreadable, day or night.

> Even in daylight, general OCR read ZERO plates off these wide
> overview cameras: vehicles are 70-420 px tall but the PLATE
> within is ~10-25 px wide — below reliable OCR.
> FIX (real ANPR practice, not model-tuning): ocr.py now
> super-resolves the crop — cubic upscale to ~400 px wide (cap 4x)
> + CLAHE contrast — before OCR. Validated: a 22 px plate in a
> 90 px vehicle crop now reads GJ05JB432 @0.99 (dropped 1 trailing
> digit -> realistic partial). Small-plate recall materially up.

The footage also carries a **burned-in caption** that OCR reads as a plate unless boxes in the top ~5% of the frame are skipped, and plate acceptance must require Indian plate *structure* (gap-closure pass 2, item 3).

**Live ANPR did work**, on the daytime road camera (cam06, GSRTC, Junagadh):

> LIVE ANPR PROVEN: while verifying, the live workers read REAL plates off
>            cam06 with real plate crops — e.g. GJ188R5253 (0.92),
>            GJ11BHO117 (0.87) — structurally validated via the new
>            ambiguity-coercing filter.

State of the old database on 18 Sep (last run): 46 sightings — **32 demo rows and 14 real reads, all 14 from cam06** (e.g. GJ10DN2875 0.95, GJ03JR8399 0.95, GJ03ER8216 0.98, GJ11VY7338 0.98, GJ03JR5317 1.00, plus partials like GJ18X). No real plate on two cameras. All 4 alerts are the demo vehicle. 553 events (548 object, 4 intrusion, 1 line-cross). 27 watchlist entries, 0 seeded from observation.

## 6. Geography and departments were assigned, and are disclosed

From P0.3:

> Catalogue carries NO department, NO coordinates (only id+name).
> Created data/camera_seed.csv: departments assigned across the
> five named departments honoring name hints ("GRAM PANCHAYAT" →
> Panchayat, "Rajkot Bus Port" → GSRTC, "RLVD" → Police);
> coordinates approximate the real named Gujarat locations.
> ASSIGNMENT IS DISCLOSED in the submission as demonstration data.

`data/camera_seed.csv` is that file. Its **active tier** (continuous inference) is currently **5 cameras across 5 departments**: cam06 GSRTC, cam09 Police (Junagadh cluster) and cam26 Panchayat, cam27 Municipal, cam28 Health (Bilimora cluster). STATUS.md's last narrative says 6 (with cam10 Municipal); the committed seed, the last launch log and the database say 5 — the seed is the truth.

## 7. Library and hardware behaviours on this laptop (all cost a crash to learn)

| Finding | Source entry | Rule for the fresh build |
|---|---|---|
| **DirectML ONNX session is not thread-safe.** Concurrent `session.run()` from several camera threads → `DmlCommandRecorder.cpp 80004005` then a native segfault (exit 139) that killed the worker process silently | "ROOT CAUSE of the worker-process deaths" | One lock around `session.run()`; pre/post-processing stays parallel. Run() ≈ 50 ms on the GTX 1650, so 6 cams × 3 fps fits |
| **Detector on DirectML: 46–55 ms/frame** (YOLOX-S). CPU in the cloud: 116–300 ms/frame | gap-closure pass 2; P2.3 | GPU path is ~10×; keep `onnxruntime-directml`, and note that a later `pip install onnxruntime` silently clobbers it (force-reinstall + provider check) |
| **PaddleOCR default "medium" models ≈ 6 s per crop on this CPU**; PP-OCRv5_mobile det/rec ≈ **0.45 s/crop (13×)**; `PaddleOCR` object not thread-safe (init race) | gap-closure pass 2, item 2 | Mobile models; lock around init+predict; per-track OCR budget (≥1.5 s between OCR per track, max 2 crops/frame, largest first) |
| `enable_mkldnn=False` required on CPU (paddle 3.3.1 raises `ConvertPirAttribute2RuntimeAttribute`) | P2.4 | Keep |
| **SQLite "database is locked" under 6 writers + API**: one object-event write per inferred frame beat WAL + busy_timeout; a single locked write killed the whole camera pull | "STABILITY FIX" (15 Sep 00:10Z) | `busy_timeout=30s`, `synchronous=NORMAL` under WAL, guard each frame not the loop, object events best-effort. P7 goes further: single-writer thread with `BEGIN IMMEDIATE` |
| **`python-multipart` missing** killed the API at import (CSV `Form` endpoint) while the launcher said "running" | gap-closure pass 2, item 1 | Pin it; the launcher must poll the port and fail loudly |
| **Windows children in `cmd /k` windows swallowed every crash trace**; spawning them detached with stdout/stderr → `data/*.log` was what made the SQLite root cause visible | "STABILITY FIX", fix 1 | Every process logs to a rotating file from day one; P7 D9 notes the 18 Sep run regressed to no log files again |
| **Crop paths with backslashes 404'd** in the UI | gap-closure pass 2, item 8 | Forward slashes in stored paths, always |
| ffmpeg is not on the laptop's PATH; the BtbN portable build was fetched (resumable download, the first attempt died at 181/195 MB) | LAUNCHER FIX 2 & 3 | Reuse `D:\projects\Sentinel_Repo\tools\ffmpeg\ffmpeg-master-latest-win64-gpl\bin`; pin its checksum |
| Health checker probing the CDN for RTSP cameras flipped 29/30 to offline → zero workers on next start | gap-closure pass 2, item 7 | Judge active RTSP cameras by their local tee freshness; never let a flaky CDN probe empty the active set |
| Worker and API are **separate processes**; an in-process pub/sub bus never reaches the API | gap-closure pass 2, item 6; P7 D5 | Cross-process channel is the database (or a real queue), never memory. The API tails the alerts table for SSE |
| Ambiguity-map matches were mislabelled `exact`; fixed | P3+P4 entry | Label match type from the rule that matched |

## 8. Measured numbers (the only ones the HLD may cite as measured)

From STATUS.md's Key measurements table and `data/worker_stats.json`:

| Measurement | Value | Where measured |
|---|---|---|
| Cameras in catalogue | 30 (id + name only) | P0.2, both environments |
| Live over HLS from the cloud | 14/30 | P0.2 (13 Sep) |
| Live over RTSP from the laptop | 27/30 (cam08, cam11, cam30 timed out) | laptop probe, 14 Sep |
| Codec | h264 on every live camera | P0.2; laptop probe |
| Resolutions (HLS copies) | 1920×1080 ×4 · 1280×960 ×2 · 1280×720 ×1 · 960×576 ×1 · 854×480 ×5 · 640×480 ×1 | P0.2 |
| Resolutions (RTSP, laptop) | 1920×1080 / 1280×720 / 2560-wide, 25–30 fps declared | laptop probe |
| Declared vs measured fps | cam24 declared 12 → measured 5.61; cam07 declared 25 → measured 25.0 | P0.2 / measure.py |
| Bitrate samples | cam07 362–745 kbps (HLS) | P0.2 / measure.py |
| Motion-gate skip rate | cam07 83 %, cam24 47 %, cam25 17 %, busy junctions (cam08/10/11) 0 % — cloud, HLS | P2.2 |
| Motion-gate skip rate (laptop, 61 s) | cam06 0.458, cam09 0.069, cam26 0.821, cam27 0.200, cam28 0.239 | worker_stats.json, 18 Sep |
| Sustained inference fps per camera, 5 active (laptop, **61 s**, not 10 min) | cam06 1.18, cam09 1.43, cam26 0.46, cam27 1.23, cam28 1.10 | worker_stats.json, 18 Sep |
| Detections per minute (laptop, 61 s) | cam06 39.4, cam09 4.9, cam26 0.0, cam27 67.9, cam28 45.3 | worker_stats.json, 18 Sep |
| Detector latency | 46–55 ms/frame on DirectML (GTX 1650); 116–300 ms on cloud CPU | gap-closure 2; P2.3 |
| OCR latency | 0.45 s/crop, PP-OCRv5_mobile on this CPU | gap-closure 2 |
| Pipeline 3 (separate rig, 10 Sep) | ring buffer flat at 61 segments / 46 MB; `-c copy` 0.54 % of one core; 62.0 s clip, 13.4 s promotion latency | `docs/reference/model-02-1-event-triggered-evidence.md` §6 |

**Still unmeasured** (the HLD currently claims two of these as `[measured]` — P7 D15): sustained fps per camera over a **10-minute** run; real detection rate per camera per minute over 10 minutes; peak VRAM; peak RAM; plate-read success rate. The previous build's worker wrote these to `data/worker_stats.json` every 10 s — the instrument exists, the run never did.

## 9. Things the previous build could not verify

- Whether the government feed at evaluation has proper ANPR lane cameras (the sandbox's are overview PTZ units).
- The RTSP session cap (suspected ~6 per account, not measured).
- Behaviour across the HLS loop wrap over a long run (P7 D1 says the HLS reader goes silent after the wrap — found by review, not by a run).
- WHEP reachability from the laptop (never probed after GATE A dropped it).
- Whether ~50 cameras appear at evaluation (catalogue had 30 throughout).
