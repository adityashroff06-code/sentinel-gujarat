import { useEffect } from 'react'
import { useMap } from 'react-leaflet'
import L from 'leaflet'

// Fits the map view to the given [lat, lon] points whenever they change.
// Renders nothing — it only drives the Leaflet map it is mounted inside.
// Ported from D:\projects\Sentinel_Repo\ui\src\components\FitBounds.jsx
// (F52); the change-detection key is computed outside the effect so the
// dependency list is static.
export default function FitBounds({ points, maxZoom = 12, padding = 40 }) {
  const map = useMap()
  const key = JSON.stringify(points)
  useEffect(() => {
    const pts = (points || []).filter(
      (p) => Number.isFinite(p?.[0]) && Number.isFinite(p?.[1])
    )
    if (!pts.length) return
    map.fitBounds(L.latLngBounds(pts), { maxZoom, padding: [padding, padding] })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, key, maxZoom, padding])
  return null
}
