# Glossary — Terminology for Model 2 / 2.1

Every technical term used in our architecture, in plain language, grouped by where it appears in the pipeline rather than alphabetically.

---

## 1. Getting video out of a camera

**RTSP** *(Real Time Streaming Protocol)* — The **remote control** for a video tap. Not the video itself; the language for saying "start sending," "stop," "what do you have?" Like phoning a restaurant to order — the call isn't the food.

**RTP** *(Real-time Transport Protocol)* — The **delivery van** carrying the actual video packets RTSP asked for. Usually written together as RTP/RTSP.

**ONVIF** — The **USB of CCTV.** An agreement between camera makers to speak one common language, so you can ask any ONVIF camera "who are you, what can you do, give me your stream" and get the same answer format. Without it you write a separate driver per brand.

**Vendor SDK** — When a camera maker doesn't follow ONVIF and hands you their own private toolkit instead. Usually Windows-only, usually painful. This is what makes some departments hard to integrate.

**API** — A doorway one program opens for another to walk through.

---

## 2. Getting video onto a screen

**WebRTC** — The tech behind **video calls**. Built for live conversation, so it optimises hard for low delay — it would rather drop a frame than make you wait. Sub-second latency. The control room's main view.

**WHEP** — WebRTC was designed for two-way calls. WHEP is the agreed **handshake for "I only want to watch, not talk."**

**HLS** *(HTTP Live Streaming)* — Chops video into small files and posts them with an index; the player downloads file after file. Because it's **ordinary web requests**, it passes any firewall and works on any phone. Cost: a few seconds behind live.

**Playlist / .m3u8** — HLS's **table of contents.** Lists which chunks exist, in order. Rewritten constantly as chunks appear and expire.

**Segment / .ts** — One chunk. In our system, 2 seconds of video. These are the "note cards" on the rack.

**PROGRAM-DATE-TIME** — A **clock sticker** in the playlist next to each segment saying exactly when it was recorded. This is what lets the promote step find "segments covering 3:00:00–3:01:00."

---

## 3. What video actually is

**Codec** — The **squeezing method**. A single raw 1080p frame is ~6 MB; a codec compresses it.

**H.264 / H.265** — The two common codecs. **H.265 is roughly half the size** for the same quality but costs more CPU to decode. The sandbox mixes both — the pipeline must handle either.

**Frame** — One picture. 25 fps = 25 pictures per second.

**Keyframe / I-frame / IDR** — A **complete picture**. Every frame after it stores only *what changed*. This is why you can't start watching mid-stream — you'd have "what changed" with nothing to change from. **You must start at a keyframe.** It's why our segments are keyframe-cut, so clips always start clean.

**GOP** *(Group of Pictures)* — The run from one keyframe to the next. A 2-second GOP = a full picture every 2 seconds.

**PTS** *(Presentation Timestamp)* — A **time label the sender stamps on each frame**. Critically different from *when it arrived*. On connect, buffered frames arrive faster than real time, so anything timed by arrival computes nonsense — impossible vehicle speeds, broken trackers.

**Bitrate** — Data per second. Our validated test feed: **3 Mbps ≈ 22 MB/min ≈ 1.35 GB/hour** per camera.

**Resolution** — Picture size in pixels. 1920×1080 = "1080p".

**Decode / Encode** — Decode = unsqueeze into actual pictures. Encode = squeeze back down. Both cost CPU.

**Transcode vs Copy** — **Transcode** = decode then re-encode (expensive, lossy). **Copy** = move already-compressed bytes untouched (nearly free, lossless). Our ring buffer uses copy — measured at **0.54% of one core**.

**Container / Mux** — The **box** the video sits in. MP4 and MPEG-TS (`.ts`) are boxes; muxing is putting streams into one. TS is built for streaming — **cut it anywhere and it still works** — which is why HLS uses it and why our clip extraction is a simple file join.

---

## 4. Networking

**TCP** — **Registered post.** Every packet confirmed, lost ones resent. Slightly slower, never corrupt. **Always use for RTSP.**

**UDP** — **Ordinary post.** Faster, but letters vanish silently. Missing packets look exactly like AI bugs. Also blocked by most government firewalls.

**NAT** — A router sharing one public address across many devices. Means **outsiders can't easily reach in** — a major reason UDP fails and some departmental cameras are unreachable.

**Gateway** — The middle box everything flows through.

**Relay** — Passing data along without storing it.

**Fan-out / tee** — **Pull once, serve many.** One connection to the camera, split internally to feed AI + live view + buffer. Without it, ten operators watching one camera = ten pulls off that department's recorder.

**tmpfs / RAM disk** — A folder that **lives in memory, not on disk.** Behaves like a normal folder, vanishes on reboot, never touches a physical drive. How HLS live view stays genuinely unsaved.

**Edge vs Central** — **Edge** = computers near the cameras (district level). **Central** = the main data centre. Working at the edge means only small results travel, not whole streams. The biggest single lever for the 80,000-camera problem.

**Exponential backoff** — After a failure, wait 2s, 4s, 8s, 16s rather than hammering in a tight loop. Explicitly required by the Resources page.

---

## 5. The AI

**ANPR** *(Automatic Number Plate Recognition)* — Two steps: **find** the plate, then **read** the characters. The only genuinely mandatory analytic in this hackathon.

**OCR** — Picture of text → actual text. The "read" half of ANPR.

**Inference** — **Using** a trained model on new data. (Training = learning; inference = doing.) All our AI work is inference.

**FRS** *(Facial Recognition System)* — Same idea as ANPR, for faces.

**Object detection** — Drawing labelled boxes: car, person, bag.

**Tracking** — Following one object **across frames on a single camera**, keeping its ID stable.

**Kalman filter** — A **predictor**: given position and velocity, guess where the object goes next. Smooths over frames where detection blips. Needs *real elapsed time* between frames — hence PTS.

**Re-identification (Re-ID)** — Recognising the **same vehicle on a different camera**, later, different angle and lighting. Much harder than tracking, and the heart of the Step 4 route-reconstruction test.

**DeepStream** — NVIDIA's toolkit for running AI across many streams on a GPU. Ships "Smart Record" — the ring-buffer idea — as a built-in feature.

**Batching** — Feeding several frames to the GPU at once. Much faster. Catch: cameras have different resolutions, so a fixed-shape batch breaks — exactly what the Resources page warns about.

**GPU** — A chip built to do the same simple maths on thousands of pixels at once. Why AI runs there, not on the CPU.

---

## 6. Storing and searching

**VMS** *(Video Management System)* — The **software a department uses** to view and record its own cameras. Every department runs a different one from a different vendor. That is the entire problem statement in one line.

**NVR / DVR** — The **recorder box**. NVR for IP cameras, DVR for analog.

**Kafka** — A **conveyor belt for events.** Producers drop events on; consumers pick them up. If a consumer stalls, nothing is lost — it queues.

**Elasticsearch** — A **search engine for text.** Finds a plate across millions of records in milliseconds. Like a book's index, for everything.

**PostgreSQL** — A solid standard database. The reliable filing cabinet.

**PostGIS** — The add-on that teaches PostgreSQL about **maps** — distance, area, "what's within 500m." Without it a location is two numbers; with it, it's geography. This is what makes gap-analysis and coverage layers possible.

**Hot / Warm / Cold storage** — Hot = fast and expensive (recent). Cold = slow and cheap (archive). Match tier to read frequency.

**Retention** — How long before deletion. Departments here run 7 or 15 days.

**Ring buffer** — A rack of exactly N slots that writes over itself. Cannot grow, by construction.

---

## 7. Security and evidence

**RBAC** *(Role-Based Access Control)* — Your **job title decides what you can see.**

**Hash / SHA-256** — A **fingerprint of a file.** Change one byte and it changes completely. Proves a clip hasn't been altered since capture.

**Audit trail** — An append-only log of **who did what, when, and why.** Ours logs every clip promotion with its trigger reason.

**Chain of custody** — The unbroken documented trail proving evidence wasn't tampered with between capture and courtroom. Hash + audit trail is how you build one.

---

## 8. The government databases

| Name | Contents |
|---|---|
| **VAHAN** | Vehicle registration — owner, make, model for a plate |
| **SARTHI** | Driving licences |
| **CCTNS** | Crime and Criminal Tracking Network — national police records |
| **eGujCop** | Gujarat Police's own CCTNS platform |
| **AFIS / NAFIS** | Fingerprint databases (state / national) |

---

## 9. Error messages you will actually see

```
Could not find ref with POC
Error constructing the frame RPS
co located POCs unavailable
```

All three mean **"I joined mid-stream and haven't seen a full picture yet."** They stop as soon as the first keyframe arrives. We hit the third during validation; it self-corrected in under a second.

The Resources page warns about these specifically because **a pipeline that quits on the first decoder error will bounce forever** on H.265 streams. Log them; never treat them as fatal.

---

*Companion to `claude/model-02-unified-viewing.md` and `claude/model-02-1-event-triggered-evidence.md`.*
