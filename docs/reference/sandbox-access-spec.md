# Sentinel Sandbox — Confirmed Access Spec (ready-to-code)

**Verified live: 13 Sep 2026, ~18:10 IST**, from the logged-in portal at `https://cctv.corp8.cloud/resource` and a live fetch of the camera catalogue. This supersedes the guesses flagged in `probe_cameras.py` comments and the `/api/ingest` mention in `sentinel-hackathon-brief.md` §13.

---

## 1. Access model (confirmed from Integrator's Guide)

| Layer | Endpoint | Auth | Notes |
|---|---|---|---|
| Portal / catalogue / HLS | `https://cctv.corp8.cloud` (CDN, Cloudflare) | **Session cookie** from form POST to `/auth/login` (fields: email, access password) | "Behind your access password"; works from any network |
| RTSP | `rtsp://<email>:<password>@103.250.160.189:8554/stream/<id>` | **Credentials embedded in URL**; email percent-encoded (`@` → `%40`) | Direct public static IP — CDN can't proxy RTP. **Force TCP** (`rtsp_transport;tcp`) |
| WebRTC (WHEP) | `http://<email>:<password>@103.250.160.189:8889/stream/<id>/whep` | Same URL-embedded credentials | Low-latency browser preview |
| Alt stream host | `stream.corp8.cloud` (dedicated non-proxied subdomain) | same | Ports: **8554/TCP, 8889/TCP, 8189/UDP** |

- Only emails on the approved access list can open RTSP/WHEP connections.
- HLS per camera: `https://cctv.corp8.cloud/<id>/index.m3u8`
- Catalogue (THE contract — camera set can change): `GET https://cctv.corp8.cloud/cameras.json` — **confirmed; `/api/ingest` does not exist on this host.**

## 2. Live catalogue snapshot (13 Sep 2026)

`cameras.json` returns a **minimal** array — `{"id","name"}` only. No codec, resolution, fps, coordinates, department, or status fields. All per-camera technical properties must be discovered by probing the streams; locations must be geocoded from the name strings for the GIS layer.

30 cameras, ids `cam01`–`cam30`:

| id | name (location label) |
|---|---|
| cam01 | 01 Chiman bhai Bridge |
| cam02 | 02 Janpath |
| cam03 | 03 O.N.G.C. Office |
| cam04 | 04 Paldi Circle |
| cam05 | 05 Visat teen Rasta |
| cam06 | 06 Timbavadi gate-Junagadh |
| cam07 | 07 hero-showroom-gir-somnath |
| cam08 | 08 majewadi-gate-junagadh |
| cam09 | 09 new-bypass-near-by-circle-junagadh-2 |
| cam10 | 10 char-chowk-road-2-junagadh |
| cam11 | 11 dolatpara-junagadh |
| cam12 | 12 Tri Mandir Adalaj Tollnaka |
| cam13 | 13 CN Vidhyalaya |
| cam14 | 14 Delight RLVD |
| cam15 | 15 Suvidha park |
| cam16 | 16 Visat P2 |
| cam17 | 17 Rajkot Bus Port CCTV |
| cam18 | 18 Rajkot CCTV |
| cam19 | 19 KHAPARIA GRAM PANCHAYAT, TALUKA GANDEVI, DISTRICT NAVSARI |
| cam20 | 20 Mohanpura |
| cam21 | 23 Patan Dethali Char Rasta |
| cam22 | 28 BK Mervada tran Rasta |
| cam23 | 30 kheram |
| cam24 | 33 dehgam |
| cam25 | 34 dhanori |
| cam26 | 35 TANKAL |
| cam27 | 36 bilimora |
| cam28 | 37 bilimora |
| cam29 | 38 bilimora |
| cam30 | Gandhidham Rambaugh p2 |

**Gotcha:** from cam21 onward the number embedded in `name` diverges from the `id` (cam21="23 Patan…", cam22="28 BK Mervada…"). Always key on `id`; treat `name` purely as a location label.

**Geography spread** (for the Model 1 GIS registry): Ahmedabad metro (Chimanbhai Bridge, Janpath, ONGC, Paldi Circle, Visat, CN Vidhyalaya, Suvidha Park, Delight RLVD), Gandhinagar corridor (Adalaj Tollnaka, Dehgam), Junagadh cluster (×6), Gir Somnath, Rajkot (×2 — incl. GSRTC Bus Port), Navsari district (Khaparia Gram Panchayat, Bilimora ×3, Tankal, Dhanori, Kheram, Mohanpura), Patan, Banaskantha-ish (BK Mervada), Gandhidham (Kutch). Matches the brief's "five departments" mix — traffic/police, GSRTC, gram panchayat visible in names.

## 3. Operational constraints (verbatim rules from the guide — treat as scoring rubric)

1. **Force RTSP over TCP** — UDP corrupts across NAT/firewalls; if 8554 blocked, fall back to HLS.
2. **Never trust `CAP_PROP_FPS`** — measure real delivery rate; never derive time metrics from it.
3. **All timing from PTS** (`CAP_PROP_POS_MSEC` / RTP timestamps), never arrival time. On connect the gateway replays a buffered GOP → first ~1–2 s arrives faster than real time. Feed trackers/Kalman filters PTS deltas.
4. **No constant frame rate** — tolerate inter-frame gaps without declaring disconnect.
5. **Reconnect with exponential backoff** ~2 s → cap ~30 s. Feeds are supervised and may restart.
6. **Join-time decoder warnings are normal** (mixed H.264/H.265; `Could not find ref with POC` until first IDR). Log, don't die.
7. **Non-uniform grid** — resolution/codec/fps/bitrate differ per camera; no fixed-shape inference batches.
8. **Each feed loops** (~12 h recording) — hard scene cut at loop point; background models, re-ID galleries, track IDs must recover.
9. **No file download** — build against live capture only.
10. **Consume only; pace load** — each client gets its own stream copy; open only cameras being processed, close finished captures. Never publish to the gateway.

## 4. Implications for the code (deltas vs. current `probe_cameras.py`)

- ✅ Constants confirmed: `CDN=https://cctv.corp8.cloud`, `STREAM_IP=103.250.160.189`, `RTSP_PORT=8554`, `WHEP_PORT=8889`, catalogue at `/cameras.json`, RTSP URL shape with percent-encoded email.
- ⚠️ **Catalogue + HLS auth is a session cookie, not HTTP Basic.** The script's anonymous→Basic fallback for `cameras.json` will likely 302 to `/auth/login`. Add a login step: `POST /auth/login` (form fields `email`, `password` — confirm exact field names from the form) with a cookie jar; reuse the jar for `cameras.json` and HLS (`ffprobe -headers "Cookie: …"`). Alternative: skip HLS in headless code entirely and treat **RTSP-with-credentials as the primary ingestion path** (it needs no cookie).
- ⚠️ Catalogue has no codec/res/fps/location fields → the probe step is *mandatory* to populate the Model 1 registry; add a geocoding pass (name → lat/lon) since coordinates aren't provided.
- `camera_ids()` catalogue-shape handling: real shape is a flat list of `{id,name}` — capture `name` into the registry's `location` column.
- ~50 cameras expected at technical evaluation vs 30 now — the catalogue-is-the-contract rule stands.

## 5. Open items

- [ ] Confirm login form field names for scripted session auth (inspect `POST /auth/login` payload once).
- [ ] Run `probe_cameras.py` (with the cookie fix or RTSP-only) from the dev machine → real codec/res/fps/bitrate mix, RTSP reachability verdict, `registry.db` seed.
- [ ] Geocode the 30 location names for the GIS map.
- [ ] Verify whether RTSP is reachable from the deployment host (decides WebRTC live-view vs HLS-relay design).
