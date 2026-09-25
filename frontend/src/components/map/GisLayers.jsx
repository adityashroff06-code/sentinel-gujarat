import { useCallback, useEffect, useMemo, useState } from 'react'
import L from 'leaflet'
import { Circle, CircleMarker, Marker, Pane, Polygon, Tooltip, useMap, useMapEvents } from 'react-leaflet'
import { clusterCameras, fieldOfView, formatLatLon, fovWedge, isLocated } from '../../lib/geo.js'
import { bubbleIcon, deptClass, deptKey, feedKind, healthKey, isAnalysed, pinIcon } from '../../lib/pins.js'
import { formatTs } from '../../lib/time.js'

// The GIS layers of the Map page (Model 1). Each overlay path carries a
// className and is coloured by tokens.css (Leaflet's SVG presentation
// attributes cannot resolve var(); CSS outranks them). Stacking, bottom to
// top: basemap (200) → cluster hulls (350) → coverage wedges (380) →
// basemap place names (390, BaseLayers.jsx) → activity (420) → gaps (430)
// → camera pins and cluster bubbles (marker pane, 600) → tooltips (650).

/** The custom panes the overlays draw into, created once per map. */
export function GisPanes() {
  return (
    <>
      <Pane name="gis-clusters" style={{ zIndex: 350 }} />
      <Pane name="gis-coverage" style={{ zIndex: 380 }} />
      <Pane name="gis-activity" style={{ zIndex: 420 }} />
      <Pane name="gis-gaps" style={{ zIndex: 430 }} />
    </>
  )
}

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`

// Leaflet makes a keyboard-focusable marker role="button" but a divIcon
// gets no Enter-to-click of its own: Enter or Space activates it here.
const activates = (e) => e.originalEvent?.key === 'Enter' || e.originalEvent?.key === ' '

/** One marker per camera: shape by feed kind, colour by department,
 *  opacity by health, a ring for the analysed tier (lib/pins.js). */
export function CameraPins({ cams, selectedId, onSelect }) {
  return cams.map((c) => (
    <Marker
      key={c.camera_id}
      position={[c.lat, c.lon]}
      icon={pinIcon(c, c.camera_id === selectedId)}
      zIndexOffset={c.camera_id === selectedId ? 1000 : isAnalysed(c) ? 200 : 0}
      keyboard
      eventHandlers={{
        click: () => onSelect(c.camera_id),
        keydown: (e) => activates(e) && onSelect(c.camera_id),
      }}
    >
      <Tooltip direction="top" offset={[0, -10]} className="gis-tip">
        <b className="mono">{c.camera_id}</b> · {deptKey(c.department)}
        <br />
        {c.location_name || 'unnamed location'}
        <br />
        <span className={`tip-health health-${healthKey(c.health)}`}>{healthKey(c.health)}</span>
        {isAnalysed(c) ? ' · analysed (ANPR)' : ' · view only'}
        {feedKind(c) === 'local' ? ' · local feed' : ' · sandbox grid'}
      </Tooltip>
    </Marker>
  ))
}

/** Count bubbles for clusters at low zoom; click zooms to the cluster. */
export function ClusterBubbles({ bubbles, onZoom }) {
  return bubbles.map((b) => (
    <Marker
      key={b.id}
      position={b.centroid}
      icon={bubbleIcon(b)}
      keyboard
      zIndexOffset={500}
      eventHandlers={{
        click: () => onZoom(b),
        keydown: (e) => activates(e) && onZoom(b),
      }}
    >
      <Tooltip direction="top" offset={[0, -18]} className="gis-tip">
        <b>{b.name ? `Near ${b.name}` : 'Cluster'}</b> · {plural(b.members.length, 'camera')} ·{' '}
        {plural(b.departments.length, 'department')}
        <br />
        {b.departments.join(' · ')}
        <br />
        <span className="muted">Click to zoom in</span>
      </Tooltip>
    </Marker>
  ))
}

// Path styles are module constants (react-leaflet re-applies pathOptions
// whenever the object changes). Colours are NOT here: `className` is a
// top-level prop because Leaflet reads it only when it first draws the
// path (setStyle never touches the class), so every class that can change
// is also part of the element's key.
const WEDGE_STYLE = { weight: 1 }
const ACTIVITY_STYLE = { weight: 2 }
const HULL_STYLE = { weight: 1.5 }
const HALO_STYLE = { weight: 2, dashArray: '3 3' }
const ISOLATED_STYLE = { weight: 1.5, dashArray: '6 6' }

/** Field-of-view wedges from bearing / FOV / range — registry values, or
 *  the stated defaults when the catalogue carries none ("assumed"). */
export function CoverageLayer({ cams }) {
  return cams.map((c) => {
    const view = fieldOfView(c)
    const cls = `gis-wedge ${deptClass(c.department)}${view.assumed ? ' is-assumed' : ''}`
    return (
      <Polygon
        key={`${c.camera_id}-${view.bearing}-${view.fov}-${view.range}-${cls}`}
        positions={fovWedge(c, view)}
        pane="gis-coverage"
        className={cls}
        pathOptions={WEDGE_STYLE}
      >
        <Tooltip sticky className="gis-tip">
          <b className="mono">{c.camera_id}</b> field of view
          <br />
          bearing {Math.round(view.bearing)}° · FOV {Math.round(view.fov)}° · range{' '}
          {Math.round(view.range)} m
          <br />
          {view.assumed ? (
            <span className="tip-assumed">assumed — the registry has no surveyed value</span>
          ) : (
            <span className="muted">from the registry</span>
          )}
        </Tooltip>
      </Polygon>
    )
  })
}

/** Radius (px) of an activity circle for n reads. */
const activityRadius = (n) => Math.min(38, 9 + 4.5 * Math.sqrt(n))

/** Activity circles sized by plate reads in the window. `items` are
 *  {key, center, label, sightings, plates, alerts, lastSeen, byProv};
 *  `plates` is null where no exact distinct count exists (a bubble whose
 *  reads span several cameras) and is then left out, never summed. */
export function ActivityLayer({ items, hours }) {
  return items.map((a) => (
    <CircleMarker
      key={`${a.key}-${a.alerts > 0}`}
      center={a.center}
      radius={activityRadius(a.sightings)}
      pane="gis-activity"
      className={`gis-activity${a.alerts > 0 ? ' has-alerts' : ''}`}
      pathOptions={ACTIVITY_STYLE}
    >
      <Tooltip direction="right" offset={[12, 0]} className="gis-tip">
        <b>{a.label}</b> · last {hours} h
        <br />
        {plural(a.sightings, 'plate read')} ·{' '}
        {a.plates != null && <>{plural(a.plates, 'distinct plate')} · </>}
        {plural(a.alerts, 'alert')}
        {Object.keys(a.byProv).length > 0 && (
          <>
            <br />
            {Object.entries(a.byProv)
              .map(([p, n]) => `${n} ${p}`)
              .join(' · ')}
          </>
        )}
        {a.lastSeen && (
          <>
            <br />
            last read {formatTs(a.lastSeen)}
          </>
        )}
      </Tooltip>
    </CircleMarker>
  ))
}

/** Cluster outlines labelled "N cameras · M departments" (shapes from
 *  geo.clusterHullShapes, memoised by the page). */
export function ClusterHulls({ hulls, showLabels }) {
  return hulls.map((h) => (
    <Polygon
      key={h.id}
      positions={h.ring}
      pane="gis-clusters"
      interactive={false}
      className="gis-hull"
      pathOptions={HULL_STYLE}
    >
      {showLabels && (
        <Tooltip permanent direction="top" position={h.top} className="gis-hull-label" opacity={1}>
          {h.label}
        </Tooltip>
      )}
    </Polygon>
  ))
}

/** Coverage gaps from GET /api/cameras/gap-analysis: a halo round every
 *  offline / degraded / unknown-health camera pin on screen, and a dashed
 *  radius round every isolated camera (no neighbour within radius_km). */
export function GapsLayer({ offline, isolated, camsById }) {
  return (
    <>
      {offline.map((g) => {
        const c = camsById.get(g.camera_id)
        if (!c) return null
        const h = healthKey(g.health)
        return (
          <CircleMarker
            key={`off-${g.camera_id}-${h}`}
            center={[c.lat, c.lon]}
            radius={14}
            pane="gis-gaps"
            className={`gis-gap-halo health-${h}`}
            pathOptions={HALO_STYLE}
          >
            <Tooltip direction="top" offset={[0, -12]} className="gis-tip">
              <b className="mono">{g.camera_id}</b> — {h === 'unknown' ? 'health unknown' : h}
              <br />
              last health check {formatTs(g.last_seen)}
            </Tooltip>
          </CircleMarker>
        )
      })}
      {isolated.map((g) => {
        const c = camsById.get(g.camera_id)
        if (!c) return null
        return (
          <Circle
            key={`iso-${g.camera_id}-${g.radius_km}`}
            center={[c.lat, c.lon]}
            radius={g.radius_km * 1000}
            pane="gis-gaps"
            className="gis-gap-isolated"
            pathOptions={ISOLATED_STYLE}
          >
            <Tooltip sticky className="gis-tip">
              <b className="mono">{g.camera_id}</b> — isolated coverage
              <br />
              no other camera within {g.radius_km} km; nearest is {g.nearest_neighbour_km} km away
            </Tooltip>
          </Circle>
        )
      })}
    </>
  )
}

/** The whole network at a glance (the Command mini-map): the Map page's
 *  pins and cluster bubbles, bubbles below `bubbleZoom`; a bubble zooms
 *  in, a pin calls `onPin(camera_id)`. */
export function NetworkOverview({ cams, onPin, bubbleZoom = 9 }) {
  const map = useMap()
  const [zoom, setZoom] = useState(() => map.getZoom())
  useMapEvents({ zoomend: () => setZoom(map.getZoom()) })
  const clusters = useMemo(() => clusterCameras(cams), [cams])
  const { pins, bubbles } = useMemo(() => {
    if (zoom >= bubbleZoom) return { pins: cams.filter(isLocated), bubbles: [] }
    return {
      pins: clusters.filter((cl) => cl.members.length === 1).map((cl) => cl.members[0]),
      bubbles: clusters.filter((cl) => cl.members.length > 1),
    }
  }, [zoom, bubbleZoom, cams, clusters])
  const zoomInto = useCallback(
    (b) =>
      map.fitBounds(L.latLngBounds(b.members.map((c) => [c.lat, c.lon])), {
        padding: [24, 24],
        maxZoom: 14,
      }),
    [map]
  )
  return (
    <>
      <CameraPins cams={pins} onSelect={onPin} />
      <ClusterBubbles bubbles={bubbles} onZoom={zoomInto} />
    </>
  )
}

/** Map event bridge: zoom and layer-control changes up to React state;
 *  the cursor readout written straight into `cursorRef` (no re-render
 *  per mouse move). */
export function MapEvents({ onZoom, onOverlay, cursorRef }) {
  const map = useMap()
  useEffect(() => {
    onZoom(map.getZoom())
  }, [map, onZoom])
  useMapEvents({
    zoomend: () => onZoom(map.getZoom()),
    overlayadd: (e) => onOverlay(e.name, true),
    overlayremove: (e) => onOverlay(e.name, false),
    mousemove: (e) => {
      if (cursorRef.current) {
        cursorRef.current.textContent = formatLatLon(e.latlng.lat, e.latlng.lng)
      }
    },
    mouseout: () => {
      if (cursorRef.current) cursorRef.current.textContent = 'move the pointer over the map'
    },
  })
  return null
}
