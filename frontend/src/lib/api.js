// The ONE API client (frontend/CLAUDE.md; docs/api.md §7).
// Ported from D:\projects\Sentinel_Repo\ui\src\api.js (F52) and rewired:
//  - session-cookie auth (decision F41): every call carries
//    credentials 'same-origin', so the sentinel_session cookie from the
//    login covers fetches, <img> crops, hls.js segments and EventSource
//    alike — no key dialog, no sessionStorage key;
//  - a 401 anywhere sends the user to /login (with a safe next param);
//  - r.ok is checked everywhere (old defect D13 — never .catch(() => {}));
//  - failures become typed ApiErrors surfaced on the global status strip.

const BASE = '/api'

// ---- typed errors + global status strip ------------------------------------

export class ApiError extends Error {
  /** kind: auth | forbidden | not-found | conflict | validation |
   *        rate-limit | server | network */
  constructor(kind, status, detail, path) {
    super(detail || `${path} -> ${status}`)
    this.name = 'ApiError'
    this.kind = kind
    this.status = status
    this.detail = detail
    this.path = path
  }
}

const statusListeners = new Set()
let stripError = null // {kind, path} of the error the strip currently shows

/** Subscribe to data-layer status events ({kind, message} or null to clear).
 *  Returns an unsubscribe function. Used by the StatusStrip. */
export function onStatus(listener) {
  statusListeners.add(listener)
  return () => statusListeners.delete(listener)
}

function report(event, path) {
  stripError = event ? { kind: event.kind, path } : null
  for (const l of statusListeners) l(event)
}

// A success clears the strip only when it answers the message on it: the
// same path recovering, or ANY success while a network error shows (any
// answer proves the API is reachable again). A background poll succeeding
// must not wipe an unrelated error the operator has not read yet.
function clearOnSuccess(path) {
  if (!stripError) return
  if (stripError.path === path || stripError.kind === 'network') report(null)
}

function kindFor(status) {
  if (status === 401) return 'auth'
  if (status === 403) return 'forbidden'
  if (status === 404) return 'not-found'
  if (status === 409) return 'conflict'
  if (status === 422) return 'validation'
  if (status === 429) return 'rate-limit'
  return 'server'
}

function redirectToLogin() {
  if (window.location.pathname === '/login') return
  const next = window.location.pathname + window.location.search
  window.location.replace('/login?next=' + encodeURIComponent(next))
}

async function detailOf(r) {
  try {
    const body = await r.json()
    if (typeof body?.detail === 'string') return body.detail
    if (Array.isArray(body?.detail) && body.detail[0]?.msg) {
      const first = body.detail[0]
      const field = (first.loc || []).slice(1).join('.')
      return field ? `${field}: ${first.msg}` : first.msg
    }
  } catch {
    /* non-JSON body: fall through to the status line */
  }
  return `request failed (${r.status})`
}

/** Core request. opts.on401 'redirect' (default) or 'throw' (login form).
 *  opts.quiet: an HTTP error is thrown but NOT put on the global status
 *  strip (per-tile background calls — each tile shows its own state);
 *  an unreachable API and a 401 are still reported. */
async function request(path, { method = 'GET', body, formData, on401 = 'redirect', quiet = false } = {}) {
  const say = quiet ? () => {} : report
  const init = { method, credentials: 'same-origin', headers: {} }
  if (formData) {
    init.body = formData
  } else if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json'
    init.body = JSON.stringify(body)
  }
  let r
  try {
    r = await fetch(BASE + path, init)
  } catch {
    const err = new ApiError('network', 0, 'API unreachable — is the backend running?', path)
    report({ kind: err.kind, message: err.detail }, path)
    throw err
  }
  if (r.status === 401 && on401 === 'redirect') {
    report({ kind: 'auth', message: 'Session expired — sign in again.' }, path)
    redirectToLogin()
    throw new ApiError('auth', 401, 'not authenticated', path)
  }
  if (!r.ok) {
    const err = new ApiError(kindFor(r.status), r.status, await detailOf(r), path)
    say({ kind: err.kind, message: err.detail }, path)
    throw err
  }
  clearOnSuccess(path)
  return r.status === 204 ? null : r.json()
}

const qs = (params = {}) => {
  const clean = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
  )
  const q = new URLSearchParams(clean).toString()
  return q ? `?${q}` : ''
}

// ---- the client -------------------------------------------------------------

export const api = {
  // auth (decision F41)
  login: (username, password) =>
    request('/auth/login', { method: 'POST', body: { username, password }, on401: 'throw' }),
  logout: () => request('/auth/logout', { method: 'POST' }),
  me: () => request('/auth/me', { on401: 'throw' }),

  // meta
  health: () => request('/health'),
  stats: () => request('/stats'),
  workers: () => request('/workers'),

  // cameras (Model 1 registry)
  cameras: (params = {}) => request('/cameras' + qs(params)),
  camera: (id) => request(`/cameras/${encodeURIComponent(id)}`),
  gapAnalysis: () => request('/cameras/gap-analysis'),
  // GIS Activity layer: [{camera_id, sightings, plates, alerts, last_seen,
  // by_provenance}] over the last `hours` (idle cameras omitted)
  cameraActivity: (hours = 24) => request('/cameras/activity' + qs({ hours })),
  createCamera: (body) => request('/cameras', { method: 'POST', body }),
  patchCamera: (id, body) =>
    request(`/cameras/${encodeURIComponent(id)}`, { method: 'PATCH', body }),
  importCameras: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return request('/cameras/import', { method: 'POST', formData: fd })
  },
  streamInfo: (id) => request(`/cameras/${encodeURIComponent(id)}/stream`),

  // analytics
  // params.match: contains (server default) | exact | anpr (docs/api.md §7)
  sightings: (params = {}) => request('/sightings' + qs(params)),
  plateSuggest: (limit = 8) => request(`/plates/suggest${qs({ limit })}`),
  route: (plate) => request(`/plates/${encodeURIComponent(plate)}/route`),
  events: (params = {}) => request('/events' + qs(params)),
  eventsSummary: (minutes = 60) => request(`/events/summary${qs({ minutes })}`),

  // watchlist (POST takes plate, category, severity, description?, source_ref?)
  watchlist: () => request('/watchlist'),
  addWatchlist: (body) => request('/watchlist', { method: 'POST', body }),
  removeWatchlist: (id) => request(`/watchlist/${id}`, { method: 'DELETE' }),

  // alerts
  alerts: (params = {}) => request('/alerts' + qs(params)),
  ack: (id) => request(`/alerts/${encodeURIComponent(id)}/ack`, { method: 'POST' }),

  // live relay (Pipeline 1): which path a camera's playlist takes —
  // {camera_id, source: tee|stale-tee|mediamtx|cdn|none, detail}. Quiet:
  // a tile shows its own state, never the global strip.
  hlsSource: (id) => request(`/hls/${encodeURIComponent(id)}/source`, { quiet: true }),

  // media URLs — plain same-origin paths: the session cookie carries them
  streamUrl: (id) => `${BASE}/hls/${encodeURIComponent(id)}/live.m3u8`,
  alertStreamUrl: `${BASE}/alerts/stream`,
  reportUrl: (kind, fmt = 'html', filters = {}) =>
    kind === 'gap'
      ? `${BASE}/reports/gap-analysis`
      : `${BASE}/reports/detections${qs({ format: fmt, ...filters })}`,
  routeReportUrl: (plate, fmt = 'html') =>
    `${BASE}/reports/route/${encodeURIComponent(plate)}${qs({ format: fmt })}`,
}

// clock_source -> provenance, mirroring ml/worker.PROVENANCE (decision F26):
// alert rows carry only clock_source, so their provenance badge derives here.
const CLOCK_PROVENANCE = {
  'rtsp-live': 'live',
  'hls-vod': 'harvest',
  harvest: 'harvest',
  replay: 'test',
  demo: 'demo',
}
export const provenanceOf = (clockSource) => CLOCK_PROVENANCE[clockSource] || 'test'

// ---- department palette (ported verbatim from the old api.js; the values
// live in tokens.css — keep the two in sync) ---------------------------------

export const DEPT_COLORS = {
  Police: '#3d7fd6',
  GSRTC: '#e0912f',
  Municipal: '#39a56a',
  Panchayat: '#b45fd1',
  Health: '#d64f6a',
  Unknown: '#8a97a6',
}
export const deptColor = (d) => DEPT_COLORS[d] || DEPT_COLORS.Unknown

// Leaflet paints SVG presentation attributes, where CSS var() does not
// resolve — so the route line colours live here beside DEPT_COLORS, with
// the same rule: the values mirror tokens.css (--accent, --text-muted,
// --danger); keep the two in sync.
export const ROUTE_COLORS = {
  line: '#3d7fd6', // --accent
  gap: '#8a97a6', // --text-muted (dashed across coverage gaps)
  suspect: '#d64f6a', // --danger (implausible-speed stop ring)
}
