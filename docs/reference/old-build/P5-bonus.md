# P5 — Bonus analytics  (budget: 2 hours) — ONLY IF GATE C PASSED

If GATE C failed, this phase does not exist. Go to P6.

**Why it is worth two hours when it passed:** Evaluation Area 5 reads *"Quality and usefulness of ANPR, vehicle or person detection, **intrusion detection, object detection**, timestamps, and output reports."* An ANPR-only submission is scored against a rubric that explicitly names four analytics. The detector built in P2 already produces three of them — they are simply not surfaced yet.

---

## P5.1 — Surface object detection  (1 hour)

**Do:** the detector already classifies person, car, truck, bus, motorcycle, bag. Stop discarding those results behind ANPR. Write them to `events` with `event_type='object_detected'`. Add a UI panel showing counts per class per camera over time, and include them in the detection report.

**Acceptance:** the dashboard shows live object counts per camera and the report includes them.

**Value per hour spent: high.** This is exposing work already done.

---

## P5.2 — Intrusion detection  (1 hour)

**Do:** using `zones_json` from `docs/03-data-contracts.md` §5:
- A zone editor — draw a polygon or line on a still frame, save normalised 0–1 coordinates to the camera record
- Zone-entry detection: a tracked object's foot point entering an intrusion polygon
- Line-crossing detection: a track crossing a line in the configured direction
- Write to `events`, fire an alert for high-severity zones

**Acceptance:** define a zone on one camera, have a person or vehicle enter it, and see the event fire.

---

## P5.3 — Pipeline 3 evidence capture  — ONLY if genuinely ahead

Already designed and validated end to end; see `reference/claude_model-02-1-event-triggered-evidence.md` and `reference/claude_model-02-1-promote.py`. Roughly one engineering day including debugging, which is why it is last.

**Do, if and only if P1–P4 are complete and stable:**
- Ring buffer per active camera: `ffmpeg -c copy -f hls -hls_time 2 -hls_list_size 450 -hls_flags delete_segments+program_date_time`
- Promote step on watchlist match: select segments overlapping `[t−30s, t+30s]`, **copy** (never move), concat with `-c copy`, SHA-256, audit row
- Link the clip from the alert detail view

**Acceptance:** an alert produces a playable ~60 s clip starting 30 s before the vehicle appeared, the buffer directory stays flat in size, and the audit row records event id, trigger reason and hash.

**If there is any doubt about time: skip this and describe it in the HLD.** It is already validated with real measurements — 0.54% of one core, 61 segments flat at 46 MB, 13.4 s promotion latency, zero decode errors on the clip. A validated design described honestly scores; a half-built one on demo day does not.

---

**Exit P5 when:** object detection and intrusion detection appear in the UI and in the report, or the phase was cut. Either way, record it.
