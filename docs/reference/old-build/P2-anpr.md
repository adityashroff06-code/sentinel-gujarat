# P2 — ANPR pipeline  (budget: 5 hours)

**The floor.** ANPR is the only truly mandatory analytic. Nothing downstream exists without sightings.

Read `docs/04-feed-rules.md` in full before starting. Most of this phase's risk lives in P2.1.

---

## P2.1 — `frame_source.py` — the critical component

**Do:** implement exactly the nine required behaviours listed at the end of `docs/04-feed-rules.md`. A generator yielding `(frame, pts_ms, wall_clock_utc)`.

Specifically:
- Transport chosen from the registry; credentialed URL built in memory, email percent-encoded, **never logged unmasked**.
- `wall_clock_utc` = stream anchor at connect + PTS delta. Never `datetime.now()` at detection time.
- Sampling to target fps by **dropping on PTS**, never by sleeping.
- Inter-frame gaps tolerated, not treated as disconnects.
- Decoder warnings logged at DEBUG, never raised.
- Jittered exponential backoff on genuine stream end — `base 2s * 2^n * random(0.5,1.5)`, cap 30 s — resetting the stream anchor on reconnect.
- Loop-discontinuity detection (PTS reset or abrupt scene-hash change) emitting `stream_restart`.
- `try/finally` release of the capture, always.

**Acceptance — all four, actually run:**
1. Reads 100 frames from a live camera with monotonically increasing `wall_clock_utc`.
2. Sampling at 3 fps over 60 s yields ~180 frames (±15%), and the **PTS span is ~60 s** — proving timing is not arrival-based.
3. Killing the network mid-read triggers reconnect with visibly increasing, jittered delays, and recovers.
4. Join-time decoder warnings appear in DEBUG logs and the loop continues.

Do not proceed until all four pass. Every later phase inherits this module's bugs.

---

## P2.2 — Motion gate

**Do:** OpenCV MOG2 background subtraction. If changed-pixel fraction is below threshold, skip inference entirely. Per-camera threshold in the registry. Handle `stream_restart` by resetting the background model — otherwise the loop cut looks like total motion.

**Acceptance:** log the skip rate. On a quiet camera it should skip a clear majority of frames. **Record the skip rate in STATUS.md** — it is a real measurement supporting the scaling argument.

---

## P2.3 — Vehicle detection

**Do:** YOLOX or RT-DETR (Apache-2.0 — **not Ultralytics**) on the ONNX Runtime, GPU where VRAM allows. Classes: car, truck, bus, motorcycle, person, bag. Apply the per-camera ROI mask from the registry if set.

**Acceptance:** bounding boxes on real sandbox frames, saved as annotated JPEGs for visual inspection. Log peak VRAM.

---

## P2.4 — Plate detection and OCR

**Do:** cascade properly — vehicle crop → plate region → OCR on the plate crop only. **Never OCR a full frame.** PaddleOCR for reading. If VRAM is tight, run OCR on CPU; plate crops are small enough that this is viable.

**Acceptance:** ≥10 real plate strings read from live footage, saved with their crops for inspection. Note the honest hit rate in STATUS.md — a low rate is information, not a failure to hide.

---

## P2.5 — Normalisation and storage

**Do:** implement `src/anpr/plates.py` exactly as specified in `docs/03-data-contracts.md` §6. Write sightings with the **60-second per-plate-per-camera dedupe rule**. Save the plate crop (~2 KB). Store `plate_raw` alongside the normalised plate, always.

**Acceptance:** a vehicle sitting in view for two minutes produces one or two sightings, not hundreds. Verify by query, not by eye.

---

## P2.6 — Worker orchestration

**Do:** `src/ingest/worker.py` — one thread or process per active camera, reading the active set from the registry. Graceful shutdown closing every capture. A supervisor that restarts a dead worker without restarting the whole service. Never two workers on one camera.

**Acceptance:** run `SENTINEL_ACTIVE_CAMERAS` workers for **10 continuous minutes**. Sightings accumulate from multiple cameras. No crash, no leaked capture, no RAM growth trend. Ten minutes, not thirty seconds — a laptop under sustained GPU load throttles and short runs hide it.

---

## P2.7 — GATE B: measure

**Do:** during the 10-minute run, record in STATUS.md:
- sustained frames processed per second per camera, with N active
- **real detection rate: vehicles per camera per minute** — the number the entire 80k storage and query model rests on
- peak VRAM, peak RAM
- motion-gate skip rate
- plate-read success rate

**GATE B:** if plate reads are accumulating with sane confidence, continue. If OCR is producing garbage, **do not spend remaining time tuning the model** — reduce to the best-quality cameras, accept lower recall, and move to P3. A route built from four good cameras scores; a perfect ANPR that never got integrated scores nothing.

---

## P2.8 — Search UI

**Do:** `GET /api/sightings` with filters, plus a search page: plate, camera, time range, minimum confidence. Results in a table with plate crop thumbnails, camera, department, timestamp, confidence.

**Acceptance:** typing a partial plate returns matching sightings with visible crops.

---

**Exit P2 when:** sightings are accumulating from ≥6 cameras, searchable in the UI, with crops, and GATE B is recorded.
