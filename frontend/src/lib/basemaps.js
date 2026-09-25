// The ONE basemap catalogue, shared by the Map page, the Command mini-map
// and the Route map (components/map/BaseLayers.jsx renders it), so every
// map in the platform looks the same.
//
// - Tiles need internet (frontend/CLAUDE.md "Offline venue"): pins, routes
//   and records render regardless; useTileHealth tells a page when no tile
//   has loaded so it can say so.
// - Every TileLayer sends Referer as strict-origin-when-cross-origin (the
//   Leaflet 1.9 `referrerPolicy` option): the page keeps
//   Referrer-Policy: no-referrer, but the OSM tile policy wants a Referer.
// - Every tile host here must be allowed by img-src in backend/app/main.py
//   _CSP — tests/test_csp.py scans frontend/src and fails if one is not.
// - Attribution stays on (OSM data is ODbL; Esri requires it).
// - No CARTO: since at least 25 Sep 2026 every keyless CARTO basemap tile
//   (dark_all, light_all, voyager) is an "API KEY REQUIRED" watermark
//   (ETag wm-…), observed with and without a Referer. The dark and light
//   maps are Esri's keyless Canvas services instead, on the one host the
//   CSP already allows. Canvas has native tiles to z16 (z17+ answers
//   "Map data not yet available"), so it is upscaled beyond that.
// - A `labels` layer (place names) draws in its own pane above the tiles
//   and FOV wedges but below every data path and pin (BaseLayers.jsx).

import { useMemo, useRef, useState } from 'react'

const OSM_ATTR =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
const ESRI_CANVAS_ATTR =
  'Tiles &copy; <a href="https://www.esri.com/">Esri</a> &mdash; Esri, HERE, Garmin, ' +
  '&copy; OpenStreetMap contributors, and the GIS User Community'
const ESRI_IMAGERY_ATTR =
  'Tiles &copy; <a href="https://www.esri.com/">Esri</a> &mdash; Source: Esri, Vantor, ' +
  'Earthstar Geographics, and the GIS User Community'

export const REFERRER_POLICY = 'strict-origin-when-cross-origin'

/** Basemap catalogue: id, control label, and the tile layers it stacks
 *  (a `labels: true` layer goes in the labels pane). */
export const BASEMAPS = [
  {
    id: 'dark',
    name: 'Dark',
    layers: [
      {
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
        maxZoom: 20,
        maxNativeZoom: 16,
        attribution: ESRI_CANVAS_ATTR,
      },
      {
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}',
        maxZoom: 18,
        maxNativeZoom: 16,
        attribution: '',
        labels: true,
      },
    ],
  },
  {
    id: 'streets',
    name: 'Streets · OSM',
    layers: [
      {
        url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
        maxZoom: 19,
        attribution: OSM_ATTR,
      },
    ],
  },
  {
    id: 'light',
    name: 'Light',
    layers: [
      {
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
        maxZoom: 20,
        maxNativeZoom: 16,
        attribution: ESRI_CANVAS_ATTR,
      },
      {
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}',
        maxZoom: 18,
        maxNativeZoom: 16,
        attribution: '',
        labels: true,
      },
    ],
  },
  {
    id: 'satellite',
    name: 'Satellite',
    layers: [
      {
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        maxZoom: 20,
        maxNativeZoom: 19,
        attribution: ESRI_IMAGERY_ATTR,
      },
      {
        // place names and boundaries over the imagery (same host)
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
        maxZoom: 18,
        maxNativeZoom: 16,
        attribution: ESRI_CANVAS_ATTR,
        labels: true,
      },
    ],
  },
]

export const DEFAULT_BASEMAP = 'dark'
const STORE_KEY = 'sentinel.basemap'

/** The viewer's last basemap id (a per-browser convenience — storage may
 *  be blocked or empty; the default then applies). */
export function storedBasemap() {
  try {
    const id = window.localStorage.getItem(STORE_KEY)
    return BASEMAPS.some((b) => b.id === id) ? id : DEFAULT_BASEMAP
  } catch {
    return DEFAULT_BASEMAP
  }
}

/** Remember the viewer's basemap id; a blocked storage keeps it for this
 *  page only. */
export function rememberBasemap(id) {
  try {
    window.localStorage.setItem(STORE_KEY, id)
  } catch {
    /* storage blocked (private window): the choice lasts this page only */
  }
}

/** Tile health for the "tiles need internet" note: 'pending' until the
 *  first tile answers, 'ok' once any tile loaded, 'failed' when tiles
 *  errored and none has loaded. Returns {status, handlers}; pass
 *  `handlers` to <BaseLayers tileHandlers>. */
export function useTileHealth() {
  const [status, setStatus] = useState('pending')
  const loaded = useRef(0)
  const handlers = useMemo(
    () => ({
      tileload: () => {
        loaded.current += 1
        if (loaded.current === 1) setStatus('ok')
      },
      tileerror: () => {
        if (loaded.current === 0) setStatus('failed')
      },
    }),
    []
  )
  return { status, handlers }
}
