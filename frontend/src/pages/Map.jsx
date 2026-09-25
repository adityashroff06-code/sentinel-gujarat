import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import L from 'leaflet'
import { LayerGroup, LayersControl, MapContainer, ScaleControl } from 'react-leaflet'
import FitBounds from '../components/FitBounds.jsx'
import BaseLayers from '../components/map/BaseLayers.jsx'
import CameraRecord from '../components/map/CameraRecord.jsx'
import {
  ActivityLayer,
  CameraPins,
  ClusterBubbles,
  ClusterHulls,
  CoverageLayer,
  GapsLayer,
  GisPanes,
  MapEvents,
} from '../components/map/GisLayers.jsx'
import MapLegend from '../components/map/MapLegend.jsx'
import { api } from '../lib/api.js'
import { BASEMAPS, storedBasemap, useTileHealth } from '../lib/basemaps.js'
import { CLUSTER_KM, clusterCameras, clusterHullShapes, isLocated } from '../lib/geo.js'
import { DEPARTMENTS, deptClass, deptKey, esc, feedKind, healthKey, isAnalysed } from '../lib/pins.js'
import { usePolled } from '../lib/poll.js'

// GIS map (Model 1 — the mandatory registry + GIS). Every registered
// camera on a basemap the viewer picks (dark control-room default,
// streets, light, satellite), with GIS overlays in the layers control:
// one layer per department, field-of-view coverage, read activity over
// the last 24 h (GET /api/cameras/activity), 15 km single-linkage
// clusters, and coverage gaps (GET /api/cameras/gap-analysis). Below zoom
// BUBBLE_ZOOM the network shows as cluster count bubbles so ~60 pins stay
// legible; pins from there in. A pin opens the full record with the ways
// onward (live view, recent reads). Chrome: a network summary strip, a
// camera search / jump box, fit-all and per-cluster zoom, a legend, a
// metric scale and a live pointer lat/lon readout.
// First ported from D:\projects\Sentinel_Repo\ui\src\pages\MapView.jsx
// (F52); rebuilt for the GIS lane (25 Sep).

const HOURS = 24
const BUBBLE_ZOOM = 9 // below: cluster count bubbles; at/above: pins
const LABEL_ZOOM = 13 // at/above: every pin shows its camera id
const WEDGE_ZOOM = 12 // at/above: field-of-view wedges drawn
const HULL_BUFFER_KM = 1.2

const fetchCameras = () => api.cameras()
const fetchActivity = () => api.cameraActivity(HOURS)

// Layer-control labels. Leaflet inserts them as HTML, so they are built
// from constants only (department names come from the fixed palette).
const deptOverlayName = (d) =>
  `<span class="lc-key lc-dept ${deptClass(d)}" aria-hidden="true"></span>${esc(d)}`
const ANALYSIS_LAYERS = [
  { key: 'clusters', label: `Clusters · ${CLUSTER_KM} km`, checked: true },
  { key: 'coverage', label: 'Coverage · FOV', checked: true },
  { key: 'activity', label: `Activity · ${HOURS} h`, checked: true },
  { key: 'gaps', label: 'Gaps', checked: false },
].map((l, i) => ({
  ...l,
  name:
    `<span class="lc-key lc-${l.key}${i === 0 ? ' lc-group-start' : ''}" aria-hidden="true"></span>` +
    esc(l.label),
}))
const NAME_TO_KEY = new Map([
  ...DEPARTMENTS.map((d) => [deptOverlayName(d), d]),
  ...ANALYSIS_LAYERS.map((l) => [l.name, l.key]),
])
const INITIAL_ON = {
  ...Object.fromEntries(DEPARTMENTS.map((d) => [d, true])),
  ...Object.fromEntries(ANALYSIS_LAYERS.map((l) => [l.key, l.checked])),
}

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`

function Stat({ n, label, sub, tone }) {
  return (
    <div className={`gis-stat ${tone ? `tone-${tone}` : ''}`}>
      <b className="num">{n}</b>
      <span>{label}</span>
      {sub && <small>{sub}</small>}
    </div>
  )
}

export default function MapPage() {
  const [params] = useSearchParams()
  const camsPolled = usePolled('cameras', fetchCameras, 15000)
  const activityPolled = usePolled(`camera-activity-${HOURS}`, fetchActivity, 30000)
  const gapsPolled = usePolled('gap-analysis', api.gapAnalysis, 60000)
  const tiles = useTileHealth()

  const [map, setMap] = useState(null)
  const [zoom, setZoom] = useState(7)
  const [on, setOn] = useState(INITIAL_ON)
  const [selId, setSelId] = useState(null)
  const [query, setQuery] = useState('')
  const [jumpMsg, setJumpMsg] = useState(null)
  const [basemap, setBasemap] = useState(() => BASEMAPS.find((b) => b.id === storedBasemap()))
  const cursorRef = useRef(null)
  const deepLinked = useRef(false)

  const cams = useMemo(() => camsPolled?.data?.cameras ?? [], [camsPolled])
  const byId = useMemo(() => new Map(cams.map((c) => [c.camera_id, c])), [cams])
  const located = useMemo(() => cams.filter(isLocated), [cams])
  const clusters = useMemo(() => clusterCameras(located), [located])
  const multiClusters = useMemo(() => clusters.filter((cl) => cl.members.length > 1), [clusters])

  const activity = useMemo(() => {
    const m = new Map()
    for (const a of activityPolled?.data ?? []) m.set(a.camera_id, a)
    return m
  }, [activityPolled])
  const gaps = gapsPolled?.data ?? null
  const gapIds = useMemo(
    () => new Set((gaps?.cameras_offline_or_degraded ?? []).map((g) => g.camera_id)),
    [gaps]
  )

  const visible = useMemo(
    () => located.filter((c) => on[deptKey(c.department)]),
    [located, on]
  )

  // Hull outlines and their "N cameras · M departments" labels follow the
  // department toggles exactly as the bubbles under them do: each cluster
  // keeps only its visible members (clusterHullShapes drops any left with
  // fewer than 2), and departments are counted by deptKey like a bubble's.
  const hulls = useMemo(() => {
    const shown = new Set(visible.map((c) => c.camera_id))
    const visClusters = clusters.map((cl) => {
      const members = cl.members.filter((c) => shown.has(c.camera_id))
      return { ...cl, members, departments: [...new Set(members.map((c) => deptKey(c.department)))] }
    })
    return clusterHullShapes(visClusters, HULL_BUFFER_KM)
  }, [clusters, visible])

  // Low zoom: a cluster with 2+ visible cameras becomes one count bubble;
  // a lone visible camera stays a pin. From BUBBLE_ZOOM in: all pins.
  const { pinCams, bubbles } = useMemo(() => {
    if (zoom >= BUBBLE_ZOOM) return { pinCams: visible, bubbles: [] }
    const shown = new Set(visible.map((c) => c.camera_id))
    const pinsOut = []
    const bubblesOut = []
    for (const cl of clusters) {
      const members = cl.members.filter((c) => shown.has(c.camera_id))
      if (members.length === 1) pinsOut.push(members[0])
      else if (members.length > 1) {
        bubblesOut.push({
          ...cl,
          members,
          departments: [...new Set(members.map((c) => deptKey(c.department)))],
          gapCount: on.gaps ? members.filter((c) => gapIds.has(c.camera_id)).length : 0,
        })
      }
    }
    return { pinCams: pinsOut, bubbles: bubblesOut }
  }, [zoom, visible, clusters, on.gaps, gapIds])

  const pinsByDept = useMemo(() => {
    const m = Object.fromEntries(DEPARTMENTS.map((d) => [d, []]))
    for (const c of pinCams) m[deptKey(c.department)].push(c)
    return m
  }, [pinCams])

  // activity circles follow what is on screen: per pin, or summed per bubble.
  // Reads and alerts add up across a bubble's cameras; distinct plates do
  // not (a plate read on two cameras is one plate, not two), and the API
  // gives distinct counts per camera only — so a bubble shows no
  // distinct-plate figure rather than an overstated one (rule 8).
  const activityItems = useMemo(() => {
    const item = (key, center, label, rows) => {
      const byProv = {}
      let lastSeen = null
      // exact only while one camera holds every read (an alerts-only row has none)
      const reading = rows.filter((a) => a.sightings > 0)
      for (const a of rows) {
        for (const [p, n] of Object.entries(a.by_provenance || {})) byProv[p] = (byProv[p] || 0) + n
        if (a.last_seen && (!lastSeen || a.last_seen > lastSeen)) lastSeen = a.last_seen
      }
      return {
        key,
        center,
        label,
        sightings: rows.reduce((s, a) => s + a.sightings, 0),
        plates: reading.length > 1 ? null : (reading[0]?.plates ?? 0),
        alerts: rows.reduce((s, a) => s + a.alerts, 0),
        byProv,
        lastSeen,
      }
    }
    const out = []
    for (const c of pinCams) {
      const a = activity.get(c.camera_id)
      if (a) out.push(item(c.camera_id, [c.lat, c.lon], c.camera_id, [a]))
    }
    for (const b of bubbles) {
      const rows = b.members.map((c) => activity.get(c.camera_id)).filter(Boolean)
      if (rows.length) {
        out.push(item(b.id, b.centroid, `${b.name ? `Near ${b.name}` : 'Cluster'} (${rows.length} active cameras)`, rows))
      }
    }
    return out.filter((a) => a.sightings > 0 || a.alerts > 0)
  }, [pinCams, bubbles, activity])

  const onScreen = useMemo(() => new Set(pinCams.map((c) => c.camera_id)), [pinCams])
  const gapOffline = useMemo(
    () => (gaps?.cameras_offline_or_degraded ?? []).filter((g) => onScreen.has(g.camera_id)),
    [gaps, onScreen]
  )
  const gapIsolated = useMemo(
    () =>
      (gaps?.isolated_coverage ?? []).filter((g) => {
        const c = byId.get(g.camera_id)
        return c && isLocated(c) && on[deptKey(c.department)]
      }),
    [gaps, byId, on]
  )

  const stats = useMemo(() => {
    const depts = new Map()
    for (const c of cams) {
      const d = deptKey(c.department)
      const e = depts.get(d) || { dept: d, total: 0, online: 0 }
      e.total += 1
      if (healthKey(c.health) === 'online') e.online += 1
      depts.set(d, e)
    }
    let reads = 0
    const prov = {}
    for (const a of activity.values()) {
      reads += a.sightings
      for (const [p, n] of Object.entries(a.by_provenance || {})) prov[p] = (prov[p] || 0) + n
    }
    return {
      total: cams.length,
      online: cams.filter((c) => healthKey(c.health) === 'online').length,
      analysed: cams.filter(isAnalysed).length,
      sandbox: cams.filter((c) => feedKind(c) === 'sandbox').length,
      local: cams.filter((c) => feedKind(c) === 'local').length,
      unlocated: cams.length - located.length,
      depts: DEPARTMENTS.filter((d) => depts.has(d)).map((d) => depts.get(d)),
      reads,
      prov,
    }
  }, [cams, located, activity])

  const onOverlay = useCallback((name, visibleNow) => {
    const key = NAME_TO_KEY.get(name)
    if (key) setOn((o) => ({ ...o, [key]: visibleNow }))
  }, [])

  const fitAll = useCallback(() => {
    if (!map || !located.length) return
    map.fitBounds(L.latLngBounds(located.map((c) => [c.lat, c.lon])), {
      padding: [48, 48],
      maxZoom: 12,
    })
  }, [map, located])

  const zoomCluster = useCallback(
    (cl) => {
      if (!map) return
      map.fitBounds(L.latLngBounds(cl.members.map((c) => [c.lat, c.lon])), {
        padding: [72, 72],
        maxZoom: 15,
      })
    },
    [map]
  )

  const select = useCallback(
    (id, fly) => {
      setSelId(id)
      const c = byId.get(id)
      if (fly && map && c && isLocated(c)) {
        map.flyTo([c.lat, c.lon], Math.max(map.getZoom(), 16), { duration: 0.8 })
      }
    },
    [byId, map]
  )

  const zoomTo = useCallback(
    (c) => map?.flyTo([c.lat, c.lon], Math.max(map.getZoom(), 16), { duration: 0.8 }),
    [map]
  )

  // /map?cam=<id> opens that camera's record once the registry arrives
  useEffect(() => {
    const want = params.get('cam')
    if (!want || deepLinked.current || !map || !byId.has(want)) return
    deepLinked.current = true
    select(want, true)
  }, [params, map, byId, select])

  // the record panel narrows the map: let Leaflet re-measure
  const panelOpen = selId != null
  useEffect(() => {
    map?.invalidateSize({ pan: false })
  }, [map, panelOpen])

  const jump = (e) => {
    e.preventDefault()
    const q = query.trim().toLowerCase()
    if (!q) return
    const hit =
      cams.find((c) => String(c.camera_id).toLowerCase() === q) ||
      cams.find(
        (c) =>
          String(c.camera_id).toLowerCase().includes(q) ||
          (c.location_name || '').toLowerCase().includes(q)
      )
    if (!hit) {
      setJumpMsg(`No camera matches “${query.trim()}”.`)
      return
    }
    setJumpMsg(null)
    select(hit.camera_id, true)
  }

  if (!camsPolled || (!camsPolled.data && !camsPolled.error)) {
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
  if (!camsPolled.data) {
    return (
      <div className="state-error">
        Could not load the camera registry — see the status strip above.
      </div>
    )
  }
  if (!cams.length) {
    return (
      <div className="state-empty">
        No cameras in the registry yet.
        <span className="hint">
          Seed the catalogue (backend.tools.seed_registry) or onboard one on the Cameras page.
        </span>
      </div>
    )
  }

  const selected = selId ? byId.get(selId) : null
  const provSub = Object.entries(stats.prov)
    .map(([p, n]) => `${n} ${p}`)
    .join(' · ')

  return (
    <div className="gis">
      <div className="gis-stats" role="group" aria-label="Camera network summary" id="gis-stats">
        <Stat n={stats.total} label="cameras" />
        <Stat n={stats.online} label="online" tone="ok" />
        <Stat n={stats.analysed} label="analysed" />
        <Stat n={stats.local} label="local feeds" />
        <Stat n={stats.depts.length} label="departments" />
        <Stat n={stats.reads} label={`reads · ${HOURS} h`} sub={provSub || null} />
        <span className="spacer" />
        <form className="gis-search" role="search" onSubmit={jump}>
          <label className="visually-hidden" htmlFor="gis-find">
            Find a camera by id or location
          </label>
          <input
            id="gis-find"
            list="gis-cam-list"
            placeholder="Find camera — id or place"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setJumpMsg(null)
            }}
            autoComplete="off"
          />
          <datalist id="gis-cam-list">
            {cams.map((c) => (
              <option key={c.camera_id} value={c.camera_id}>
                {c.location_name || ''}
              </option>
            ))}
          </datalist>
          <button type="submit">Go</button>
          {jumpMsg && (
            <span className="gis-search-msg" role="status">
              {jumpMsg}
            </span>
          )}
        </form>
      </div>

      <div className="gis-body">
        <div className={`gis-map ${zoom >= LABEL_ZOOM ? 'gis-labels' : ''}`}>
          <MapContainer
            ref={setMap}
            center={[22.6, 72.0]}
            zoom={7}
            minZoom={5}
            maxZoom={19}
            scrollWheelZoom
            zoomControl
          >
            <FitBounds points={located.map((c) => [c.lat, c.lon])} maxZoom={12} padding={48} />
            <GisPanes />
            <MapEvents onZoom={setZoom} onOverlay={onOverlay} cursorRef={cursorRef} />
            <LayersControl position="topright" collapsed={false}>
              <BaseLayers tileHandlers={tiles.handlers} onChange={setBasemap} />
              {stats.depts.map(({ dept }) => (
                <LayersControl.Overlay key={dept} name={deptOverlayName(dept)} checked>
                  <LayerGroup>
                    <CameraPins cams={pinsByDept[dept]} selectedId={selId} onSelect={select} />
                  </LayerGroup>
                </LayersControl.Overlay>
              ))}
              {ANALYSIS_LAYERS.map((l) => (
                <LayersControl.Overlay key={l.key} name={l.name} checked={l.checked}>
                  <LayerGroup>
                    {l.key === 'clusters' && (
                      <ClusterHulls hulls={hulls} showLabels={zoom >= BUBBLE_ZOOM - 2} />
                    )}
                    {l.key === 'coverage' && zoom >= WEDGE_ZOOM && <CoverageLayer cams={visible} />}
                    {l.key === 'activity' && <ActivityLayer items={activityItems} hours={HOURS} />}
                    {l.key === 'gaps' && (
                      <GapsLayer offline={gapOffline} isolated={gapIsolated} camsById={byId} />
                    )}
                  </LayerGroup>
                </LayersControl.Overlay>
              ))}
            </LayersControl>
            <ClusterBubbles bubbles={bubbles} onZoom={zoomCluster} />
            <ScaleControl position="bottomright" imperial={false} maxWidth={140} />
          </MapContainer>

          <div className="gis-jumpbar" role="group" aria-label="Zoom to">
            <button type="button" onClick={fitAll} id="gis-fit-all">
              Fit all
            </button>
            {multiClusters.map((cl) => (
              <button
                type="button"
                key={cl.id}
                className="gis-cluster-chip"
                onClick={() => zoomCluster(cl)}
                title={`${plural(cl.members.length, 'camera')} · ${cl.departments.join(', ')}`}
              >
                {cl.name || cl.members[0].camera_id}
                <span className="num">{cl.members.length}</span>
              </button>
            ))}
          </div>

          <MapLegend
            depts={stats.depts}
            counts={stats}
            layers={on}
            hours={HOURS}
            bubbleZoom={BUBBLE_ZOOM}
          />
        </div>

        {selected && (
          <CameraRecord
            cam={selected}
            activity={activity.get(selected.camera_id)}
            hours={HOURS}
            onClose={() => setSelId(null)}
            onZoom={zoomTo}
          />
        )}
      </div>

      <div className="gis-statusbar" aria-live="off">
        <span>
          Pointer{' '}
          <b className="num" ref={cursorRef}>
            move the pointer over the map
          </b>
        </span>
        <span>
          Zoom <b className="num">{zoom}</b>
        </span>
        <span>
          {zoom < BUBBLE_ZOOM
            ? `Clustered view — zoom to ${BUBBLE_ZOOM}+ for individual cameras`
            : `${plural(pinCams.length, 'camera')} in the visible layers`}
        </span>
        <span className="spacer" />
        <span>Basemap: {basemap?.name ?? '—'}</span>
        {tiles.status === 'failed' && (
          <span className="gis-tiles-failed" role="note">
            Basemap tiles need internet — pins and records still work.
          </span>
        )}
      </div>
    </div>
  )
}
