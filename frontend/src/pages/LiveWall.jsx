import { useEffect, useMemo, useState } from 'react'
import Tile from '../components/Tile.jsx'
import { api } from '../lib/api.js'

// Live Wall — 1/4/9 grid with paging. Only the visible tiles mount a
// player; paging unmounts the previous set, which destroys those pulls
// (Tile.jsx cleanup — verified by the smoke's network-log assertion).
// Ported from D:\projects\Sentinel_Repo\ui\src\pages\LiveWall.jsx (F52):
// rewired to the {total, cameras} list shape and the session data layer;
// D13 fixes — no silent .catch(), designed empty/error states, buttons
// instead of click-able spans (keyboard focus), and the wall no longer
// hides cameras whose health is unknown: a dead tile SHOWS its state.
const SORT_TIER = { active: 0 }
const SORT_HEALTH = { online: 0, degraded: 1 }

export default function LiveWall() {
  const [state, setState] = useState({ status: 'loading', cams: [] })
  const [size, setSize] = useState(4)
  const [page, setPage] = useState(0)

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

  const pages = Math.max(1, Math.ceil(state.cams.length / size))
  const visible = useMemo(
    () => state.cams.slice(page * size, page * size + size),
    [state.cams, page, size]
  )

  const setGrid = (n) => {
    setSize(n)
    setPage(0)
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

  return (
    <div className="wall">
      <div className="wall-ctrl" role="group" aria-label="Wall controls">
        <span className="muted">Grid</span>
        {[1, 4, 9].map((n) => (
          <button
            key={n}
            className={`chip ${size === n ? 'on' : ''}`}
            aria-pressed={size === n}
            onClick={() => setGrid(n)}
          >
            {n}
          </button>
        ))}
        <span className="spacer" />
        <button
          id="wall-prev"
          className="chip"
          onClick={() => setPage((p) => (p - 1 + pages) % pages)}
        >
          ‹ prev
        </button>
        <span className="muted num">
          page {page + 1}/{pages}
        </span>
        <button id="wall-next" className="chip" onClick={() => setPage((p) => (p + 1) % pages)}>
          next ›
        </button>
      </div>
      <div className={`grid g${size}`}>
        {visible.map((c) => (
          <Tile key={c.camera_id} cam={c} />
        ))}
      </div>
    </div>
  )
}
