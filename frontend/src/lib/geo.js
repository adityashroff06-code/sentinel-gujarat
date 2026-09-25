// GIS geometry for the Map page (Model 1): great-circle distance, field-of-
// view wedges, single-linkage camera clusters and their hulls. Pure
// functions over [lat, lon] pairs — no Leaflet, no React, no network.

const EARTH_RADIUS_KM = 6371.0088
const toRad = (d) => (d * Math.PI) / 180
const toDeg = (r) => (r * 180) / Math.PI

/** Cameras closer than this (km) share a cluster — single linkage. */
export const CLUSTER_KM = 15

/** Field-of-view values used when the registry has none (the sandbox
 *  catalogue carries no bearing / FOV / range): shown as "assumed". */
export const FOV_DEFAULTS = { bearing: 0, fov: 70, range: 80 }

const finite = (v) => typeof v === 'number' && Number.isFinite(v)

/** True when a camera row has usable coordinates. */
export const isLocated = (c) => finite(c?.lat) && finite(c?.lon)

/** Great-circle distance in km between two [lat, lon] points. */
export function haversineKm([lat1, lon1], [lat2, lon2]) {
  const dp = toRad(lat2 - lat1)
  const dl = toRad(lon2 - lon1)
  const a =
    Math.sin(dp / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dl / 2) ** 2
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(a)))
}

/** The point `distanceM` metres from [lat, lon] along `bearingDeg`
 *  (0 = north, clockwise). */
export function destination([lat, lon], bearingDeg, distanceM) {
  const d = distanceM / 1000 / EARTH_RADIUS_KM
  const t = toRad(bearingDeg)
  const p1 = toRad(lat)
  const p2 = Math.asin(Math.sin(p1) * Math.cos(d) + Math.cos(p1) * Math.sin(d) * Math.cos(t))
  const l2 =
    toRad(lon) +
    Math.atan2(Math.sin(t) * Math.sin(d) * Math.cos(p1), Math.cos(d) - Math.sin(p1) * Math.sin(p2))
  return [toDeg(p2), ((toDeg(l2) + 540) % 360) - 180]
}

/** A camera's field of view: {bearing, fov, range, assumed} — registry
 *  values where present, FOV_DEFAULTS otherwise (assumed = any default). */
export function fieldOfView(cam) {
  const bearing = finite(cam.bearing_deg) ? cam.bearing_deg : null
  const fov = finite(cam.fov_deg) && cam.fov_deg > 0 ? cam.fov_deg : null
  const range = finite(cam.range_m) && cam.range_m > 0 ? cam.range_m : null
  return {
    bearing: bearing ?? FOV_DEFAULTS.bearing,
    fov: fov ?? FOV_DEFAULTS.fov,
    range: range ?? FOV_DEFAULTS.range,
    assumed: bearing == null || fov == null || range == null,
  }
}

/** The FOV wedge polygon ([lat, lon] ring) for a camera: its position plus
 *  an arc of `range` metres across `fov` degrees centred on `bearing`. */
export function fovWedge(cam, view = fieldOfView(cam), steps = 18) {
  const origin = [cam.lat, cam.lon]
  const full = view.fov >= 360
  const start = full ? 0 : view.bearing - view.fov / 2
  const sweep = full ? 360 : view.fov
  const arc = []
  for (let i = 0; i <= steps; i += 1) {
    arc.push(destination(origin, start + (sweep * i) / steps, view.range))
  }
  return full ? arc : [origin, ...arc]
}

/** Convex hull (Andrew's monotone chain) of [lat, lon] points, computed on
 *  a local equirectangular projection so longitude is not over-weighted.
 *  Returns the hull ring counter-clockwise, without repeating the start. */
export function convexHull(points) {
  if (points.length < 3) return points.slice()
  const lat0 = toRad(points.reduce((a, p) => a + p[0], 0) / points.length)
  const k = Math.cos(lat0)
  const pts = points
    .map((p) => ({ x: p[1] * k, y: p[0], p }))
    .sort((a, b) => a.x - b.x || a.y - b.y)
  const cross = (o, a, b) => (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x)
  const lower = []
  for (const q of pts) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], q) <= 0) lower.pop()
    lower.push(q)
  }
  const upper = []
  for (let i = pts.length - 1; i >= 0; i -= 1) {
    const q = pts[i]
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], q) <= 0) upper.pop()
    upper.push(q)
  }
  upper.pop()
  lower.pop()
  return [...lower, ...upper].map((q) => q.p)
}

/** Hull of the points each padded by a `bufferKm` circle — a rounded
 *  outline that also works for one or two cameras. */
export function bufferedHull(points, bufferKm, steps = 16) {
  const ring = []
  for (const p of points) {
    for (let i = 0; i < steps; i += 1) {
      ring.push(destination(p, (360 * i) / steps, bufferKm * 1000))
    }
  }
  return convexHull(ring)
}

// A few Gujarat cities, used ONLY to name a cluster by its nearest city
// ("near Junagadh") — never to place a camera. Public, approximate centres.
const PLACES = [
  ['Ahmedabad', 23.0225, 72.5714], ['Gandhinagar', 23.2156, 72.6369],
  ['Rajkot', 22.3039, 70.8022], ['Junagadh', 21.5222, 70.4579],
  ['Surat', 21.1702, 72.8311], ['Vadodara', 22.3072, 73.1812],
  ['Navsari', 20.9467, 72.952], ['Bilimora', 20.769, 72.961],
  ['Bhavnagar', 21.7645, 72.1519],
  ['Jamnagar', 22.4707, 70.0577], ['Gandhidham', 23.0753, 70.1337],
  ['Bhuj', 23.242, 69.6669], ['Patan', 23.8493, 72.1266],
  ['Palanpur', 24.1725, 72.4381], ['Mehsana', 23.588, 72.3693],
  ['Veraval', 20.9077, 70.3679], ['Porbandar', 21.6417, 69.6293],
  ['Anand', 22.5645, 72.9289], ['Bharuch', 21.7051, 72.9959],
  ['Valsad', 20.5992, 72.9342], ['Amreli', 21.6032, 71.2221],
  ['Himmatnagar', 23.598, 72.966], ['Godhra', 22.7788, 73.6143],
  ['Morbi', 22.8173, 70.8378], ['Surendranagar', 22.7201, 71.6495],
]

/** Name of the nearest listed city to [lat, lon] (for labels only). */
export function nearestPlace(point) {
  let best = null
  let bestKm = Infinity
  for (const [name, lat, lon] of PLACES) {
    const km = haversineKm(point, [lat, lon])
    if (km < bestKm) {
      best = name
      bestKm = km
    }
  }
  return bestKm < 80 ? best : null
}

/** Single-linkage clusters of located cameras: two cameras closer than
 *  `thresholdKm` share a cluster, transitively. Returns clusters sorted
 *  largest first, each {id, name, members, centroid, departments[]}. */
export function clusterCameras(cams, thresholdKm = CLUSTER_KM) {
  const pts = cams.filter(isLocated)
  const parent = pts.map((_, i) => i)
  const find = (i) => {
    while (parent[i] !== i) {
      parent[i] = parent[parent[i]]
      i = parent[i]
    }
    return i
  }
  for (let i = 0; i < pts.length; i += 1) {
    for (let j = i + 1; j < pts.length; j += 1) {
      if (haversineKm([pts[i].lat, pts[i].lon], [pts[j].lat, pts[j].lon]) <= thresholdKm) {
        const a = find(i)
        const b = find(j)
        if (a !== b) parent[a] = b
      }
    }
  }
  const groups = new Map()
  pts.forEach((c, i) => {
    const root = find(i)
    if (!groups.has(root)) groups.set(root, [])
    groups.get(root).push(c)
  })
  return [...groups.values()]
    .map((members) => {
      members.sort((a, b) => String(a.camera_id).localeCompare(String(b.camera_id)))
      const centroid = [
        members.reduce((a, c) => a + c.lat, 0) / members.length,
        members.reduce((a, c) => a + c.lon, 0) / members.length,
      ]
      const departments = [...new Set(members.map((c) => c.department || 'Unknown'))]
      return {
        id: `cl-${members[0].camera_id}`,
        name: nearestPlace(centroid),
        members,
        centroid,
        departments,
      }
    })
    .sort((a, b) => b.members.length - a.members.length || a.id.localeCompare(b.id))
}

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`

/** Outline geometry for every multi-camera cluster: the hull of its
 *  cameras padded by `bufferKm` (so a pair still draws an area) and the
 *  hull's northernmost point, where the label sits clear of the count
 *  bubble. Returns [{id, ring, top, label}]. */
export function clusterHullShapes(clusters, bufferKm) {
  return clusters
    .filter((cl) => cl.members.length > 1)
    .map((cl) => {
      const ring = bufferedHull(
        cl.members.map((c) => [c.lat, c.lon]),
        bufferKm
      )
      const top = ring.reduce((a, p) => (p[0] > a[0] ? p : a), ring[0])
      const label =
        `${cl.name ? `${cl.name} · ` : ''}${plural(cl.members.length, 'camera')} · ` +
        plural(cl.departments.length, 'department')
      return { id: `${cl.id}-${cl.members.length}`, ring, top, label }
    })
}

/** "23.05120° N, 72.55600° E" — five decimals is ~1 m. */
export function formatLatLon(lat, lon, digits = 5) {
  if (!finite(lat) || !finite(lon)) return '—'
  const ns = lat >= 0 ? 'N' : 'S'
  const ew = lon >= 0 ? 'E' : 'W'
  return `${Math.abs(lat).toFixed(digits)}° ${ns}, ${Math.abs(lon).toFixed(digits)}° ${ew}`
}
