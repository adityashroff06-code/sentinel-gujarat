> **Editor's note (fresh build):** copied verbatim from the previous build's `04-feed-rules.md`. `frame_source.py` below is the fresh build's `ml/ingest/` package (`base.py`, `rtsp.py`, `replay.py`, `hls_vod.py`); the nine required behaviours are its acceptance test (`docs/tasks.md` S2.1–S2.2).

# 04 — Feed rules: the sandbox's contract, in executable form

Source: the official *Consuming the Sentinel Camera Grid* guide. Every item below is stated by the organisers. Treat this list as a scoring rubric in disguise — these read like the exact failure modes they watched teams hit last time, and every one is a cheap defensive fix but an expensive bug on demo day.

## Access model

| Protocol | Endpoint | Reachability |
|---|---|---|
| **HLS** | `https://cctv.corp8.cloud/<id>/index.m3u8` | Served over the CDN, behind the access password. **Works on any network.** |
| **RTSP** | `rtsp://<email>:<password>@103.250.160.189:8554/stream/<id>` | Direct on the public static IP. Needs port 8554/TCP open. |
| **WebRTC (WHEP)** | `http://<email>:<password>@103.250.160.189:8889/stream/<id>/whep` | Needs 8889/TCP (and 8189/UDP). |

- RTSP and WebRTC carry media over TCP/UDP that a CDN cannot proxy, which is why they sit on the raw IP.
- **Credentials are required** on RTSP and WebRTC, embedded in the URL. The `@` in the email must be percent-encoded as `%40` (`alice%40example.com`). Only approved emails connect.
- `<id>` is `cam01` … `cam30`. **Start from the catalogue, not from the pattern** — the camera set can change.

```bash
curl -s https://cctv.corp8.cloud/cameras.json
```

**Design consequence:** HLS is the only transport guaranteed to work from a home connection. `frame_source.py` must prefer whatever the probe proved reachable and fall back cleanly, with the choice recorded per camera in the registry `transport` column. If RTSP is blocked, that is not a failure — the ring buffer reads HLS segments directly, which is simpler rather than harder.

## What you are connecting to

Every camera is a live stream. One second of video takes one second to arrive, frames carry monotonic PTS, and there is **no seeking and no way to run ahead of real time**. Treat each endpoint as a physical camera on an operational network.

## The DO list

| Rule | Implementation |
|---|---|
| **Force RTSP over TCP** | `rtsp_transport=tcp`, always. UDP fails across NAT and firewalls and produces corrupt frames that look exactly like model bugs. If 8554 is blocked, use HLS — never fall back to UDP. |
| **Drive all timing from PTS** | `CAP_PROP_POS_MSEC` (OpenCV), buffer PTS (GStreamer), or RTP timestamps. On connect the gateway replays its buffered GOP, so the first second or two arrives **faster than real time**. A tracker timestamping by arrival will compute impossible velocities after every connection. Kalman filters and multi-object trackers must be fed PTS deltas. |
| **Reconnect automatically with backoff** | Feeds are supervised and may restart. Exponential backoff from ~2 s, capped ~30 s. **Add jitter** — `base * 2^n * random(0.5, 1.5)` — or every client resynchronises and hammers in waves. No tight loops. |
| **Expect a scene discontinuity** | Each feed is a continuous recording that **loops**. At the loop point the scene cuts abruptly, like a camera reboot. Background models, re-ID galleries and track IDs must recover from a hard cut. |
| **Pace your load** | Each connected client gets its own copy of the stream. Open only cameras you are actively processing; close captures you are done with. |

## The DON'T list

| Rule | Implementation |
|---|---|
| **Don't trust the reported frame rate** | `CAP_PROP_FPS` often mismatches real delivery. Using it to convert pixels-per-frame into speed, dwell time, or any time-derived metric produces incorrect results. Measure delivered fps by counting frames over a wall-clock window. |
| **Don't assume a constant frame rate** | Frame intervals are not uniform. Tolerate inter-frame gaps without treating them as disconnects. Motion models must use actual elapsed PTS. |
| **Don't treat join-time decode warnings as fatal** | Attaching mid-stream to a mixed H.264/H.265 grid produces `Error constructing the frame RPS`, `Could not find ref with POC`, `co located POCs unavailable` until the first IDR arrives. Normal, self-correcting. Pipelines that abort on first decoder error will bounce. |
| **Don't assume a uniform grid** | Cameras differ in resolution, codec, frame rate, bitrate. Read per-camera properties from the catalogue and size batching, buffers and decoders accordingly. A fixed-shape inference batch across every camera will not work unscaled. |
| **Don't plan around obtaining copies of the footage** | No file download. Pulling a stream URL with curl/wget yields a partial file that *looks* complete. **Build against a live capture from the start.** |
| **Don't publish to the gateway** | Consume only. Never push a stream to any path, never call the gateway's control API. |

## Required behaviour of `frame_source.py`

This one module carries most of the risk in the project. It must:

1. Accept a camera record and choose its transport from the registry.
2. Build the credentialed URL in memory from environment variables, percent-encoding the email. **Never log it unmasked.**
3. Yield `(frame, pts_ms, wall_clock_utc)` tuples. `wall_clock_utc` = stream anchor at connect + PTS delta.
4. Sample to the requested fps by **dropping on PTS**, not by sleeping.
5. Survive inter-frame gaps without declaring a disconnect.
6. Log decoder warnings at DEBUG, never raise on them.
7. Reconnect with jittered exponential backoff on genuine stream end, resetting the stream anchor on reconnect.
8. Detect the loop discontinuity (large PTS reset or abrupt scene-hash change) and emit a `stream_restart` signal so trackers and background models reset rather than producing garbage across the cut.
9. Release the capture on exit, always — `try/finally`, no exceptions.

## Pre-submission checklist (official)

- [ ] Every client forces RTSP over TCP
- [ ] No timing logic depends on `CAP_PROP_FPS` or frame arrival time
- [ ] Inter-frame gaps don't crash or stall the pipeline
- [ ] Reconnect with backoff implemented **and tested by restarting a feed**
- [ ] Decoder warnings on join are logged, not fatal
- [ ] Camera list and per-camera properties read from the catalogue
- [ ] Pipeline handles mixed H.264/H.265 and mixed resolutions
- [ ] Behaviour is sane across a scene discontinuity

Run this list before submitting. Tick each item against an observation, not an intention.

## Reporting a feed problem

Include camera id, exact URL (credentials masked), client and version, UTC timestamp, and the client-side error log. Confirm the camera's live status in the catalogue before reporting it down.
