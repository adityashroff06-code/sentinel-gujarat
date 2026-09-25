import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import Tile from '../components/Tile.jsx'
import { api } from '../lib/api.js'

// Live Wall — 1/4/9/16 grid with paging and source filters. Only the
// visible tiles mount a player; paging unmounts the previous set, which
// destroys those pulls (Tile.jsx cleanup — verified by the smoke's
// network-log assertion). Every camera in the registry is on the wall:
// the relay picks each one's path (worker tee, local feed via mediamtx,
// or the organisers' CDN recording) and the tile badge names it.
// Ported from D:\projects\Sentinel_Repo\ui\src\pages\LiveWall.jsx (F52):
// rewired to the {total, cameras} list shape and the session data layer;
// D13 fixes — no silent .catch(), designed empty/error states, buttons
// instead of click-able spans (keyboard focus), and the wall no longer
// hides cameras whose health is unknown: a dead tile SHOWS its state.
// Relay lane (25 Sep): 16-up grid remembered per browser, filter chips,
// and ?cam=<id> opens one camera full size (a deep link from the map,
// the camera table or a tile's expand button).
const SORT_TIER = { active: 0 }
const SORT_HEALTH = { online: 0, degraded: 1 }
const GRID_SIZES = [1, 4, 9, 16]
const GRID_KEY = 'sentinel.wall.grid'

const FILTERS = [
  { id: 'all', label: 'All', test: () => true },
  { id: 'analysed', label: 'Analysed', test: (c) => c.fps_tier === 'active' },
  { id: 'sandbox', label: 'Sandbox', test: (c) => /^cam/i.test(String(c.camera_id)) },
  { id: 'local', label: 'Local feeds', test: (c) => /^local/i.test(String(c.camera_id)) },
]

// The grid choice is a per-browser convenience: storage can be missing or
// throw (private window, blocked site data) and the wall still works.
function loadGrid() {
  try {
    const n = Number(window.localStorage.getItem(GRID_KEY))
    return GRID_SIZES.includes(n) ? n : 4
  } catch {
    return 4
  }
}

function saveGrid(n) {
  try {
    window.localStorage.setItem(GRID_KEY, String(n))
  } catch {
    // storage unavailable: the choice simply is not remembered
  }
}

export default function LiveWall() {
  const [state, setState] = useState({ status: 'loading', cams: [] })
  const [size, setSize] = useState(loadGrid)
  const [filter, setFilter] = useState('all')
  const [page, setPage] = useState(0)
  const [params, setParams] = useSearchParams()
  const focusId = params.get('cam')

  useEffect(() => {
    let alive = true
    api
      .cameras()
      .then((d) => {
        if (!alive) return
        const cams = [...d.cameras].sort(
          (a, b) =>
            (SORT_TIER[a.fps_tier] ?? 1) - (SORT_TIER[b.fps_tier] ?? 1) ||
            (SORT_HEALTH[a.health] ?? 2) - (SORT_HEALTH[b.health] ?? 2) ||
            String(a.camera_id).localeCompare(String(b.camera_id))
        )
        setState({ status: 'ready', cams })
      })
      .catch(() => alive && setState({ status: 'error', cams: [] }))
    return () => {
      alive = false
    }
  }, [])

  const counts = useMemo(
    () => Object.fromEntries(FILTERS.map((f) => [f.id, state.cams.filter(f.test).length])),
    [state.cams]
  )
  const shown = useMemo(() => {
    const f = FILTERS.find((x) => x.id === filter) || FILTERS[0]
    return state.cams.filter(f.test)
  }, [state.cams, filter])

  const pages = Math.max(1, Math.ceil(shown.length / size))
  const safePage = Math.min(page, pages - 1)
  const visible = useMemo(
    () => shown.slice(safePage * size, safePage * size + size),
    [shown, safePage, size]
  )

  const setGrid = (n) => {
    setSize(n)
    saveGrid(n)
    setPage(0)
  }
  const pickFilter = (id) => {
    setFilter(id)
    setPage(0)
  }
  const closeFocus = () => {
    const next = new URLSearchParams(params)
    next.delete('cam')
    setParams(next)
  }

  if (state.status === 'loading') {
    return (
      <div className="wall">
        <div className="skeleton-rows" aria-label="Loading wall">
          <div className="skeleton" style={{ height: 30, width: '40%' }} />
          <div className="skeleton" style={{ height: 320 }} />
        </div>
      </div>
    )
  }
  if (state.status === 'error') {
    return (
      <div className="state-error">
        Could not load the camera registry — see the status strip above.
      </div>
    )
  }
  if (!state.cams.length) {
    return (
      <div className="state-empty">
        No cameras in the registry yet.
        <span className="hint">
          Seed the catalogue or onboard a camera on the Cameras page.
        </span>
      </div>
    )
  }

  // ---- ?cam=<id>: one camera, full size -----------------------------------
  if (focusId) {
    const cam = state.cams.find((c) => c.camera_id === focusId)
    return (
      <div className="wall">
        <div className="wall-ctrl" role="group" aria-label="Wall controls">
          <button id="wall-back" className="chip" onClick={closeFocus}>
            ‹ back to the wall
          </button>
          {cam && (
            <span className="muted">
              <span className="mono">{cam.camera_id}</span>
              {cam.location_name ? ` · ${cam.location_name}` : ''}
              {cam.department ? ` · ${cam.department}` : ''}
            </span>
          )}
        </div>
        {cam ? (
          <div className="grid g1">
            <Tile key={cam.camera_id} cam={cam} expandable={false} />
          </div>
        ) : (
          <div className="state-empty">
            Camera <span className="mono">{focusId}</span> is not in the registry.
            <span className="hint">Go back to the wall and pick a camera from the grid.</span>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="wall">
      <div className="wall-ctrl" role="group" aria-label="Wall controls">
        <span className="muted">Grid</span>
        {GRID_SIZES.map((n) => (
          <button
            key={n}
            className={`chip ${size === n ? 'on' : ''}`}
            aria-pressed={size === n}
            onClick={() => setGrid(n)}
          >
            {n}
          </button>
        ))}
        <span className="muted wall-sep">Show</span>
        {FILTERS.map((f) => (
          <button
            key={f.id}
            id={`wall-filter-${f.id}`}
            className={`chip ${filter === f.id ? 'on' : ''}`}
            aria-pressed={filter === f.id}
            onClick={() => pickFilter(f.id)}
          >
            {f.label} <span className="num">{counts[f.id]}</span>
          </button>
        ))}
        <span className="spacer" />
        <button
          id="wall-prev"
          className="chip"
          onClick={() => setPage((p) => (Math.min(p, pages - 1) - 1 + pages) % pages)}
        >
          ‹ prev
        </button>
        <span className="muted num">
          page {safePage + 1}/{pages}
        </span>
        <button
          id="wall-next"
          className="chip"
          onClick={() => setPage((p) => (Math.min(p, pages - 1) + 1) % pages)}
        >
          next ›
        </button>
      </div>
      {visible.length ? (
        <div className={`grid g${size}`}>
          {visible.map((c) => (
            <Tile key={c.camera_id} cam={c} />
          ))}
        </div>
      ) : (
        <div className="state-empty">
          No cameras match this filter.
          <span className="hint">Pick “All” to see every camera in the registry.</span>
        </div>
      )}
    </div>
  )
}
