import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { CircleMarker, MapContainer, TileLayer, Tooltip } from 'react-leaflet'
import AlertCard from '../components/AlertCard.jsx'
import FeedStatus from '../components/FeedStatus.jsx'
import FitBounds from '../components/FitBounds.jsx'
import { ProvenanceBadge } from '../components/Badges.jsx'
import Tile from '../components/Tile.jsx'
import { api, deptColor } from '../lib/api.js'
import { useAlertStream, usePolled } from '../lib/poll.js'
import { formatTimeIST } from '../lib/time.js'

// Command — the landing / video screen (HERO, F53). Four live tiles,
// GIS mini-map, streaming alert feed, latest plate reads, object AND
// person counts (F46), worker health, provenance badges, the F46
// "Start here" panel and feed-status strip. Nothing here is hard-coded:
// everything is polled through the ONE shared poller or streamed.
// Ported from D:\projects\Sentinel_Repo\ui\src\pages\Dashboard.jsx (F52):
// rewired off its private setInterval/EventSource onto lib/poll.js,
// D13 fixed (IST times, no silent .catch, critical severity styled,
// designed empty/loading states).

const SORT_TIER = { active: 0 }
const SORT_HEALTH = { online: 0, degraded: 1 }
const OBJECT_CLASSES = ['car', 'motorcycle', 'truck', 'bus', 'auto', 'person']

const fetchCameras = () => api.cameras()
const fetchLatest = () => api.sightings({ limit: 50 })
const fetchSummary = () => api.eventsSummary(60)

export default function Command() {
  const stats = usePolled('stats', api.stats, 5000)?.data
  const camsPolled = usePolled('cameras', fetchCameras, 15000)
  const workersPolled = usePolled('workers', api.workers, 5000)
  const latestPolled = usePolled('sightings-latest', fetchLatest, 5000)
  const summaryPolled = usePolled('events-summary', fetchSummary, 10000)
  const { alerts, loaded: alertsLoaded } = useAlertStream(200)

  const cams = useMemo(() => camsPolled?.data?.cameras ?? [], [camsPolled])
  const workers = workersPolled?.data ?? null
  const sightings = useMemo(() => latestPolled?.data?.sightings ?? [], [latestPolled])
  const summary = summaryPolled?.data ?? null

  const liveTiles = useMemo(
    () =>
      [...cams]
        .sort(
          (a, b) =>
            (SORT_TIER[a.fps_tier] ?? 1) - (SORT_TIER[b.fps_tier] ?? 1) ||
            (SORT_HEALTH[a.health] ?? 2) - (SORT_HEALTH[b.health] ?? 2) ||
            String(a.camera_id).localeCompare(String(b.camera_id))
        )
        .slice(0, 4),
    [cams]
  )
  const pts = cams.filter((c) => Number.isFinite(c.lat) && Number.isFinite(c.lon))

  const lastReadByCam = useMemo(() => {
    const m = {}
    for (const s of sightings) {
      const t = Date.parse(s.seen_at)
      if (Number.isFinite(t)) m[s.camera_id] = Math.max(m[s.camera_id] ?? 0, t)
    }
    return m
  }, [sightings])

  const objectCounts = useMemo(() => {
    const totals = Object.fromEntries(OBJECT_CLASSES.map((c) => [c, 0]))
    for (const cam of Object.values(summary?.cameras ?? {})) {
      for (const [cls, n] of Object.entries(cam.objects ?? {})) {
        if (cls in totals) totals[cls] += n
      }
    }
    return totals
  }, [summary])

  const kpis = stats
    ? [
        ['Cameras online', `${stats.cameras_online}/${stats.cameras_total}`],
        ['Departments', stats.departments],
        ['Sightings', stats.sightings_total],
        ['Unique plates', stats.plates_unique],
        ['Object events', stats.events_total],
        ['Zone events', stats.zone_events],
        ['Active alerts', stats.alerts_active],
      ]
    : []

  const wraw = workers?.cameras
  const workerRows = Object.entries(wraw || {})

  return (
    <div className="page command">
      {/* -------- Start here (F46): what an evaluator is looking at ------- */}
      <div className="card start-here" id="start-here">
        <h2>Start here</h2>
        <ol>
          <li>
            <b>What this is:</b> Sentinel — an integrated video management &amp;
            analytics platform over departmental CCTV networks: one registry, live
            viewing, ANPR search, watchlist alerts and vehicle route
            reconstruction. Every screen is live from the operational backend.
          </li>
          <li>
            <b>Try a route:</b> trace{' '}
            <Link className="plate" to="/route/GJ01AB1234">
              GJ01AB1234
            </Link>{' '}
            (the labelled demonstration vehicle) or{' '}
            <Link className="plate" to="/route/MH04JH3316">
              MH04JH3316
            </Link>{' '}
            (a real plate read live from our own filmed feeds) on the Route
            screen — or search any partial plate under Search.
          </li>
          <li>
            <b>Where the live feeds come from:</b> the organisers&apos; sandbox
            camera grid, pulled live over the gateway, plus our own filmed
            cameras (<span className="mono">local01…</span>) replayed over RTSP —
            two different systems in one viewer.
          </li>
          <li>
            <b>What is demonstration data:</b> the geography of our own feeds is
            seeded, and every row carries a provenance badge — rows marked{' '}
            <span className="prov-badge prov-demo">demo</span> are demonstration
            data, never live reads.
          </li>
        </ol>
      </div>

      {/* -------- feed-status strip (F46) --------------------------------- */}
      <FeedStatus workers={workers} lastReadByCam={lastReadByCam} />

      {/* -------- KPI row -------------------------------------------------- */}
      <div className="kpis">
        {kpis.length
          ? kpis.map(([k, v]) => (
              <div className="kpi" key={k}>
                <b className="num">{v}</b>
                <span>{k}</span>
              </div>
            ))
          : [0, 1, 2, 3, 4, 5, 6].map((i) => (
              <div className="kpi" key={i} aria-hidden="true">
                <div className="skeleton" style={{ height: 24, width: 48 }} />
              </div>
            ))}
      </div>

      <div className="command-grid">
        {/* ---- live tiles ---- */}
        <div className="card span2">
          <h2>
            Live feeds <span className="count">active tier, relayed HLS</span>
            <Link to="/wall" className="chip more">
              wall ›
            </Link>
          </h2>
          {liveTiles.length ? (
            <div className="grid g4">
              {liveTiles.map((c) => (
                <Tile key={c.camera_id} cam={c} />
              ))}
            </div>
          ) : (
            <div className="state-empty">
              No cameras to show yet.
              <span className="hint">The registry is empty — onboard cameras first.</span>
            </div>
          )}
        </div>

        {/* ---- mini-map ---- */}
        <div className="card map-card">
          <h2>
            Camera network <span className="count num">{cams.length} cameras</span>
            <Link to="/map" className="chip more">
              map ›
            </Link>
          </h2>
          <div className="mini-map">
            {pts.length > 0 ? (
              <MapContainer center={[22.5, 71.5]} zoom={7} zoomControl={false} scrollWheelZoom={false}>
                <TileLayer
                  url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
                  attribution="&copy; OpenStreetMap contributors"
                />
                <FitBounds points={pts.map((c) => [c.lat, c.lon])} maxZoom={9} padding={20} />
                {pts.map((c) => (
                  <CircleMarker
                    key={c.camera_id}
                    center={[c.lat, c.lon]}
                    radius={5}
                    pathOptions={{
                      color: deptColor(c.department),
                      fillColor: deptColor(c.department),
                      fillOpacity: c.health === 'online' ? 0.9 : 0.25,
                      opacity: c.health === 'online' ? 1 : 0.4,
                    }}
                  >
                    <Tooltip>
                      {c.camera_id} · {c.department || 'Unknown'} · {c.health || 'unknown'}
                    </Tooltip>
                  </CircleMarker>
                ))}
              </MapContainer>
            ) : (
              <div className="state-empty">No located cameras yet.</div>
            )}
          </div>
        </div>

        {/* ---- live alert feed ---- */}
        <div className="card">
          <h2>
            Live alerts <span className="count">streaming</span>
            <Link to="/alerts" className="chip more">
              all ›
            </Link>
          </h2>
          <div className="alert-feed">
            {alerts.slice(0, 8).map((a) => (
              <AlertCard key={a.alert_seq} alert={a} compact />
            ))}
            {alertsLoaded && alerts.length === 0 && (
              <div className="state-empty">
                No alerts yet.
                <span className="hint">
                  A watchlisted plate passing any active camera fires one here
                  within seconds.
                </span>
              </div>
            )}
          </div>
        </div>

        {/* ---- latest reads ---- */}
        <div className="card">
          <h2>
            Latest plate reads
            <Link to="/search" className="chip more">
              search ›
            </Link>
          </h2>
          {sightings.length ? (
            <table className="reads-table">
              <thead>
                <tr>
                  <th aria-label="Crop" />
                  <th>Plate</th>
                  <th>Conf.</th>
                  <th>Camera</th>
                  <th>Seen (IST)</th>
                  <th>Data</th>
                </tr>
              </thead>
              <tbody>
                {sightings.slice(0, 8).map((r) => (
                  <tr key={r.sighting_id}>
                    <td>
                      {r.crop_url ? (
                        <img className="crop-thumb sm" src={r.crop_url} alt="" />
                      ) : (
                        '—'
                      )}
                    </td>
                    <td>
                      <Link className="plate" to={`/route/${encodeURIComponent(r.plate)}`}>
                        {r.plate}
                      </Link>
                    </td>
                    <td className="num">{r.confidence?.toFixed ? r.confidence.toFixed(2) : r.confidence}</td>
                    <td>
                      <span className="mono">{r.camera_id}</span>{' '}
                      {r.department && (
                        <span style={{ color: deptColor(r.department) }}>{r.department}</span>
                      )}
                    </td>
                    <td className="num">{formatTimeIST(r.seen_at)}</td>
                    <td>
                      <ProvenanceBadge provenance={r.provenance} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="state-empty">
              No plate reads yet.
              <span className="hint">Workers write them here as vehicles pass.</span>
            </div>
          )}
        </div>

        {/* ---- object + person counts (F46) ---- */}
        <div className="card">
          <h2>
            Objects detected <span className="count">last 60 min of the timeline</span>
          </h2>
          <div className="kpis compact">
            {OBJECT_CLASSES.map((cls) => (
              <div className="kpi" key={cls} id={cls === 'person' ? 'person-count' : undefined}>
                <b className="num">{objectCounts[cls]}</b>
                <span>{cls === 'person' ? 'persons' : `${cls}s`}</span>
              </div>
            ))}
          </div>
          <p className="muted footnote">
            Vehicle and person detection per class from the events table; the
            person count is first-class output (FAQ 31), not a by-product.
          </p>
        </div>

        {/* ---- worker health ---- */}
        <div className="card">
          <h2>Analytics workers</h2>
          {workers?.available && workerRows.length > 0 ? (
            <table>
              <thead>
                <tr>
                  <th>Camera</th>
                  <th>State</th>
                  <th>Frames</th>
                  <th>Det.</th>
                  <th>Sightings</th>
                  <th>Alerts</th>
                  <th>Zone</th>
                </tr>
              </thead>
              <tbody>
                {workerRows.map(([cid, w]) => (
                  <tr key={cid}>
                    <td className="mono">{cid}</td>
                    <td>
                      {w.alive === false ? (
                        <span className="sev-word sev-high">DEAD</span>
                      ) : (
                        <span className="ok-word">alive</span>
                      )}
                    </td>
                    <td className="num">{w.frames ?? 0}</td>
                    <td className="num">{w.detections ?? 0}</td>
                    <td className="num">{w.sightings ?? 0}</td>
                    <td className="num">{w.alerts ?? 0}</td>
                    <td className="num">{w.zone_events ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="state-empty">
              No worker snapshot.
              <span className="hint">
                The analytics pipeline is not running — the feed strip above says
                so too.
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
