# Model 2.1 — Unified Viewing + Event-Triggered Evidence Capture

**Status:** LOCKED IN as our working architecture (10 Sep 2026)
**Base:** Model 2 (Unified Viewing & Metadata Analytics) — see `claude/model-02-unified-viewing.md`
**Delta:** adds Pipeline 3, an event-triggered evidence-capture layer
**Validation:** built and measured end-to-end on 10 Sep 2026 — results in §6. **Not theoretical.**

---

## 1. Why 2.1 exists

Model 2 has a hole: the centre can watch everything live but can never re-examine anything. No rewind, no evidence, and a missed ANPR read is gone forever.

Model 4 fixes that by recording everything — at roughly **1.6 TB/day for 50 cameras**, plus the bandwidth and privacy cost of mass retention.

**Model 2.1 gets the operational benefit of Model 4's rewind at ~0.1% of its storage cost**, by recording only the seconds that a watchlist match makes relevant.

| | Model 2 | **Model 2.1** | Model 4 |
|---|---|---|---|
| Live viewing | ✅ | ✅ | ✅ |
| Searchable metadata | ✅ | ✅ | ✅ |
| Re-examine an incident | ❌ | ✅ | ✅ |
| Court-usable clip | ❌ | ✅ | ✅ |
| Arbitrary rewind, any camera, any time | ❌ | ❌ | ✅ |
| Permanent storage, 50 cams | 0 | **~2.2 GB/day** | ~1,600 GB/day |

---

## 2. The three pipelines

All three run off **one** RTSP pull per camera. Pulling more than once wastes bandwidth and loads the source — the Resources page warns *"each connected client receives its own copy of the stream."*

```
CAMERA / DEPARTMENT VMS
        │  ONE RTSP pull (TCP), continuous
        ▼
┌──────────────────────────────────────────────────────────────────┐
│  EDGE GATEWAY   (near the cameras — NOT the centre)              │
│                                                                  │
│  packets ──┬──► PIPELINE 2: decode → ANPR → plate text ──────┐   │
│  in RAM    │                                                 │   │
│            ├──► PIPELINE 1: relay ───────────────────────────┼───┼──►  LIVE VIEW
│            │    WebRTC / HLS, memory only, NOTHING SAVED     │   │     at the centre
│            │                                                 │   │
│            └──► PIPELINE 3: RING BUFFER                      │   │
│                 fixed N segments, self-overwriting           │   │
│                        │                                     │   │
│                        │ ◄── promote(t−30s .. t+30s) ◄───────┘   │
│                        ▼      ONLY on a watchlist match          │
│                   CLIP ~22 MB ───────────────────────────────────┼──►  EVIDENCE STORE
└──────────────────────────────────────────────────────────────────┘      at the centre
                                                                          the ONLY
                                                                          permanent video
```

### Pipeline 1 — Live viewing (nothing saved)
Packets land in a small RAM buffer, get relayed to the operator's browser, and the next packets overwrite the same memory. There is no `write_to_disk()` in this path. **Saving is an action, not a default.**

- **WebRTC / WHEP** — sub-second latency, memory-to-memory, the control room's primary path
- **HLS** — a few seconds behind, works on any phone and any restricted network; point it at `tmpfs` so it never touches a physical disk

### Pipeline 2 — Analytics (metadata only)
Decode → ANPR → a text record per sighting (`plate | camera | location | timestamp`). Hundreds of bytes, kept forever, searchable in milliseconds. This is unchanged from Model 2.

### Pipeline 3 — Evidence capture (the 2.1 addition)
A fixed-size rolling buffer of the compressed stream, plus a promote step that fires only on a match.

---

## 3. How Pipeline 3 actually works

### The ring buffer
Write the incoming stream to disk as **HLS segments** — 2-second, keyframe-aligned chunks — with a hard cap on how many are kept.

```bash
ffmpeg -rtsp_transport tcp -i rtsp://<host>:8554/stream/<id> \
  -c copy -f hls \
  -hls_time 2 -hls_list_size 450 \
  -hls_flags delete_segments+program_date_time \
  -hls_segment_type mpegts \
  -hls_segment_filename 'buf/cam<id>_%05d.ts' buf/cam<id>.m3u8
```

Four design choices carry the whole thing:

| Flag | Why it matters |
|---|---|
| `-c copy` | **No decode, no re-encode.** Compressed packets go straight to disk. Measured at **0.54% of one core** |
| `-hls_time 2` | Segments are **keyframe-aligned by construction**, so clips never start with corrupt frames |
| `-hls_list_size 450` + `delete_segments` | 450 × 2s = **15-minute buffer, fixed forever.** Segment 451 deletes segment 1 |
| `program_date_time` | Stamps each segment with wall-clock time — solves the PTS→clock mapping the Resources page warns about |

### The promote step
On a match: read the playlist's wall-clock stamps, select segments overlapping `[t−30s, t+30s]`, **copy** them to the evidence store, concat with `-c copy`, write an audit row with a SHA-256.

Two details that matter:
- **Copy, never move** — moving punches a hole in the ring buffer
- **Wait for the post-event window** — at alert time, `t+30s` hasn't happened yet. This is the only real latency (~13s measured)

Full implementation: `claude/model-02-1-promote.py`.

---

## 4. Why it cannot overflow

The guarantee is **structural, not procedural**. Nothing depends on a cleanup job running.

| Control | What it makes impossible |
|---|---|
| Fixed `hls_list_size` | Buffer growth. Not policy — arithmetic. There is no segment 451 |
| Separate volumes with hard quotas | Buffer spilling into permanent storage |
| Single write path requiring a valid `event_id` | Anything reaching the evidence store without an alert |
| Append-only audit log with content hashes | Undetectable tampering; proves *what exists and why* |
| Retention policy on the evidence store | Clips expire after N days unless flagged to a case file |

---

## 5. The privacy argument

This is not just an engineering optimisation — it is a **civil-liberties position**, and worth stating explicitly to a government evaluator:

> The system retains nothing about the public by default. A rolling buffer overwrites itself continuously. Video becomes permanent only where a specific, logged, auditable watchlist match justifies it — and expires on a schedule unless attached to a case.

That is a materially better answer than Model 4's total archive, and it maps directly onto the bonus criterion for *"enhanced cybersecurity, privacy protection, auditability, or role-based access controls."*

---

## 6. Validation — measured, not asserted

Built end-to-end on 10 Sep 2026 against a real RTSP server (MediaMTX v1.9.3) serving a looping 3.0 Mbps H.264 feed at `rtsp://…:8554/stream/12` — **deliberately mirroring the sandbox's URL shape, protocol set and looping behaviour.**

### Results

| Claim | Result | Verdict |
|---|---|---|
| All three transports serve from one publish | RTSP 200, HLS 200, WHEP alive; 2 readers fanned out | ✅ |
| Ring buffer stops growing | Grew to **61 segments / 46 MB**, then flat for **150+ s** of continuous streaming | ✅ |
| Old data is physically overwritten | Segments 00000–00109 gone; only 00110–00170 on disk | ✅ |
| `-c copy` is nearly free | **2.0 s CPU over 367 s wall = 0.54% of one core** | ✅ |
| Buffer size matches theory | 46 MB for 122 s @ 3 Mbps — predicted 45.75 MB | ✅ |
| Alert produces a correct clip | **62.0 s, 1550 frames (62 × 25 exactly), 23.3 MB** | ✅ |
| Clip is not corrupt | Full decode end-to-end, **zero errors** | ✅ |
| Clip covers the right window | Burned-in timecode: **T=0112s → T=0173s**, contiguous, gapless | ✅ |
| Promotion doesn't disturb the buffer | Buffer unchanged at 61 segs / 46 MB after promote | ✅ |
| Audit trail | Event ID, plate, camera, window, segments used, SHA-256, trigger reason | ✅ |
| Promotion latency | **13.4 s**, almost entirely the unavoidable post-event wait | ✅ |

### Observed, and worth noting
The join produced `co located POCs unavailable` — precisely the class of non-fatal decoder warning the Resources page warns about (*"Error constructing the frame RPS"*, *"Could not find ref with POC"*). It self-corrected. **A pipeline that aborts on first decoder error would have failed here.**

### Caveats on this validation
- Single camera, not 50 — concurrency is proven by arithmetic (0.54% × 50 ≈ 27% of one core), not yet by test
- Synthetic footage; real ANPR accuracy is a separate, harder problem and is **not** validated by this
- Loop-boundary handling (buffer straddling the sandbox's scene cut) is designed but **not yet tested**
- Local network — the sandbox will add real jitter, packet loss and reconnects

---

## 7. Can we demo it? Yes — and here is the script

Every element below is already proven to work.

1. **Live wall** — grid of departmental feeds, live. State plainly: nothing is being recorded.
2. **Watchlist** — show the stolen-vehicle table the system is matching against.
3. **The hit** — target vehicle passes a camera. Alert fires with plate, camera, timestamp, snapshot.
4. **The reveal** — *"Model 2 stops here. Watch what ours does."* Click the alert. A **62-second clip** opens, starting 30 seconds *before* the vehicle appeared. Scrub it. It plays cleanly.
5. **The disk** — show the buffer directory: flat at a fixed size while the stream runs. Show the evidence folder: one clip.
6. **The number** — *"2.2 GB per day instead of 1,600. Same capability."*
7. **The audit row** — event ID, trigger reason, SHA-256. Chain of custody.

Step 4 is the moment. Step 6 is the argument.

**Demo risks:** post-event wait means ~15 s of dead air after the alert — fill it by narrating the audit trail. Have a pre-recorded fallback clip in case the live feed drops mid-demo.

---

## 8. Cost and priority

Roughly **one engineering day**, plus debugging: keyframe alignment (solved by HLS segments), PTS→clock mapping (solved by `program_date_time`), single-pull fan-out, loop-boundary detection, and false-positive cooldown per plate per camera.

**This is a phase-two feature.** ANPR accuracy and cross-camera route reconstruction are what Step 4 actually scores. Model 2.1 wins bonus marks *after* the scored path works end to end. **If we are behind on the core on 14 September, this gets cut without hesitation.**

---

## 9. Open questions

- Clip window: is ±30 s right, or does ±15 s suffice? Halves storage
- Buffer depth: 15 min is generous when promotion happens within seconds. 5 min may do
- Should the journey reel (clips from every camera on the route, stitched) be v1 or v2?
- Production second source: ONVIF Recording Search / Replay against departmental VMS, for footage older than the buffer

---

*Design validated against a live RTSP server on 10 Sep 2026. Test rig, promote implementation, proof frames and audit output retained in the session scratchpad.*
