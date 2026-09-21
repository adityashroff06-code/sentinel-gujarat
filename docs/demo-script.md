> **Editor's note (fresh build):** copied verbatim from the previous build's `05-demo-script.md`. The screens it names exist in the fresh build under the same names except Command (`Dashboard`); the walkthrough the videos follow is task S3.4, the recording task is S5.4.

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
