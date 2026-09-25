import { useEffect, useState } from 'react'
import { LayerGroup, LayersControl, Pane, TileLayer, useMapEvents } from 'react-leaflet'
import { BASEMAPS, REFERRER_POLICY, rememberBasemap, storedBasemap } from '../../lib/basemaps.js'

// The basemap entries of a <LayersControl> — the Map page, the Command
// mini-map and the Route map all render this, so the platform has one
// look (catalogue, referrer policy, CSP and CARTO notes: lib/basemaps.js).
// The viewer's pick is remembered per browser and restored on every map,
// and written to the map container as data-basemap so CSS can switch
// label colours for light basemaps. A basemap's place-name layer draws in
// its own pane at z 390: above the tiles (200), cluster hulls (350) and
// FOV wedges (380), below every data path in Leaflet's overlay pane (400,
// e.g. the Route pins), activity (420), gaps (430), markers (600) and
// tooltips (650) — names stay readable, data stays on top.

const LABELS_PANE_Z = 390

function Tiles({ basemap, spec, handlers }) {
  return (
    <TileLayer
      url={spec.url}
      subdomains={spec.subdomains ?? 'abc'}
      maxZoom={spec.maxZoom}
      maxNativeZoom={spec.maxNativeZoom}
      attribution={spec.attribution}
      referrerPolicy={REFERRER_POLICY}
      className={`${spec.labels ? 'basemap-labels' : 'basemap-tiles'} basemap-${basemap}`}
      eventHandlers={handlers}
    />
  )
}

/** Persists the basemap the viewer picks, tags the map container with it
 *  and reports it upward. */
function BasemapMemory({ initial, onChange }) {
  const map = useMapEvents({
    baselayerchange: (e) => {
      const hit = BASEMAPS.find((b) => b.name === e.name)
      if (hit) {
        rememberBasemap(hit.id)
        map.getContainer().dataset.basemap = hit.id
        onChange?.(hit)
      }
    },
  })
  useEffect(() => {
    map.getContainer().dataset.basemap = initial
  }, [map, initial])
  return null
}

/** Render inside a <LayersControl>. `tileHandlers` come from
 *  useTileHealth(); `onChange(basemap)` fires when the viewer switches. */
export default function BaseLayers({ tileHandlers, onChange }) {
  const [initial] = useState(storedBasemap)
  return (
    <>
      {BASEMAPS.map((b) => (
        <LayersControl.BaseLayer key={b.id} name={b.name} checked={b.id === initial}>
          <LayerGroup>
            {b.layers.map((spec) =>
              spec.labels ? (
                <Pane
                  key={spec.url}
                  name={`basemap-labels-${b.id}`}
                  style={{ zIndex: LABELS_PANE_Z, pointerEvents: 'none' }}
                >
                  <Tiles basemap={b.id} spec={spec} handlers={tileHandlers} />
                </Pane>
              ) : (
                <Tiles key={spec.url} basemap={b.id} spec={spec} handlers={tileHandlers} />
              )
            )}
          </LayerGroup>
        </LayersControl.BaseLayer>
      ))}
      <BasemapMemory initial={initial} onChange={onChange} />
    </>
  )
}
