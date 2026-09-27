> **Editor's note (fresh build):** copied verbatim from the previous build's `05-demo-script.md`. The screens it names exist in the fresh build under the same names except Command (`Dashboard`); the walkthrough the videos follow is task S3.4, the recording task is S5.4.

# Demo run sheets — v2.7 (27 Sep 2026, decisions F72–F77) — **record these**

These supersede v2.6 below for recording. They add the four Phase 7 pieces:
- the **analysis render** (S7.1, F74);
- **vehicle thumbnails** on every read and a **full evidence frame on a watchlist hit** (S7.2, F73);
- the **alert toast** (S7.3);
- **production**: a hook, narration, captions, zoom-ins and an end card (S7.5).

v2.6's `own01` mechanics are unchanged (a stock clip onboarded on camera and published once through, F56/F70/F71), except that its file and watch plate now come from S7.0's progress block. The route is still the labelled demo vehicle.

**The judges' question for each video is "is this a working system?"** Every beat below answers it with something the backend produced on screen, in real time, with the IST clock visible.

## Production rules (both videos)

- **Allowed:**
  - a hook card at the start and an end card at the finish (plain text on the product's dark background);
  - captions that say what is on screen;
  - zoom-ins (a crop of the recorded frame), to make a plate, a thumbnail or a toast readable;
  - trimming dead air (page loads, waiting for the next vehicle);
  - the render (S7.1) played as its own segment, full screen, with its burned-in label left visible.
- **Not allowed:**
  - reordering anything inside a take;
  - a cut between a read and the alert it fires (the clock stays in shot across that moment);
  - speed-ups while a clock is visible;
  - any overlay that adds a box, plate, number or result the platform did not produce;
  - hiding a `DEMO` badge;
  - background music louder than the voice.
- **Voice:** ~140 words a minute; each video's script below is ≤ 400 words, so 3:00 leaves room for pauses. Record the voice live or dub it afterwards, but keep every "this is live" sentence over a live shot.
- **Screen:** unchanged from v2.6 — Chrome guest window, 1920×1080, zoom 100 %, bookmarks bar hidden, the Chrome window only. The render plays in VLC or Chrome full screen. No terminal, `.env`, log tail, password field or address bar with a credential appears in any frame.
- **Tools:** OBS or Win+Alt+R to record; any editor you know to cut (Clipchamp ships with Windows 11). Export 1080p H.264, ≤ 3:00, then upload unlisted.

## Before recording

- The v2.6 checklist: `launch.py status` shows the worker alive and `feeds: 28/28`, and Command's feed strip shows **cam06 READING** before video 2.
- S7.2 and S7.3 are on `main`, and the platform was restarted after they merged.
- Chime on (header toggle). Sign in **before** starting the recorder, or show the login and sign in with the password masked.
- Video 1 setup: v2.6 steps 2–3 (`SENTINEL_ACTIVE_CAMERAS=6`, restart; reset after every dry run). Step 1's file is **the one S7.0 names** (`own01.mp4` at 1080p, or `own01-1440.mp4`). The watch plate is **the one S7.0 and S7.4 name** (v2.6's default was `MH02EX1995` at ~41 s of the clip, i.e. ~71 s after publishing with the 30 s pre-roll).

## Video 1 — our own feed (≤ 3:00)

| # | Time | Beat | Says | Shows |
|---|---|---|---|---|
| 0 | 0:00–0:08 | **Hook** | "Gujarat's plan covers about eighty thousand cameras across many departments. No control room can watch them all. Sentinel watches for you — and only keeps what the law can justify." | Hook card: **"~80,000 cameras. No one can watch them all."** then the Sentinel wordmark |
| 1 | 0:08–0:30 | **What the AI sees** | "This is Sentinel's own pipeline run on a recorded traffic clip at full frame rate. Every box, every track number and every plate you see comes from the same detector, tracker and plate reader that run live on the platform." | The S7.1 render, full screen, ~20 s of its densest stretch. **Leave its label visible.** Zoom once onto a plate label as it appears. Caption: *"Pipeline output on recorded stock footage — processed offline"* |
| 2 | 0:30–0:35 | **Sign in** | "One platform, role-based access." | The header with user and role (already signed in) |
| 3 | 0:35–0:58 | **Onboard a camera** | "Nothing is hard-coded. I'm onboarding a new camera now, through this form. The same works in bulk by CSV, or over the API." | Cameras → **Add camera** → `own01` as in v2.6 beat 2 → it appears in the table and as a pin on Map. Point at **Bulk import (CSV)** |
| 4 | 0:58–1:10 | **The watchlist** | "Here's a representative watchlist. I'm adding a stolen vehicle to it now." | Watchlist → add the S7.0 plate (`stolen_vehicle`, high) |
| 5 | 1:10–1:25 | **It is live** | "That camera is now a live feed — a different system from the government grid, in the same viewer. It replays a stock traffic clip once through; we didn't film it." | Start the feed off camera (v2.6 beat 4 command). Live Wall → the `own01` tile beside the sandbox tiles |
| 6 | 1:25–2:05 | **Detection, then the hit** | "Every plate the pipeline reads lands here, with the vehicle it came from. … There — the watchlisted vehicle. The alert fires from that live read, and it reaches every screen." | Search filtered to `own01`: rows filling with **vehicle thumbnails**, plate crops, confidences, `LIVE`. Then the **toast + chime** (zoom in on it) → **View** → the evidence frame lightbox |
| 7 | 2:05–2:18 | **Evidence, only on a hit** | "This full frame was stored for one reason: a watchlist match. Its SHA-256 is in the audit trail. Reads that don't match never keep a frame — watching is not storing." | The lightbox: the frame with the vehicle and plate boxes, the caption bar, the SHA-256. Caption: *"Full frame stored only on a watchlist hit · SHA-256 audited"* |
| 8 | 2:18–2:35 | **The route** | "Where else has a vehicle been? Our clip is one location, so for the multi-camera route this is our injected demonstration vehicle — badged DEMO." | Route → `GJ01AB1234` with the numbered pins, departments crossed and the timeline; keep the DEMO badge in shot |
| 9 | 2:35–2:48 | **The report** | "And everything exports with timestamps and where each row came from." | Reports → Detection report (HTML), `own01` rows `live`, provenance column visible |
| 10 | 2:48–3:00 | **End card** | "Sentinel. One registry, one viewer, live number-plate recognition, and evidence only when it's justified." | End card (below) |

## Video 2 — the government-provided feed (≤ 3:00)

| # | Time | Beat | Says | Shows |
|---|---|---|---|---|
| 0 | 0:00–0:06 | **Hook** | "Now the government-provided feed — live." | Hook card: **"Live on the Government-provided feed"** |
| 1 | 0:06–0:28 | **Onboarding** | "The organisers' catalogue is the contract. All thirty sandbox cameras were onboarded from it automatically — nothing is hard-coded. Departments and coordinates are seeded, because the catalogue carries none." | Cameras → the 30 rows with source **catalogue** → Map, pins by department |
| 2 | 0:28–0:48 | **Viewing** | "Five cameras are analysed live over RTSP. The rest are viewed from the organisers' recording. We say which is which on every tile." | Live Wall → **Analysed 5** (`LIVE · RTSP`), then **Sandbox 30** (`CDN RECORDING`). Never call a recording live |
| 3 | 0:48–1:28 | **ANPR on the live feed** | "This is camera six, read live. Every row is a real read: the vehicle, its plate, the confidence and the time — all from the government feed." | Search → a plate from *Most read live* on **cam06**: **vehicle thumbnails** and crops, confidences, IST times, all `LIVE`. Zoom onto one thumbnail so the plate box shows |
| 4 | 1:28–1:48 | **Vehicles and people** | "Beyond plates, the same pass counts cars, motorcycles, trucks, buses and people on every analysed camera." | Reports → *Object detection per camera* |
| 5 | 1:48–2:05 | **Line crossing** | "A virtual line across the bypass counts every crossing, live." | Zones → cam06's *Bypass crossing line*; Reports' line-cross column |
| 6 | 2:05–2:25 | **A real alert on the government feed** *(if S7.2's acceptance left one)* | "This alert was fired by a live read on the government feed, against our watchlist. The evidence frame and its hash were stored because of the match — and only because of it." | Alerts → the S7.2 live cam06 alert → evidence lightbox with the SHA-256. If there is no such alert, drop this beat and give beat 3 the time |
| 7 | 2:25–2:48 | **The report** | "The output report: every detected vehicle and plate, with timestamps, camera, department and provenance." | Reports → **Detection report (HTML)** opened on screen; scroll it |
| 8 | 2:48–3:00 | **End card** | "Designed for about eighty thousand cameras. The design is in our HLD." | End card (below) |

## End card (both videos, 10–12 s)

> **SENTINEL** — Integrated Video Management & Analytics
> Model 1 registry + GIS · Model 2 unified viewing & live ANPR · watchlist alerts · evidence on hits only
> Measured on one laptop (GTX 1650): 5 live government cameras, 0 worker restarts `[measured, S4.1]`
> Statewide design: ~80,000 cameras, text + plate crop over the WAN `[model, HLD §7]`
> Aditya Shroff · Gujarat Police Sentinel Innovation Challenge 2026 · Category 1

Every number on the card carries its label, as in the HLD. Nothing else is claimed.

---

# Demo run sheets — v2.6 (25 Sep 2026, decision F70) — *superseded for recording by v2.7 above; its `own01` mechanics still apply*

These supersede the v2.3 tables below for recording: S3.6 closed without filming (F70), so "our own feed" is a stock traffic clip that **we onboard as our own camera on camera** and publish **once through**, which puts the real detection → watchlist → alert path on screen (F56's once-through rule, so every read is counted once). The multi-camera route is the labelled demonstration vehicle. Beat content and the rules at the bottom of this file are unchanged.

**What the videos are.** Two **screen recordings of the running platform**, each ≤ 3 minutes, narrated, uploaded **unlisted**; the links go on the submission form and into deck slide 18. The CCTV clips in `archive.zip` are the platform's *input* (the local feeds), not these videos.

## Before recording (both videos)

- **Where:** the laptop, **Google Chrome**, `http://127.0.0.1:8000/`. The hosted URL is not needed (S5.4 does not wait on S3.5). Chrome, not Edge, because cam06 and five other sandbox cameras are H.265 (F62).
- **Screen:** Chrome in a fresh guest window, bookmarks bar hidden, zoom 100 %, 1920 × 1080; record the Chrome window only (Win + Alt + R, or OBS). No terminal, `.env`, log tail or password manager in shot. Sign in with the password field masked, or sign in before starting the recorder and show the login page only by signing out at the end.
- **State:** `python launch.py status` shows the worker alive and `feeds: 28/28`; Command's feed strip shows **cam06 READING** (daylight on the sandbox loop; the S4.1 reads came 13:30–17:00 IST on 25 Sep). If the sandbox is down, record video 1 first; it does not depend on the sandbox.
- **Takes:** several; keep the best; trim dead air only (no reordering, no overlays that invent anything).

## Video 1 — our own feed (≤ 3 min)

**One-time setup, then a full dry run before the real take** (a laptop Claude session can do both; nothing here has run yet):

1. A 1080p copy of stock clip `13270133_3840_2160_30fps.mp4` (the source of `local01`; the wall's copy is 720p, too small for its ~45 px plates) with 30 s of black in front, so the worker is connected before the first vehicle: `<ffmpeg> -i D:\projects\sentinel-footage\raw\13270133_3840_2160_30fps.mp4 -vf "scale=-2:1080,tpad=start_duration=30:color=black" -r 30 -c:v libx264 -preset veryfast -crf 20 -bf 0 -g 60 -an D:\projects\sentinel-footage\own01.mp4` (`<ffmpeg>` = the path printed by `.venv\Scripts\python -c "from backend.core import config; print(config.ffmpeg())"`). The offline scoring (`data/footage_analysis.json`) read, in the clip's own time: `MH02F15860`/`MH02EZ1785` at ~9 s, `MH02FG7423` at ~25 s, **`MH02EX1995` at ~41 s (conf 0.90)**, `MH02FG5664` at ~49 s. With the pre-roll add 30 s to each.
2. `.env`: `SENTINEL_ACTIVE_CAMERAS=6` (the five analysed sandbox cameras plus `own01`), then `python launch.py stop` and `python launch.py start` (the cap is read at start).
3. After every dry run: delete `own01` (Cameras → edit, or set its tier to `registered`) and remove the test watchlist entries, so the real take starts clean. Its reads stay as `live` reads on camera `own01` — one pass each, which is what F56 requires.

| # | Beat | Says | Shows |
|---|---|---|---|
| 1 | **Sign in** | "One platform, role-based access." | The login page, signing in as **admin**; the header shows the user and role. Two seconds |
| 2 | **Onboard a camera** | "Nothing is hard-coded. A camera is onboarded through this form, in bulk by CSV, or over the API." | Cameras → **Add camera**: id `own01`, department, location name *"Own camera 1 — stock traffic clip, seeded coordinates"*, latitude/longitude, transport **rtsp**, RTSP URL template `rtsp://127.0.0.1:8556/stream/own01`, tier **active**, notes *"private camera, consent on file (O10)"* → it appears in the table and as a pin on Map. Point at **Bulk import (CSV)** on the same screen |
| 3 | **The watchlist** | "A representative watchlist. I am adding this vehicle now." | Watchlist → add `MH02EX1995` (stolen vehicle, high) and `MH02FG7423` |
| 4 | **It is live** | "That camera is now a feed like any other — a different system from the government grid, in the same viewer. It replays a stock traffic clip once through: not footage we filmed." | Off camera, start the feed: `.venv\Scripts\python scripts\replay_publish.py --many own01=D:\projects\sentinel-footage\own01.mp4 --port 8556 --hls-port 0` (once through, its own mediamtx on 8556; the wall's feeds stay on 8554). Live Wall → the `own01` tile (from the worker's tee) beside the sandbox tiles |
| 5 | **Nothing is recorded** | "This video is relayed, not stored. Watching is not the same as storing." | Over the live wall |
| 6 | **Detection and the hit** | "The pipeline reads every plate it can. The watchlisted vehicle passes." | Search or Command filling with `own01` reads (`LIVE`, crops, confidences); then the alert arrives on **Alerts** from the real read: plate, crop, camera, timestamp, match type, `LIVE` |
| 7 | **The route** | "Where else has it been? Our own camera is one location, so for the multi-camera route this is our **injected demonstration vehicle**, badged DEMO." | Route → `GJ01AB1234`: numbered pins on three cameras, the timeline with DEMO crops and timestamps. Keep the DEMO badge in shot |
| 8 | **The report** | "Exported with timestamps and where every row came from." | Reports → Detection report (HTML), provenance column visible, `own01` rows `live` |

If `own01` produces no watchlist hit in the take (OCR misreads the same plate differently pass to pass — F58), use a plate it did read as the next take's watchlist entry, from Search.

## Video 2 — the government-provided feed (≤ 3 min)

| # | Beat | Shows |
|---|---|---|
| 1 | **Onboarding** | Cameras: the 30 sandbox cameras with source **catalogue**, onboarded from the organisers' catalogue at start (`launch.py` step 6); Map shows them by department. Say: "the catalogue is the contract; nothing is hard-coded", and that departments and coordinates are seeded because the catalogue carries none |
| 2 | **Viewing** | Live Wall → **Analysed 5**, 4-up: `LIVE · RTSP` tiles with department labels; then **Sandbox 30** to show `CDN RECORDING` tiles — never call a recording live |
| 3 | **ANPR** | Search → a plate from *Most read live* on **cam06**: crops, confidences, timestamps, all `LIVE` |
| 4 | **Vehicle and person detection** | Reports → *Object detection per camera* (car, motorcycle, truck, bus, person counts) |
| 5 | **Line crossing** | Zones → cam06's *Bypass crossing line*; Reports' line-cross column (53 events on the live feed, 25 Sep) |
| 6 | **The report** | Reports → **Detection report (HTML)** opened on screen: vehicles and plates with timestamps, camera, department and provenance |

---

# Demo run sheets — v2.3 (22 Sep 2026)

**These two tables are the ones to record.** They replace the 15 Sep run sheet kept below, which missed what the portal actually asks for: onboarding is the **first** thing the own-feed video must show, and the government-feed video must show more analytics than ANPR. Both still run to 2–3 minutes, rehearsed with a timer, narrated over a screen recording, with no slides inside the video.

Sources: portal Step 5 ("Onboarding and processing of live or recorded CCTV feeds… AI-powered detection and analytics… correlation… automatic generation of real-time alerts"); FAQ 31 (the government-feed video shows "onboarding, viewing, and analytics output (ANPR, vehicle/person/intrusion/object detection)"); decision F43 (the hit and the route are real).

**v2.5 (24 Sep, decisions F54–F56) — what each video proves, in the brief's names.** Video 1: Model 1 (onboarding a camera, the map), Model 2 across **two systems** (the organisers' gateway and our mediamtx), Pipeline 1 (live view, nothing stored) and Model 2's metadata analytics (the real hit and the route). Video 2: Model 1 (the catalogue onboarded) and Model 2 on the government feed — cam06 and the demo tier **pulled live**, never a recorded copy. Pipeline 3 is not shown: it is described in the HLD, not built — so beat 4's "nothing is recorded" is literally true. The own cameras replay footage filmed on a named date, published once with the real gaps between the shots, so the route's times are real; say so in beat 3.

## Video 1 — our own feed (≤ 3 min)

| # | Beat | Says | Shows |
|---|---|---|---|
| 1 | **Sign in** | "One platform, role-based access." | The login page, signing in; the header shows the user and role. Two seconds, not more |
| 2 | **Onboard a camera** | "Nothing is hard-coded. A camera is onboarded through the form, or in bulk by CSV, or over the API." | The Cameras screen: add `local01` with its real location, department and coordinates; it appears in the table and as a pin on the map |
| 3 | **It is live** | "That camera is now a feed like any other." | The tile for `local01` playing beside the sandbox tiles — two different systems in one viewer |
| 4 | **Nothing is recorded** | "This video is relayed, not stored. Watching is not the same as storing." | Say it plainly over the live wall |
| 5 | **The watchlist** | "A representative watchlist. I am adding this vehicle now." | The Watchlist screen; add the real plate on camera |
| 6 | **The hit** | "The vehicle passes the gate." | The alert appears live from a **real** read: plate, crop, camera, timestamp, match type — with a `live` provenance badge |
| 7 | **The route** | "Where else has it been?" | Route: numbered pins across `local01`–`local03`, the timeline with crops and real timestamps |
| 8 | **The report** | "Exported with timestamps." | The detection report, provenance column visible |

If S3.6 produced no real multi-camera route, use the injected vehicle for beats 6–7, say on camera that it is an injected demonstration vehicle, and keep the `demo` badge in shot. Never let an injected row pass as a live read.

## Video 2 — the government-provided feed (≤ 3 min)

| # | Beat | Shows |
|---|---|---|
| 1 | **Onboarding** | Fetch the catalogue → cameras appear in the registry → onto the map. Say: "the catalogue is the contract; nothing is hard-coded" |
| 2 | **Viewing** | Live tiles from the provided feeds, 4-up, with department labels |
| 3 | **ANPR** | Real plate reads on the daylight camera: crops, confidences, timestamps, all `live` |
| 4 | **Vehicle and person detection** | The object counts per class per camera on Command, and the person count beside them |
| 5 | **Intrusion or line crossing** | A zone drawn on a camera and the event it produced, with its alert |
| 6 | **The report** | The exported detection report opened on screen — detected vehicles and plates with timestamps |

## Rules for both (unchanged)

- Record several takes; keep the best.
- Have fallback footage of every component working, recorded earlier. Feeds go down; footage does not.
- Nothing on screen may show a credential — address bar, terminal scrollback, log tail, and now the login page: never type a real password on camera where the keystrokes or a password manager could be read.
- No mock-ups, no animations, no simulated interfaces.
- Say measured numbers only where they were measured.

---

*History: the 15 Sep run sheet, verbatim, superseded by the two tables above.*

# 05 — Demo script (run sheet for both videos)

Max 2–3 minutes each. Rehearse with a timer. Narrate over a screen recording; no slides inside the video.

---

## Video 1 — own feed

| # | Beat | Says | Shows |
|---|---|---|---|
| 1 | **The wall** | "Cameras from five departments, one interface, live." | Live grid, department labels visible |
| 2 | **The map** | "Every camera registered with its department, location, codec and health." | GIS map, colour-coded by department; click one pin for its full record |
| 3 | **Nothing is recorded** | "This video is relayed, not stored. Watching is not the same as storing." | Say it plainly over the live wall |
| 4 | **The watchlist** | "A representative watchlist — stolen vehicles, wanted persons." | The watchlist table |
| 5 | **The hit** | "A watchlisted vehicle passes camera 4." | Alert appears live with plate, crop, camera, timestamp |
| 6 | **The route** | "Where else has it been?" | Click through → map draws the route, timeline beside it |
| 7 | **Across departments** | "This vehicle crossed Police, GSRTC and Municipal cameras. One platform, three departments." | The `departments_crossed` header |
| 8 | **The report** | "Exported with timestamps." | The detection report |

If Pipeline 3 was built, insert after 6: *"Model 2 stops at the metadata. Ours keeps the evidence."* Click the alert → a 62-second clip opens, starting 30 seconds **before** the vehicle appeared. Then show the buffer directory flat at fixed size, and say the number: **2.2 GB a day instead of 1,600, for the same capability.**

**Known risk:** the post-event wait means roughly 15 seconds of dead air after the alert. Fill it by narrating the audit trail — event id, trigger reason, SHA-256 — which is the chain-of-custody argument anyway.

---

## Video 2 — Government-provided feed

Required content: onboarding the provided feeds, successful live/recorded viewing, video-analytics output on that feed, **plus the output report showing detected vehicles and number plates with timestamps.**

| # | Beat | Shows |
|---|---|---|
| 1 | **Onboarding** | Fetch the catalogue → cameras appear in the registry → onto the map. Say: "the catalogue is the contract; nothing is hard-coded." |
| 2 | **Viewing** | Live tiles playing from the provided feeds |
| 3 | **Analytics** | ANPR running: detections, plates read, crops, timestamps |
| 4 | **The report** | Export and open it on screen — detected vehicles and plates with timestamps |

---

## Rules for both

- **Record several takes.** Keep the best.
- **Have fallback footage of each component working in isolation**, recorded earlier. Feeds go down. Footage does not.
- Nothing on screen may show a credential. Check the address bar, terminal scrollback and any log tail before recording.
- No mock-ups, no animations, no simulated interfaces. Stated four separate ways in the rules: without an operational backend it will not be considered.
- Say measured numbers only where they were measured. If something is modelled, say "we model" — a jury that catches one invented figure discounts everything else.
