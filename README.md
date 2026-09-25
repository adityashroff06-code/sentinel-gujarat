# Sentinel — Integrated Video Management & Analytics Platform

Entry to the [Gujarat Police Innovation Challenge 2026](https://sentinel.gujarat.gov.in/) (Home Department / SCRB).

Sentinel is one platform over the departments' CCTV systems: a **camera registry with a GIS view** (Model 1), **unified live viewing and metadata analytics** across different camera systems (Model 2) — continuous ANPR, vehicle and person detection, intrusion zones and line crossing — a **watchlist with real-time alerts**, and the scored capability: **a vehicle's complete, timestamped, location-wise route from a single registration number**.

It is a working system, not a mock-up: every screen reads the operational backend, and the analysed cameras are pulled live from the organisers' sandbox grid.

![Sentinel workflow and integration diagram](deliverables/Sentinel-Workflow-Integration-Diagram.png)

One pull per camera feeds the pipelines over the Model 1 registry: **Pipeline 1** relays live video (relayed, never recorded), **Pipeline 2** runs ANPR and analytics at the node and stores only text rows and small plate crops, and **Pipeline 3** (evidence clips on a watchlist match) is designed and validated separately — **not built in the demo**. The full design is the [technical proposal (HLD)](deliverables/HLD.md).

## The hosted demo

The URL of the hosted platform and the evaluator credentials are on the **submission form**; they are never written into this repository. Every page needs a sign-in except the login page itself. Roles: `viewer`, `evaluator`, `admin`.

**A five-minute walkthrough**

1. **Command** (the first screen) — the *Start here* panel says what the platform is, which plates to try, where every feed comes from, and which rows are demonstration data.
2. **Route** — type `GJ01AB1234`: the labelled demonstration vehicle's route across three cameras in three departments, with timestamps, speeds and the OCR near-miss it still matched. Every stop carries a `DEMO` badge.
3. **Search** — ANPR search is OCR-tolerant (exact, OCR look-alikes such as 8↔B and 0↔O, then one character away). Try a plate from *Plates to try → Most read live*: those are real reads from the live pipeline, marked `LIVE`, with their crops.
4. **Live Wall** — every camera in one viewer: the analysed sandbox cameras (`LIVE · RTSP`), the other sandbox cameras from the organisers' recording (`CDN RECORDING`), and 28 local feeds from our own media server (`LOCAL FEED`) — two different systems, one relay.
5. **Map** — the GIS console: departments, clusters, fields of view, activity and coverage gaps; click a camera for its registry record.
6. **Alerts**, **Watchlist**, **Zones**, **Reports** — the alert stream (Server-Sent Events), the watchlist that drives it, the zone editor (a crossing line on cam06 fired 53 line-crossing events on the live feed), and the exported detection report with timestamps and a provenance column.

Use **Google Chrome**: six sandbox cameras (among them cam06, the analysed camera that reads plates) are H.265, which Chrome decodes and some Edge installations do not.

## What is demonstration data — disclosed

- **Seeded geography.** The organisers' catalogue carries no department or coordinates. The 30 sandbox cameras' departments and coordinates are seeded demonstration assignments (`data/camera_seed.csv`), stated in every export.
- **The labelled demonstration vehicle.** `GJ01AB1234` is injected through the real sighting → match → alert path with `provenance='demo'`. It is badged `DEMO` on every screen, on its plate crops and in every export; it never passes as a live read.
- **The tiered active set.** Five sandbox cameras are analysed continuously (cam06, cam09, cam26, cam27, cam28), within the laptop's 4 GB GPU and the gateway's session limit; the other 25 are registered and viewed.
- **The local feeds.** `local01`–`local28` are 28 stock traffic clips, looped on our own media server at seeded Ahmedabad/Gandhinagar coordinates. They are not sandbox footage and were not filmed by the team; each registry row says so. They are view-only on the platform database, because a looped clip analysed there would count one vehicle once per loop. Reads kept from `local01`'s analysed run in the 24 Sep end-to-end walkthrough carry that camera id: they are real reads of a looped clip, so a vehicle there can be counted once per pass.
- **Not built:** Pipeline 3 evidence clips, Model 3 VMS federation and facial recognition are described in the HLD, not built.

## Documents

| Deliverable | File |
|---|---|
| Solution presentation | [`deliverables/Sentinel-Solution-Presentation.pdf`](deliverables/Sentinel-Solution-Presentation.pdf) (and `.pptx`) |
| Technical proposal (HLD) | [`deliverables/HLD.pdf`](deliverables/HLD.pdf) (source [`HLD.md`](deliverables/HLD.md)) |
| Workflow and integration diagram | [`deliverables/Sentinel-Workflow-Integration-Diagram.pdf`](deliverables/Sentinel-Workflow-Integration-Diagram.pdf) (and `.svg`, `.png`) |
| Registry API documentation (OpenAPI 3.1) | [`deliverables/registry-api.json`](deliverables/registry-api.json) |
| Sample onboarded camera dataset | [`deliverables/sample-camera-dataset.csv`](deliverables/sample-camera-dataset.csv) |
| Gap-analysis report (Model 1) | [`deliverables/gap-analysis-report.html`](deliverables/gap-analysis-report.html) |
| Detection report with timestamps | [`deliverables/detection-report.html`](deliverables/detection-report.html) (and `.csv`) |
| Departmental systems unaffected (Model 2 note) | [`deliverables/departmental-systems-unaffected.md`](deliverables/departmental-systems-unaffected.md) |
| Built frontend | [`deliverables/frontend-dist.zip`](deliverables/frontend-dist.zip) |

Figures in the documents are labelled: `[measured]` for the six figures from the 10-minute live run on the laptop (25 Sep 2026, HLD §7.1), `[model]` for arithmetic from stated assumptions, `[estimate]` for judgement.

## Running it yourself

**Needs:** Windows 10/11 · Python 3.13 · Node 20.19+ (first start only, to build the frontend) · 8 GB RAM · an NVIDIA GPU is used through DirectML when present, else the detector runs on the CPU · a sandbox portal account.

```
copy .env.example .env          # fill in SENTINEL_EMAIL / SENTINEL_PASSWORD and the two API keys
python launch.py start          # doctor -> venv -> ffmpeg -> models -> probe -> seeds
                                #   -> frontend -> local feeds -> API + worker -> browser
.venv\Scripts\python -m backend.tools.users add <name> --role admin   # prompts for the password
```

Then open `http://127.0.0.1:8000/` and sign in. `python launch.py status` answers "is it up" (workers, database counts, `:8000`, `feeds N/28`); `python launch.py stop` stops everything it started. `python launch.py demo` injects the labelled demonstration vehicle and `demo-clear` removes exactly those rows. Credentials are read from the environment only and are never logged, stored or shown unmasked.

**Troubleshooting**

| Symptom | What to do |
|---|---|
| `status` shows fewer than `feeds: 28/28` | `python launch.py replay-start` restarts the local feeds |
| A tile says the browser cannot decode HEVC | Open the page in Google Chrome (H.265 camera) |
| Tiles say *Organisers' CDN not answering* or *Feed reconnecting* | The organisers' sandbox is down or rate-limiting; the relay backs off and the tiles recover on their own, and the local feeds keep playing |
| A tile says *Local feed offline* | `python launch.py replay-start` |
| A tile says *Too many open streams — slowing down* | Use a smaller grid; the relay is rate-limiting this browser |
| *Session expired — sign in again* | Sessions last 8 hours; sign in again |
| The Live Wall at 16-up stalls sandbox tiles | Use the default 4-up grid; the organisers' CDN rate-limits bursts |
| Sign-in refused after five failures | Further attempts for that name or address are locked for 15 minutes, by design |
| Anything else | Logs are in `data/logs/` (one rotating file per process) |

## Repository

`backend/` (FastAPI + SQLite: registry, analytics API, auth, relay, reports) · `ml/` (ingest, motion gate, YOLOX-S detector, tracker, PaddleOCR cascade, watchlist matching, zones) · `frontend/` (React, Leaflet, hls.js) · `tests/` (pytest) · `scripts/` · `docs/` (design record, decisions, plan and build log — how the build sessions run is in [`docs/sessions.md`](docs/sessions.md)).

Licence: Apache-2.0 (`LICENSE`). Never commit `.env`.
