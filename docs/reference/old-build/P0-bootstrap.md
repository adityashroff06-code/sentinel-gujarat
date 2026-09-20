# P0 — Bootstrap & probe  (budget: 1 hour)

**Purpose:** answer the three questions every downstream design choice depends on, before writing any of that code.

1. Does RTSP reach us from here, or are we HLS-only?
2. What does the catalogue actually contain — specifically, **does it carry department and coordinates?**
3. How many cameras are live, and what is the codec / resolution / fps / bitrate mix?

---

## P0.1 — Project skeleton

**Do:**
- Create the directory layout from `docs/03-data-contracts.md` §8.
- `requirements.txt`: `fastapi`, `uvicorn[standard]`, `opencv-python`, `numpy`, `python-dotenv`, `httpx`, `pydantic`, `Pillow`.
- `src/config.py` — load every variable from `.env.example` with documented defaults. Expose `masked(url)` which replaces credentials with `<email>`/`***` before any display or log.
- `src/db.py` — connect with WAL + `foreign_keys=ON`, create every table in `docs/03-data-contracts.md` verbatim.
- Logging configured from `SENTINEL_LOG_LEVEL`.

**Acceptance:** `python -c "from src.db import init; init()"` creates `data/sentinel.db` with all six tables. `sqlite3 data/sentinel.db ".schema"` matches the contract exactly, field for field.

---

## P0.2 — Probe the grid

**Do:**
- Port `reference/claude_probe_cameras.py` to `src/tools/probe.py`. Keep its structure; adapt it to `src/config.py` and the registry schema in the data contract.
- It must fetch `cameras.json`, dump the raw response to `data/cameras_raw.json`, probe every camera on both HLS and RTSP, measure real delivered fps by counting frames over a wall-clock window, and write the registry.
- **Every printed line must be credential-masked.**

**Acceptance:** run it. `data/cameras_raw.json` exists, the `cameras` table has one row per catalogue entry, and the summary prints live count, per-transport reachability, codec mix, resolution mix and mean bitrate.

**Then record in STATUS.md:** every row of the Key Measurements table that P0.2 can fill.

---

## P0.3 — GATE A: inspect the raw catalogue by hand

**Do:** open `data/cameras_raw.json` and answer, in STATUS.md:

- Does each camera carry a **department**? Which values?
- Does each carry **lat/lon** or any location field?
- What other fields exist that we are not yet using?

**If department and coordinates are present:** map them into the registry. The GIS map is real data — say so in the submission.

**If absent:** create `data/camera_seed.csv` with columns `camera_id,department,location_name,lat,lon`. Assign plausible Gujarat coordinates spread across a city so routes are visible, distribute cameras across the five named departments (Health, Police, GSRTC, Panchayat, Municipal), and import it. **This assignment is disclosed in the submission** — never presented as sandbox-supplied. Record the decision in STATUS.md.

**Acceptance:** every camera in the registry has a department and coordinates, and STATUS.md records which of the two paths was taken.

---

## P0.4 — Transport decision

**Do:** from P0.2's results, set each camera's `transport` column and record GATE A in STATUS.md.

- RTSP reachable → full design available; WHEP worth testing for the live wall.
- RTSP blocked, HLS working → HLS-only. Drop WHEP from the demo, keep it in the HLD as the production path, and state the constraint plainly rather than implying otherwise.
- Neither → stop. Record it and contact the organisers.

**Acceptance:** GATE A row filled in STATUS.md with the decision and its rationale.

---

## P0.5 — Tiering

**Do:** set `fps_tier = 'active'` on the best `SENTINEL_ACTIVE_CAMERAS` cameras. Choose by: live status, resolution not excessive (lower resolution decodes cheaper), and — if the catalogue shows it — spread across **different departments**, because a route crossing departments is direct evidence for the central claim. Everything else stays `registered`.

**Acceptance:** the count of `fps_tier='active'` equals `SENTINEL_ACTIVE_CAMERAS`, and the selected cameras span at least three departments if the data allows.

---

**Exit P0 when:** the registry is populated, GATE A is recorded, the active set is chosen, and the measurements table in STATUS.md is filled as far as P0 can fill it.
