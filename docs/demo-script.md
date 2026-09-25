> **Editor's note (fresh build):** copied verbatim from the previous build's `05-demo-script.md`. The screens it names exist in the fresh build under the same names except Command (`Dashboard`); the walkthrough the videos follow is task S3.4, the recording task is S5.4.

# Demo run sheets — v2.6 (25 Sep 2026, decision F70) — **record these**

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
