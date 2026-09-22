> **Editor's note (fresh build):** copied verbatim from the previous build's `05-demo-script.md`. The screens it names exist in the fresh build under the same names except Command (`Dashboard`); the walkthrough the videos follow is task S3.4, the recording task is S5.4.

# Demo run sheets — v2.3 (22 Sep 2026)

**These two tables are the ones to record.** They replace the 15 Sep run sheet kept below, which missed what the portal actually asks for: onboarding is the **first** thing the own-feed video must show, and the government-feed video must show more analytics than ANPR. Both still run to 2–3 minutes, rehearsed with a timer, narrated over a screen recording, with no slides inside the video.

Sources: portal Step 5 ("Onboarding and processing of live or recorded CCTV feeds… AI-powered detection and analytics… correlation… automatic generation of real-time alerts"); FAQ 31 (the government-feed video shows "onboarding, viewing, and analytics output (ANPR, vehicle/person/intrusion/object detection)"); decision F43 (the hit and the route are real).

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
