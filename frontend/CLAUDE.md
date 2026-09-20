# frontend/ — layer rules

React 18 + Vite, Leaflet (BSD-2), hls.js (Apache-2.0). Served in production by the API from the built `dist/`; in development Vite on `:5173` proxies `/api` to `:8000`. Reads the root `CLAUDE.md` first; these rules add to it.

## Screens (all required)

Command (dashboard: live tiles, mini-map, alert feed, latest reads, object counts, worker health) · Map (GIS) · Live Wall · Search · Route · Alerts · **Watchlist** (list, add, remove) · **Cameras** (registry table, add-camera form, CSV import with per-row accept/reject, edit) · Zones · Reports. The last two bold screens did not exist in the previous build although their APIs did — Model 1 requires onboarding to be *demonstrated*, and the demo script shows the watchlist table.

## Rules that bite this layer

- **Only visible tiles hold an open stream.** Mount a player on view, `destroy()` it on hide; verify in the network panel that paging a 4-tile wall stops the previous four. Tiles show camera id, department and a live indicator; the grid offers 1/4/9.
- **Pins are coloured by department** (Police, GSRTC, Municipal, Panchayat, Health, Unknown — one shared palette), health by opacity; filters actually filter; pin click opens the full record. Route: numbered pins in time order, polyline **dashed across gaps**, a timeline with crops, and a header with first/last seen, duration, distance, cameras and **departments crossed, prominent**; fuzzy stops visibly marked; suspect stops marked.
- **Alerts** arrive over SSE (`/api/alerts/stream`) newest first, severity-coded for every severity value including `critical`, each with plate, **crop**, camera, department, timestamp, category, match type; acknowledge persists; one click to the route; the list is capped. Zone alerts carry no route link.
- **Times are shown in IST** through one `formatTs()` (`Intl.DateTimeFormat`, `Asia/Kolkata`) — never `slice()` on an ISO string, never raw UTC. Storage stays UTC.
- **No silent failure**: every fetch checks `r.ok`; one shared data layer / poller (not Header and Dashboard polling separately); a connection-status strip that distinguishes "quiet night" from "pipeline dead"; zone save reports the real result.
- **Provenance is visible**: rows labelled `live | harvest | demo` in Search, Route and Reports.
- **Auth**: the API key is entered once and kept in memory (or `sessionStorage`), sent as `X-API-Key`; admin-only actions hidden for viewers.
- **Offline venue**: Leaflet CSS bundled, not from a CDN; basemap tiles need internet (state it in the UI when tiles fail); pins and route render regardless. OSM attribution stays on (ODbL). No `leaflet.offline` pre-seeding.
- **Nothing on screen may show a credential** — check every address bar, tooltip and error toast before a screen is recorded.
- Plates in URLs are `encodeURIComponent`-ed; navigation uses router `<Link>`s.

## What the previous build did here (read-only reference)

`D:\projects\Sentinel_Repo\ui\src\` — `api.js` (thin client + `DEPT_COLORS`), `main.jsx` (nav + routes), `components/{Header,Tile,FitBounds}.jsx`, `pages/{Dashboard,MapView,LiveWall,Search,RouteView,Alerts,Zones,Reports}.jsx`, `styles.css`. Defect D13 in `docs/reference/old-build/P7-enhancements.md` lists its UI faults; §7 E5 has the operator-experience wish list for after the deadline.
