# frontend/ — layer rules

React **18.3.1** + Vite 6 (`npm create vite@6`, Node **20.19+**), `react-router-dom@6`, Leaflet 1.9.4 + `react-leaflet@4.2.1` (BSD-2), `hls.js@1` (Apache-2.0) — decision F28. Served in production by the API from the built `dist/` (ignored by git; zipped into `deliverables/` on the submission tag, F30); in development Vite on `:5173` proxies `/api` and `/crops` to `:8000`. Reads the root `CLAUDE.md` first; these rules add to it.

## Screens (all required)

**Login** (username + password; one unspecific error; the header then shows the signed-in user, the role and sign-out) · Command (dashboard: a **Start here** panel for evaluators, live tiles, mini-map, alert feed, latest reads, object and person counts, worker health, a **feed-status strip**) · Map (GIS) · Live Wall · Search (filters include vehicle class and provenance) · Route · Alerts · **Watchlist** (list, add, remove) · **Cameras** (registry table, add-camera form, CSV import with per-row accept/reject, edit) · Zones · Reports. The last two bold screens did not exist in the previous build although their APIs did — Model 1 requires onboarding to be *demonstrated*, and the demo script shows the watchlist table.

## Rules that bite this layer

- **Only visible tiles hold an open stream.** Mount a player on view, `destroy()` it on hide; verify in the network panel that paging a 4-tile wall stops the previous four. Tiles show camera id, department and a live indicator; the grid offers 1/4/9.
- **Pins are coloured by department** (Police, GSRTC, Municipal, Panchayat, Health, Unknown — one shared palette), health by opacity; filters actually filter; pin click opens the full record. Route: numbered pins in time order, polyline **dashed across gaps**, a timeline with crops, and a header with first/last seen, duration, distance, cameras and **departments crossed, prominent**; fuzzy stops visibly marked; suspect stops marked.
- **Alerts** arrive over SSE (`/api/alerts/stream`) newest first, severity-coded for every severity value including `critical`, each with plate, **crop**, camera, department, timestamp, category, match type; acknowledge persists; one click to the route; the list is capped. Zone alerts carry no route link.
- **Times are shown in IST** through one `formatTs()` (`Intl.DateTimeFormat`, `Asia/Kolkata`) — never `slice()` on an ISO string, never raw UTC. Storage stays UTC.
- **No silent failure**: every fetch checks `r.ok`; one shared data layer / poller (not Header and Dashboard polling separately); a connection-status strip that distinguishes "quiet night" from "pipeline dead"; zone save reports the real result.
- **Provenance is visible**: rows labelled `live | harvest | demo | test` in Search, Route, **Alerts** and Reports — a judge must never mistake a seeded row for a live read (decision F46).
- **An evaluator is told what they are looking at** (F46): the **Start here** panel names what to click, which plates to try and which data is demonstration data (seeded geography, the labelled demo vehicle); the **feed-status strip** distinguishes "no traffic on this camera" from "feed down" from "pipeline dead", using `/api/workers` state and last-read times — never a silent blank screen.
- **Auth** (decision F41, task S3.0): there is **no key dialog**. People sign in at `/login`; the `sentinel_session` cookie is same-origin, so every fetch uses `credentials: 'same-origin'` and `<img>` crops, hls.js segments and the `EventSource` alert stream need nothing extra. Any 401 sends the user to `/login`. The role comes from `GET /api/auth/me`, and actions above the role are **hidden, not just refused**: a viewer sees no acknowledge or watchlist buttons, an evaluator sees no user administration or tier edits.
- **Offline venue**: Leaflet CSS bundled, not from a CDN; basemap tiles need internet (state it in the UI when tiles fail); pins and route render regardless. OSM attribution stays on (ODbL). No `leaflet.offline` pre-seeding.
- **Nothing on screen may show a credential** — check every address bar, tooltip and error toast before a screen is recorded.
- Plates in URLs are `encodeURIComponent`-ed; navigation uses router `<Link>`s.

## Port and polish (v2.5 — decisions F52, F53)

- **Port first.** Start from the previous build's `ui/src` — the same stack (React 18.3.1, react-leaflet 4.2.1, hls.js 1, Leaflet 1.9.4; only Vite moves 5 → 6). Rewire every call to `docs/api.md` and the session cookie, and fix D13 on the way (IST, `r.ok`, the `critical` severity, the zone-save result). Name every ported file in the progress block.
- **One token sheet**, `src/styles/tokens.css`: surface layers, text, the six department colours, severity colours, provenance colours, a spacing scale, radii, a type scale, shadows, motion durations. No colour or size literal outside it. **One theme: dark, control room.**
- **Type:** the system UI font stack (no web-font download — the venue may be offline); tabular numerals for times and counts; plates in a monospace face, always upper case.
- **Every screen has four designed states:** loading (a skeleton, not a lone spinner), empty (says why and what to do next), error (the status strip plus an in-place message) and data. Never a blank screen.
- **Five hero screens get the design pass (S3.3b): Login, Command, Live Wall, Route, Search/Reports.** Command reads in five seconds at 1920×1080 — the video frame. Route is the scored moment: its header (plate, first and last seen, duration, distance, cameras, departments crossed) carries the largest type on the page. A new alert animates in once (≤ 200 ms) and never loops. Provenance badges stay legible at video resolution.
- **Layout:** no horizontal scroll at 1366×768 (the laptop, and likely a judge's screen) or 1920×1080 (the videos, a wall); the Live Wall fills the viewport.
- **Accessibility basics:** text contrast ≥ 4.5:1, a visible keyboard focus, a label on every input, nothing said by colour alone (severity carries a word, a pin's popup names its department).
- **No new runtime dependency** without a row in `docs/decisions.md` saying what it costs (bundle size, licence). No UI kit, no CSS framework, no chart library for a handful of counters — CSS and SVG do it.
- **Review gate before every commit (F53):** `npm --prefix frontend run build` and `run lint` clean, the Playwright smoke green, the pytest suite green, a code review at high effort and `/security-review`, every finding fixed or answered in the progress block. The progress block names the skills that actually ran.

## Package layout (decision F12)

Vite + React in `frontend/` — `src/lib/{api,time,poll}.js`, `src/styles/tokens.css`, `src/components/{Shell,Header,StatusStrip,LoginForm,DeptLegend,Tile,FitBounds}.jsx`, `src/pages/{Login,Command,Map,LiveWall,Search,Route,Alerts,Watchlist,Cameras,Zones,Reports}.jsx`. `npm --prefix frontend run dev` (port 5173, proxies `/api` to 8000) and `npm --prefix frontend run build` → `frontend/dist`, served by the API.

## What the previous build did here (the port source, F52 — read-only)

`D:\projects\Sentinel_Repo\ui\src\` (in a cloud session, a read-only clone of `github.com/adityashroff06-code/Sentinel_Repo`) — `api.js` (thin client + `DEPT_COLORS`), `main.jsx` (nav + routes), `components/{Header,Tile,FitBounds}.jsx`, `pages/{Dashboard,MapView,LiveWall,Search,RouteView,Alerts,Zones,Reports}.jsx`, `styles.css`. Defect D13 in `docs/reference/old-build/P7-enhancements.md` lists its UI faults; §7 E5 has the operator-experience wish list for after the deadline.
