# Runbook — onboarding a fresh camera grid (and the local demo feeds)

*Written in S3.7 (24 Sep 2026, decisions F45, F52, F55). Audience: Adi, on the
laptop, when the organisers hand over a new grid (evaluation promises ~50
cameras) — or when the second system's own recordings come online. Every
command runs from the repo root in PowerShell; `python` is always
`.venv\Scripts\python`.*

The catalogue is the contract, the URL pattern is not. The adapter
(`backend/tools/probe.py::fetch_catalogue`) accepts **both** published
shapes — the sandbox's `cameras.json` (`{id, name}`) and the Integrator's
Guide's `GET /api/ingest` (id, location, codec, live status, stream
properties, RTSP/WHEP/HLS URLs) — and normalises either to the registry
columns. Whatever the catalogue supplies is used **verbatim**;
`data/camera_seed.csv` fills only what it does not carry. No code change is
needed for a new grid.

## Before the five commands: point `.env` at the new grid

Adi edits `.env` (sessions cannot read or write it):

- `SENTINEL_CATALOGUE_URL=<host>/api/ingest` — the new catalogue. Empty
  keeps the sandbox default (the CDN's `/cameras.json`). A local JSON file
  path also works (an offline copy; the seeder reads it directly).
- `SENTINEL_STREAM_IP` / `SENTINEL_RTSP_PORT` / `SENTINEL_WHEP_PORT` /
  `SENTINEL_CDN` — the new grid's endpoints. The probe's RTSP leg builds
  URLs from these; catalogue-supplied URLs are stored on the row
  (credential-scrubbed to `<email>:<password>@` placeholders — no stored
  URL ever carries a credential).
- `SENTINEL_EMAIL` / `SENTINEL_PASSWORD` if the new grid issues new
  credentials.

Known limit: the probe's HLS leg goes through the CDN session (cookie
login, sandbox-shaped). On a grid with a different HLS scheme the HLS
column of the probe may read failed even when HLS works — the live wall
relay (step 5) is the real HLS verification.

## The five commands, in order

### 1. Probe — fetch the catalogue, measure what answers

```powershell
.venv\Scripts\python -m backend.tools.probe
```

**Check after it:**
- First line: `catalogue: N cameras (<shape> shape) -> cameras_raw.json`.
  Note **which shape** the grid served — it goes in the progress block.
- Summary line: `probe: N cameras — RTSP live X, HLS live Y, 403s Z ->
  probe_results_<date>.json`. X is what the worker can use.
- `data/cameras_raw.json` was rewritten from the new grid. Open it once:
  ids sane (`^[A-Za-z0-9_-]{1,64}$` — anything else was skipped with a
  warning, never repaired), **no credential anywhere** (the writer scrubs
  userinfo; if you see a password, stop and file it as a bug).
- Commit the refreshed `data/cameras_raw.json` and
  `data/probe_results_<date>.json` (the committed 14 Sep evidence file is
  never overwritten).
- Decoder noise (`Could not find ref with POC`, RPS errors) during RTSP
  probing is normal on join (rule 5). A burst of 403s means the CDN rate
  limiter — wait minutes, do not re-run in a loop.

### 2. Seed the registry

```powershell
.venv\Scripts\python -m backend.tools.seed_registry
```

**Check after it:** the printed line
`cameras: N rows, A active across D departments — ACCEPTANCE: PASS|FAIL`.
- N must equal the catalogue's camera count (every catalogue id present,
  none invented — the seed CSV can never add a camera the catalogue does
  not name).
- **On a brand-new grid expect `ACCEPTANCE: FAIL` (exit 1) here** — the
  new ids are not in `data/camera_seed.csv` yet, so nothing is `active`.
  That FAIL is the signal for step 3, not an error.
- Spot-check one row the grid described richly: catalogue-supplied
  department/location/coordinates/codec/URLs must appear **verbatim**;
  seed values only where the catalogue was silent.

### 3. Check (and, on a new grid, assign) the active tier

The automatic pick was cut (F55): the tier is assigned by hand in
`data/camera_seed.csv` (`fps_tier` column — the seed stays the tier ledger
even when the grid publishes its own geography, because the catalogue
never carries a tier). Choose up to `SENTINEL_ACTIVE_CAMERAS` (6) cameras
that were **RTSP-live in step 1**, spread across departments, and — for
the demo route — three of them inside **one geographic cluster** so the
route's speeds stay plausible. Append/edit their CSV rows, re-run step 2,
then verify:

```powershell
.venv\Scripts\python -c "from backend.core import db; con = db.connect(); rows = [tuple(r) for r in con.execute('SELECT camera_id, department, transport, health, fps_tier FROM cameras') if r['fps_tier'] == 'active']; print(*rows, sep=chr(10))"
```

**Check after it:** count `<= SENTINEL_ACTIVE_CAMERAS`; every listed
camera answered RTSP in the probe (the worker only pulls
`transport IN ('rtsp','replay')`); step 2 now prints `ACCEPTANCE: PASS`.
Remember the suspected ~6-per-account RTSP session cap
(`docs/sandbox-findings.md` §3) — the active tier plus nothing else is the
whole pull budget (the wall is served from the worker's tee, never a
second pull).

### 4. Restart the worker

Stop the running supervisor (Ctrl+C in its console, or create the
`data/stop` file), then:

```powershell
.venv\Scripts\python -m ml
```

**Check after it:** `data/logs/` — one `worker started: camNN (rtsp)`
line per active camera; `data/worker_stats.json` updating every 10 s with
frames climbing on every active camera within a minute. Join-time decoder
warnings are logged and non-fatal; a camera that pulls **zero frames**
while others work is the session cap or a dead feed — drop it from the
active tier rather than stalling the set (root §9).

### 5. Verify tiles

With the API up:

```powershell
.venv\Scripts\python -m backend.app
```

then sign in at `http://127.0.0.1:8000/` and open the **Live Wall**.

**Check after it:** every active camera's tile plays moving video (served
from the worker's local HLS tee through the relay — one upstream pull per
camera, always); camera health reads `online`; on daytime road cameras,
sightings begin to arrive within a few minutes. `scripts/smoke_frontend.py`
(S3.3) is the scripted version of this check once the frontend lands.

## When the new grid publishes departments and coordinates of its own

Nothing to do in code — this is the designed case (F45):

- The adapter stores grid-published `department`, `location` and
  coordinates **verbatim**; `apply_seed` only fills columns the catalogue
  left NULL, so the seed can never overwrite the grid's own values.
- **Update the disclosure**: the submission's "geography was assigned for
  demonstration" note applies only to cameras whose geography still comes
  from `data/camera_seed.csv`. Cameras described by the grid itself are no
  longer covered by it — say so per camera set, don't blanket-claim.
- Do **not** copy grid values into `camera_seed.csv` — pointless (they
  lose to the catalogue anyway) and a staleness trap when the grid
  corrects itself. Keep CSV rows for those ids only for `fps_tier`.
- Department spellings outside the five known ones are stored verbatim
  (the catalogue is the contract); expect them to appear as their own
  group in UI filters and the gap analysis.

## The second system: local demo feeds (own recordings)

Adi's 10 recordings (60–90 s, with coordinates) become `local01..local10`
— published over local RTSP and consumed by the **same** worker, relay and
analytics as the sandbox. Own footage only; sandbox footage is never
downloaded (root §8, rule 6). mediamtx binds `127.0.0.1` only (rule 11).

One-time: `.venv\Scripts\python scripts\replay_publish.py --fetch`
(downloads mediamtx, records its SHA-256 in `CHECKSUMS.txt`; verified on
every later start).

**Per feed:**

1. **Pre-transcode once to a ≤ 2 s GOP** so publishing can stream-copy
   (near-zero CPU — what several concurrent feeds need on 4 cores) and
   the worker's HLS tee can cut 2 s segments:

   ```powershell
   & "D:\projects\Sentinel_Repo\tools\ffmpeg\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe" -i IN.mp4 -c:v libx264 -preset veryfast -g 60 -keyint_min 60 -an data\footage\local01_gop2.mp4
   ```

   `-g 60` = 2 s at 30 fps footage; use `-g 50` for 25 fps.

2. **Publish** with the `--copy` mode (input must already carry the ≤ 2 s
   GOP from step 1; without `--copy` it re-encodes at ~one core per feed):

   ```powershell
   .venv\Scripts\python scripts\replay_publish.py --file data\footage\local01_gop2.mp4 --name local01 --copy
   ```

   The CLI runs one mediamtx + one publisher per invocation — for several
   feeds at once use one process per feed on **distinct ports**
   (`--port 8555`, `8556`, …, registering the matching URL below), or
   S3.4's launcher, which imports `start_mediamtx()` / `publish()` and
   multiplexes all ten on one server.

3. **Register** it as the second system's camera, active tier:

   ```powershell
   .venv\Scripts\python -m backend.tools.seed_registry --add local01 Municipal rtsp://127.0.0.1:8554/stream/local01 --tier active
   ```

   `--add` sets id, department, plain-local URL (stored as-is, no
   credentials involved), `transport='rtsp'`, `source='manual'`. For the
   map pins, append a `local01,...` row to `data/camera_seed.csv` with the
   recording's real location and coordinates and `fps_tier,active`, then
   re-run the plain `seed_registry` — the seed fills the coordinates the
   `--add` left NULL and keeps the department `--add` set.

4. **Restart the worker and verify the tile** — steps 4 and 5 above,
   unchanged. Check the loop wrap: the recording loops with a hard scene
   cut; the ingest emits its restart tick and trackers reset (GATE A'
   behaviour) — a tile that freezes at the wrap is a bug, not a feed
   problem. Mind the budget: sandbox active + local feeds together stay
   within `SENTINEL_ACTIVE_CAMERAS`.

Rollback for any step: the registry is idempotent — fix the input
(`.env`, CSV, catalogue) and re-run the same command; nothing is
double-inserted. A wrong `--add` is corrected by re-running `--add` with
the right values (same id upserts).
