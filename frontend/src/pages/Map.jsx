import { useEffect, useMemo, useState } from 'react'
import { CircleMarker, MapContainer, TileLayer, Tooltip } from 'react-leaflet'
import DeptLegend from '../components/DeptLegend.jsx'
import FitBounds from '../components/FitBounds.jsx'
import { api, deptColor } from '../lib/api.js'
import { formatTs } from '../lib/time.js'

// GIS map (Model 1). Every camera a pin, coloured by department, health by
// opacity; department + status filters; click a pin -> full record panel.
// Ported from D:\projects\Sentinel_Repo\ui\src\pages\MapView.jsx (F52):
// rewired to the {total, cameras} list shape and the session data layer;
// D13 fixes — errors reach the status strip (no .catch(() => {})),
// timestamps render through formatTs (IST), OSM attribution stays on.
export default function MapPage() {
  const [state, setState] = useState({ status: 'loading', cams: [] })
  const [sel, setSel] = useState(null)
  const [deptOff, setDeptOff] = useState({}) // department -> hidden?
  const [onlineOnly, setOnlineOnly] = useState(false)
  const [tilesFailed, setTilesFailed] = useState(false)

  useEffect(() => {
    let alive = true
    api
      .cameras()
      .then((d) => alive && setState({ status: 'ready', cams: d.cameras }))
      .catch(() => alive && setState({ status: 'error', cams: [] }))
    return () => {
      alive = false
    }
  }, [])

  const depts = useMemo(
    () =>
      [...new Set(state.cams.map((c) => c.department || 'Unknown'))].sort(),
    [state.cams]
  )
  const shown = state.cams.filter(
    (c) =>
      c.lat != null &&
      c.lon != null &&
      !deptOff[c.department || 'Unknown'] &&
      (!onlineOnly || c.health === 'online')
  )
  const center = shown.length
    ? [
        shown.reduce((a, c) => a + c.lat, 0) / shown.length,
        shown.reduce((a, c) => a + c.lon, 0) / shown.length,
      ]
    : [22.6, 72.0]

  if (state.status === 'loading') {
    return (
      <div className="page">
        <div className="card">
          <div className="skeleton-rows" aria-label="Loading map">
            <div className="skeleton" style={{ height: 28, width: '30%' }} />
            <div className="skeleton" style={{ height: 320 }} />
          </div>
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
          Seed the catalogue (backend.tools.seed_registry) or onboard one on
          the Cameras page.
        </span>
      </div>
    )
  }

  return (
    <div className="map-wrap">
      <div className="filters" role="group" aria-label="Map filters">
        {depts.map((d) => (
          <button
            key={d}
            className={`chip ${deptOff[d] ? '' : 'on'}`}
            style={{ borderColor: deptOff[d] ? undefined : deptColor(d) }}
            aria-pressed={!deptOff[d]}
            onClick={() => setDeptOff((o) => ({ ...o, [d]: !o[d] }))}
          >
            {d}
          </button>
        ))}
        <button
          className={`chip ${onlineOnly ? 'on' : ''}`}
          aria-pressed={onlineOnly}
          onClick={() => setOnlineOnly((v) => !v)}
        >
          online only
        </button>
      </div>

      <MapContainer center={center} zoom={7} scrollWheelZoom>
        <FitBounds points={shown.map((c) => [c.lat, c.lon])} maxZoom={12} />
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution="&copy; OpenStreetMap contributors"
          eventHandlers={{ tileerror: () => setTilesFailed(true) }}
        />
        {shown.map((c) => (
          <CircleMarker
            key={c.camera_id}
            center={[c.lat, c.lon]}
            radius={7}
            pathOptions={{
              color: deptColor(c.department),
              fillColor: deptColor(c.department),
              fillOpacity: c.health === 'online' ? 0.9 : 0.25,
              weight: c.health === 'online' ? 2 : 1,
            }}
            eventHandlers={{
              click: () =>
                api.camera(c.camera_id).then(setSel).catch(() => setSel(null)),
            }}
          >
            <Tooltip>
              {c.camera_id} · {c.department || 'Unknown'} ·{' '}
              {c.location_name || 'unnamed'} · {c.health || 'health unknown'}
            </Tooltip>
          </CircleMarker>
        ))}
      </MapContainer>

      {tilesFailed && (
        <div className="map-note" role="note">
          Basemap tiles need internet — pins and records still work.
        </div>
      )}
      <DeptLegend depts={depts} />

      {sel && (
        <div className="side" role="region" aria-label={`Camera ${sel.camera_id}`}>
          <button className="ghost close" onClick={() => setSel(null)} aria-label="Close">
            ×
          </button>
          <h3>
            {sel.camera_id}
            <span className="badge" style={{ background: deptColor(sel.department) }}>
              {sel.department || 'Unknown'}
            </span>
          </h3>
          <div className="loc">{sel.location_name || 'unnamed location'}</div>
          {[
            ['Health', sel.health],
            ['Transport', sel.transport],
            ['Tier', sel.fps_tier],
            ['Codec', sel.codec],
            ['Resolution', sel.width ? `${sel.width}×${sel.height}` : null],
            ['Declared fps', sel.declared_fps],
            ['Measured fps', sel.measured_fps],
            ['Bitrate', sel.bitrate_kbps ? `${sel.bitrate_kbps} kbps` : null],
            ['Ownership', sel.ownership],
            ['Coordinates', sel.lat != null ? `${sel.lat}, ${sel.lon}` : null],
            ['Last seen', formatTs(sel.last_seen)],
            ['Source', sel.source],
          ].map(([k, v]) => (
            <div className="kv" key={k}>
              <span>{k}</span>
              <span>{v ?? '—'}</span>
            </div>
          ))}
          {sel.notes && <p className="muted" style={{ marginTop: 12 }}>{sel.notes}</p>}
        </div>
      )}
    </div>
  )
}
