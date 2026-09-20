# P4 — Route reconstruction  (budget: 3 hours) — THE SCORED MOMENT

*"On evaluation day you are handed a vehicle registration number. Your system must identify, trace and present that vehicle's movement across the integrated CCTV network."*

Everything before this phase exists to make this phase possible. If the schedule slips, it slips into here — not out of it.

---

## P4.1 — Route query

**Do:** implement `GET /api/plates/{plate}/route` returning **exactly** the JSON in `docs/03-data-contracts.md` §7. Steps:

1. Normalise the input plate.
2. Gather candidate sightings: exact matches, then fuzzy matches via `plate_match()`, marking each stop's `match_type`.
3. Order by `seen_at`.
4. Collapse consecutive sightings on the same camera within 2 minutes into one stop.
5. Join camera metadata for location, department and coordinates.
6. Compute `elapsed_from_previous_s`, `implied_speed_kmh` (Haversine), `distance_km`, `duration_seconds`, `departments_crossed`.
7. Flag `gaps` where consecutive stops are more than N minutes apart.

**Implied speed is a sanity check, not a claim.** An implausible value means a mis-read plate or a coincidence, and the UI should mark the stop as suspect rather than drawing a confident line through it.

**Acceptance:** a plate with sightings on ≥3 cameras returns an ordered route with correct elapsed times, and the whole response validates against the contract field for field.

---

## P4.2 — Fuzzy candidate handling

**Do:** where OCR produced near-misses of the same vehicle, surface them as **candidate** stops flagged `match_type: "fuzzy"` with their distance — never silently merged into the confident route.

**Acceptance:** a deliberately corrupted plate (one character changed) still appears as a fuzzy candidate on the route, visibly distinguished from exact matches.

---

## P4.3 — Route UI

**Do:** a search box, a plate, and a result:
- Numbered pins on the Leaflet map in time order
- A polyline connecting them — **dashed across flagged gaps**, solid where continuous
- A timeline panel beside the map: each stop with its crop, camera, department, timestamp, elapsed-since-previous
- A header line: *first seen, last seen, total duration, distance, N cameras, M departments*
- Fuzzy stops visibly marked as candidates

**`departments_crossed` prominent.** A route crossing Police → GSRTC → Municipal cameras is direct visual evidence for the central claim that heterogeneous departmental systems have been integrated. Most teams will show fifty anonymous streams; showing the departments turns a dataset property into proof at no cost.

**Acceptance:** typing a plate draws a real route on the map with a readable timeline beside it.

---

## P4.4 — Detection report export (named deliverable)

**Do:** `GET /api/reports/detections` producing CSV and a printable PDF/HTML: **detected vehicles and number plates with timestamps**, filterable by camera, time range and plate. Plus a per-route export for a single vehicle.

This is not optional polish. Deliverable 4 states explicitly: *"screen recording plus an output report showing detected vehicles/number plates with timestamps."*

**Acceptance:** both formats generate from live data and open cleanly. Save samples into `deliverables/`.

---

## P4.5 — GATE C

**Do:** end to end, cold, with somebody else's plate: pick a plate from the sightings table, type it into the UI, and confirm a timestamped, location-wise route across ≥3 cameras appears.

**Pass** → P5, and Pipeline 3 only if time genuinely remains.
**Fail** → cut P5 and Pipeline 3 entirely, without debate. All remaining time goes to P4, then P6.

**Record the decision and a screen capture either way.**

---

**Exit P4 when:** GATE C is recorded and the detection report exports.
