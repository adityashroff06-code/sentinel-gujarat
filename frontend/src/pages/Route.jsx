import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, Tooltip } from 'react-leaflet'
import { MatchChip, ProvenanceBadge } from '../components/Badges.jsx'
import FitBounds from '../components/FitBounds.jsx'
import { api, deptColor, ROUTE_COLORS } from '../lib/api.js'
import { formatTs } from '../lib/time.js'

// Route — THE scored view: a registration number in, the vehicle's
// complete timestamped location-wise route out. Numbered pins in time
// order, the polyline dashed across coverage gaps, a timeline with crops,
// and a header carrying first/last seen, duration, distance, cameras and
// departments crossed — prominent (docs/api.md §7: direct evidence that
// heterogeneous departmental systems are integrated). Fuzzy, ambiguity
// and suspect stops are visibly marked; warnings[] are shown verbatim.
// Ported from D:\projects\Sentinel_Repo\ui\src\pages\RouteView.jsx (F52):
// rewired to the session data layer; D13 fixed (IST via formatTs, typed
// errors instead of String(e), ambiguity and provenance badges added,
// stops sharing a camera share one pin so overlapping numbers stay
// readable); warnings[] surfaced (B6 — the old UI dropped them).

function fmtDuration(seconds) {
  if (seconds == null) return '—'
  const m = Math.round(seconds / 60)
  return m >= 60 ? `${Math.floor(m / 60)} h ${m % 60} min` : `${m} min`
}

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`

export default function RoutePage() {
  const { plate: plateParam } = useParams()
  const navigate = useNavigate()
  const [plate, setPlate] = useState(plateParam || '')
  const [state, setState] = useState({ status: plateParam ? 'loading' : 'idle', route: null, error: null })
  const [tilesFailed, setTilesFailed] = useState(false)

  const run = useCallback(async (p) => {
    if (!p) return
    setState({ status: 'loading', route: null, error: null })
    try {
      const route = await api.route(p)
      setState({ status: 'ready', route, error: null })
    } catch (err) {
      setState({ status: 'error', route: null, error: err.detail || 'route query failed' })
    }
  }, [])

  useEffect(() => {
    if (plateParam) {
      setPlate(plateParam)
      run(plateParam)
    }
  }, [plateParam, run])

  const trace = (e) => {
    e?.preventDefault()
    const p = plate.trim().toUpperCase()
    if (p) navigate(`/route/${encodeURIComponent(p)}`)
  }

  const route = state.route
  const stops = route?.stops || []
  const located = stops.filter((s) => s.lat != null && s.lon != null)
  const camerasCrossed = new Set(stops.map((s) => s.camera_id)).size
  const gapAfter = useMemo(
    () => new Set((route?.gaps || []).map((g) => g.after_sequence)),
    [route]
  )

  // one pin per camera position: stops sharing a camera share the pin and
  // its number label reads "3·4" instead of two overlapping tooltips
  const pins = useMemo(() => {
    const byCam = new Map()
    for (const s of located) {
      const pin = byCam.get(s.camera_id)
      if (pin) {
        pin.seqs.push(s.sequence)
        pin.suspect = pin.suspect || s.suspect
      } else {
        byCam.set(s.camera_id, { ...s, seqs: [s.sequence], suspect: s.suspect })
      }
    }
    return [...byCam.values()]
  }, [located])

  // polyline legs between consecutive located stops on different cameras;
  // a leg leaving a stop that precedes a coverage gap is dashed
  const legs = useMemo(() => {
    const out = []
    for (let i = 1; i < located.length; i += 1) {
      const prev = located[i - 1]
      const s = located[i]
      if (prev.camera_id === s.camera_id) continue
      out.push({
        key: `${prev.sequence}-${s.sequence}`,
        positions: [
          [prev.lat, prev.lon],
          [s.lat, s.lon],
        ],
        dashed: gapAfter.has(prev.sequence),
      })
    }
    return out
  }, [located, gapAfter])

  return (
    <div className="route-page">
      <div className="route-map">
        {located.length > 0 ? (
          <MapContainer center={[located[0].lat, located[0].lon]} zoom={11} scrollWheelZoom>
            <FitBounds points={located.map((s) => [s.lat, s.lon])} />
            <TileLayer
              url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution="&copy; OpenStreetMap contributors"
              eventHandlers={{ tileerror: () => setTilesFailed(true) }}
            />
            {legs.map((leg) => (
              <Polyline
                key={leg.key}
                positions={leg.positions}
                pathOptions={{
                  color: leg.dashed ? ROUTE_COLORS.gap : ROUTE_COLORS.line,
                  weight: 3,
                  dashArray: leg.dashed ? '6 8' : null,
                }}
              />
            ))}
            {pins.map((p) => (
              <CircleMarker
                key={p.camera_id}
                center={[p.lat, p.lon]}
                radius={13}
                pathOptions={{
                  color: p.suspect ? ROUTE_COLORS.suspect : deptColor(p.department),
                  fillColor: deptColor(p.department),
                  fillOpacity: 0.9,
                  weight: 2,
                }}
              >
                {/* one Tooltip only: a second bindTooltip would replace the
                    permanent number label — details go in a Popup instead */}
                <Tooltip permanent direction="center" className="seqtip" opacity={1}>
                  {p.seqs.join('·')}
                </Tooltip>
                <Popup>
                  {p.camera_id} · {p.department || 'Unknown'} · {p.location_name || 'unnamed'}
                </Popup>
              </CircleMarker>
            ))}
          </MapContainer>
        ) : (
          <div className="state-empty route-map-empty">
            {state.status === 'ready'
              ? 'No located stops for this plate.'
              : 'Enter a registration number to trace its route across the camera network.'}
          </div>
        )}
        {located.length > 0 && tilesFailed && (
          <div className="map-note" role="note">
            Basemap tiles need internet — pins, route and timeline still work.
          </div>
        )}
      </div>

      <div className="route-panel">
        <form className="route-form" onSubmit={trace}>
          <label className="visually-hidden" htmlFor="route-plate">
            Registration number
          </label>
          <input
            id="route-plate"
            className="plate"
            placeholder="registration no."
            value={plate}
            onChange={(e) => setPlate(e.target.value.toUpperCase())}
          />
          <button className="primary" type="submit">
            Trace
          </button>
        </form>

        {state.status === 'loading' && (
          <div className="skeleton-rows" aria-label="Tracing route">
            <div className="skeleton" style={{ height: 90 }} />
            {[0, 1, 2].map((i) => (
              <div key={i} className="skeleton" style={{ height: 56 }} />
            ))}
          </div>
        )}
        {state.status === 'error' && (
          <div className="state-error">{state.error}</div>
        )}
        {state.status === 'ready' && route && route.total_sightings === 0 && (
          <div className="state-empty">
            No sightings for <span className="plate">{route.query_plate}</span>.
            <span className="hint">
              The plate has not passed a covered camera — or try a partial search
              under Search.
            </span>
          </div>
        )}

        {state.status === 'ready' && route && route.total_sightings > 0 && (
          <>
            {/* ---- the header: the scored answer, largest type ---- */}
            <div className="route-header" id="route-header">
              <div className="route-plate-line">
                <span className="plate hero">{route.query_plate}</span>
                <span className="chip on">{route.match_mode}</span>
              </div>
              <div className="route-depts" aria-label="Departments crossed">
                {route.departments_crossed.map((d) => (
                  <span key={d} className="badge" style={{ background: deptColor(d) }}>
                    {d}
                  </span>
                ))}
                <span className="route-depts-count">
                  {plural(route.departments_crossed.length, 'department')} crossed
                </span>
              </div>
              <div className="route-stats">
                <div className="kv">
                  <span>First seen</span>
                  <span className="num">{formatTs(route.first_seen)}</span>
                </div>
                <div className="kv">
                  <span>Last seen</span>
                  <span className="num">{formatTs(route.last_seen)}</span>
                </div>
                <div className="kv">
                  <span>Duration</span>
                  <span className="num">{fmtDuration(route.duration_seconds)}</span>
                </div>
                <div className="kv">
                  <span>Distance</span>
                  <span className="num">
                    {route.distance_km != null ? `${route.distance_km} km` : '—'}
                  </span>
                </div>
                <div className="kv">
                  <span>Stops / cameras</span>
                  <span className="num">
                    {plural(stops.length, 'stop')} · {plural(camerasCrossed, 'camera')}
                  </span>
                </div>
              </div>
            </div>

            {route.warnings?.length > 0 && (
              <div className="route-warnings" role="note">
                {route.warnings.map((w) => (
                  <p key={w}>⚠ {w}</p>
                ))}
              </div>
            )}

            {/* ---- the timeline ---- */}
            <div className="route-timeline">
              {stops.map((s) => (
                <div
                  key={s.sequence}
                  className={`route-stop ${s.suspect ? 'suspect' : ''} match-${s.match_type}`}
                >
                  <div
                    className="seq"
                    style={{ background: s.suspect ? ROUTE_COLORS.suspect : deptColor(s.department) }}
                  >
                    {s.sequence}
                  </div>
                  {s.crop_url && (
                    <img className="crop-thumb" src={s.crop_url} alt={`crop at ${s.camera_id}`} />
                  )}
                  <div className="stop-body">
                    <div>
                      <b className="mono">{s.camera_id}</b>{' '}
                      <span style={{ color: deptColor(s.department) }}>
                        {s.department || 'Unknown'}
                      </span>{' '}
                      <MatchChip matchType={s.match_type} distance={s.match_distance} />{' '}
                      <ProvenanceBadge provenance={s.provenance} />
                    </div>
                    <div className="muted">
                      <span className="plate sm">{s.plate_raw}</span> · conf{' '}
                      <span className="num">{s.confidence?.toFixed ? s.confidence.toFixed(2) : s.confidence}</span>
                      {s.location_name && ` · ${s.location_name}`}
                    </div>
                    <div className="muted num">
                      {formatTs(s.seen_at)}
                      {s.elapsed_from_previous_s != null &&
                        ` · +${Math.round(s.elapsed_from_previous_s / 60)} min`}
                      {s.implied_speed_kmh != null && ` · ${s.implied_speed_kmh} km/h`}
                      {s.suspect && (
                        <span className="sev-word sev-high"> ⚠ SUSPECT — implausible speed</span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {route.gaps?.length > 0 && (
              <p className="muted route-gaps">
                {plural(route.gaps.length, 'coverage gap')}:{' '}
                {route.gaps
                  .map((g) => `after #${g.after_sequence} (${g.minutes} min — ${g.note})`)
                  .join('; ')}
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}
