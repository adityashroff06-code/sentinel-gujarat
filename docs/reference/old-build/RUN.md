# RUN — laptop operating guide

Everything here runs on **your laptop** (Windows, GTX 1650). The cloud dev
box built and validated all of this, but two things must happen on your
machine: the CDN doesn't rate-limit a single user, and the GPU makes the
detector ~10× faster.

## Shortest path: `python launch.py`

Open a terminal (cmd, PowerShell or Anaconda Prompt) in the repo folder and run:

```bat
python launch.py check      :: what is present / missing (nothing is changed)
python launch.py            :: first run: ffmpeg -> .venv -> pip -> YOLOX -> probe -> dashboard
python launch.py demo       :: inject the demo hero vehicle (route + alerts + report)
python launch.py demo-clear :: remove ONLY the demo rows (live reads untouched)
python launch.py harvest    :: §2 + §3 (plate harvest + watchlist)
python launch.py stop
```

### Demo vehicle for a guaranteed end-to-end walkthrough

Live ANPR reads real plates off the daytime cameras (e.g. cam06), but a
*cross-camera* route needs the same vehicle on several cameras, which only
the CDN's shared-timeline recordings can supply and the CDN rate-limits a
busy IP. So for a reliable demo run `python launch.py demo` after the
platform is up: it injects one watchlisted hero vehicle (**GJ01AB1234**)
through the **real** pipeline (same `record_sighting` + `match_sighting` the
live workers use), producing a genuine 3-camera / 3-department route, live
alerts with crops, and report rows. It sits alongside the live reads; remove
it any time with `python launch.py demo-clear`. Demo steps:

1. `python launch.py` — wait for the dashboard; the Live Wall shows real feeds.
2. `python launch.py demo` — in a second terminal.
3. Dashboard → 4 live alerts appear; **Route** → type `GJ01AB1234` → the
   map draws the route with a timeline; **Search**/**Reports** show the reads.

**Venue note:** the map basemap tiles load from OpenStreetMap over the
internet. Without internet the camera **pins and the route polyline still
render** (on a dark background) — only the street basemap is missing.

The first start is self-contained: if `ffmpeg`/`ffprobe` are not on PATH it
downloads a portable build (~190 MB, one time) into `tools/ffmpeg/` and uses
it from there; then it creates `.venv`, installs `requirements.txt`, fetches
YOLOX-S, probes the grid, seeds the registry and opens
http://localhost:8000/dashboard. Later starts skip everything already done.
Any Python 3.10–3.13 works (Anaconda's 3.13 included — all wheels exist).

The `.bat` files (`START_SENTINEL`, `HARVEST`, `STOP_SENTINEL`, `CHECK_SETUP`)
are one-line wrappers around the same commands for double-clicking. If a
double-click does nothing, `.bat` association is broken on that machine —
use the `python launch.py` form; it is the same code path.

`python launch.py status` prints what the running platform has done (workers,
frames/fps per camera, sightings, top plates) — paste that output when reporting.

**Transport on the laptop (measured 14 Sep):** from your network RTSP works for
27/30 cameras (live 1080p/720p H.264, TCP) and the CDN's HLS times out, so the
registry marks them `transport=rtsp` and each worker pulls its camera ONCE over
RTSP via ffmpeg, teeing a stream-copied local HLS window (`data/hls/<cam>/`)
that the Live Wall plays. Cameras without a worker fall back to the CDN relay.

## 0. One-time setup (manual equivalent)

```bat
cd C:\Users\Sai\Downloads\Sentinel_Repo
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m src.tools.fetch_models          :: downloads YOLOX-S (Apache-2.0)
```

- `ffmpeg` and `ffprobe` must be on PATH (`ffmpeg -version` to check) — or let
  `launch.py` fetch the portable copy.
- GPU (optional but wanted): `pip install onnxruntime-directml` so the
  detector uses the GTX 1650. Without it, it runs on CPU — still works.
- `.env` already has your credentials (gitignored — never commit it).

## 1. Probe + registry (refresh on your IP)

```bat
python -m src.tools.probe            :: catalogue -> registry, transports
python -m src.tools.seed_registry    :: departments/coords/tiers (disclosed)
python -m src.tools.measure          :: real fps + bitrate per camera
```

## 2. Harvest sightings — the GATE B step

This walks each camera across its ~12 h recording, runs the full ANPR
pipeline, and writes deduped sightings on a shared timeline. **Daylight is
at the end of each recording** (positions ~0.8–1.0), so those segments read
best.

```bat
:: start with the active tier; --per-camera controls how many segments
python -m src.tools.harvest --active --sweep --per-camera 400
```

Read its summary: **per-camera new-plate counts** and **"plates seen on
>=2 cameras (routeable)"**. That tells us which 3–4 cameras actually yield
plates (your chosen strategy) and whether a real vehicle crosses several.

- If counts are low, raise `--per-camera` or add `--fps-stride 10` (denser
  frame sampling), and/or target specific cameras:
  `--cameras cam01,cam05,cam08,cam10`.
- Pick one real vehicle whose plate reads cleanly on several cameras — that
  is the demo/eval "hero" vehicle (the route safety net). Tell me the plate.

## 3. Watchlist (seed with real observed plates)

```bat
python -m src.tools.seed_watchlist --from-sightings 6
```

Record in STATUS.md which plates came from observation (the tool prints
them).

## 4. Run the platform (demo recipe)

**Pick the playback window first.** The recordings loop (~12 h, starting
~21:00 at night). The whole platform advances on ONE shared timeline
(`src/ingest/timeline.py`), and `SENTINEL_PLAYBACK_OFFSET_S` in `.env`
shifts that "live" window. For daylight footage set it so the live edge
lands ~9–11 h into the recording:

```
SENTINEL_PLAYBACK_OFFSET_S=34000     # ≈ 09:26 recording time (daylight)
```
(Any value works; the relay, the workers and the harvest all use the same
offset, so the wall, the reads and the route stay in sync. Restart the API
and the workers after changing it.)


```bat
:: terminal 1 — API + HLS relay + alert SSE + health checker (+ serves the built UI)
cd ui && npm install && npm run build && cd ..
uvicorn src.api.main:app --port 8000            :: open http://localhost:8000

:: terminal 2 — live ANPR workers (active cameras), tracker, zones, matcher, alerts
python -m src.ingest.worker
```
(Dev alternative for the UI: `cd ui && npm run dev` → http://localhost:5173,
which proxies /api to :8000.)

**Screens** — record the video on **Command** (`/dashboard`): 4 live
tiles, GIS mini-map, live alert feed, latest plate reads, object counts,
worker status. Then: **Map** (30 cameras by department, click a pin),
**Live Wall** (1/4/9 grid), **Search** (plate → sightings with crops),
**Route** (plate → numbered route, departments crossed, gaps), **Alerts**
(live SSE, acknowledge), **Zones** (draw an intrusion polygon or crossing
line on a still — workers pick it up on their next restart), **Reports**
(detection report CSV/HTML, gap-analysis, OpenAPI).

**Demo flow that matches 05-demo-script.md:** Command → Map → "nothing is
recorded" over the wall → Alerts/watchlist → wait for a hit (or open Route
for the hero plate) → Route with departments crossed → Reports.

## 5. Measurements (P2.7 — real numbers for the HLD)

Let the worker run **10 continuous minutes**, then read its stats
(live on the Command screen and at `/api/workers`, from data/worker_stats.json). Record in STATUS.md:
sustained fps/camera, vehicles/camera/min, peak VRAM/RAM, motion-skip
rate, plate-read rate. These are the only "measured" numbers the HLD may
cite; everything else is labelled a model.

## 6. Reports (named deliverables)

```bat
python -m src.tools.report gap           :: deliverables/gap-analysis-report.html
python -m src.tools.report detections    :: deliverables/detection-report.{csv,html}
python -m src.tools.export_openapi       :: deliverables/registry-api.json
```

Open each HTML and Ctrl-P → Save as PDF for the submission.

## Notes

- `data/` (DB, crops) and `.env` are gitignored. `data/camera_seed.csv` is
  committed and its assignment is disclosed in the submission.
- If a camera 403s intermittently, that's the CDN's limiter — the code
  retries with backoff. It won't ban a single laptop user the way it
  banned the shared cloud IP.
