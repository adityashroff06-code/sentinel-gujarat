// Camera pins and cluster bubbles as Leaflet divIcons — HTML, so every
// colour comes from tokens.css through CSS classes (Leaflet's SVG
// presentation attributes cannot resolve var()). Icons are cached by their
// visual key, so a poll that changes nothing never re-creates a marker.

import L from 'leaflet'
import { DEPT_COLORS } from './api.js'

/** The shared department palette's keys, in legend order. */
export const DEPARTMENTS = Object.keys(DEPT_COLORS)

/** A department normalised to the palette (anything else is Unknown). */
export const deptKey = (d) => (d && Object.hasOwn(DEPT_COLORS, d) ? d : 'Unknown')

/** CSS class slug for a department: dept-police, dept-gsrtc, … */
export const deptClass = (d) => `dept-${deptKey(d).toLowerCase()}`

/** 'sandbox' for the organisers' catalogue cameras, 'local' for our own
 *  feeds and anything onboarded by hand, CSV or API. */
export const feedKind = (cam) => (cam?.source === 'catalogue' ? 'sandbox' : 'local')

/** online | degraded | offline | unknown */
export const healthKey = (h) =>
  h === 'online' || h === 'degraded' || h === 'offline' ? h : 'unknown'

export const isAnalysed = (cam) => cam?.fps_tier === 'active'

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }
/** HTML-escape a string for divIcon markup and layer-control labels. */
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (ch) => ESC[ch])

const PIN_BOX = 22
const iconCache = new Map()

/** The divIcon for one camera pin: shape by feed kind (circle = sandbox,
 *  diamond = local), colour by department, opacity by health, a ring for
 *  the analysed (active) tier, an id label shown at street zoom. */
export function pinIcon(cam, selected = false) {
  const kind = feedKind(cam)
  const health = healthKey(cam.health)
  const tier = isAnalysed(cam) ? 'tier-active' : 'tier-registered'
  const key = [cam.camera_id, kind, deptKey(cam.department), health, tier, selected].join('|')
  const hit = iconCache.get(key)
  if (hit) return hit
  const id = esc(cam.camera_id)
  const spoken = esc(
    `${cam.camera_id}, ${deptKey(cam.department)}, ${health}` +
      `${isAnalysed(cam) ? ', analysed' : ''}${kind === 'local' ? ', local feed' : ''}`
  )
  const icon = L.divIcon({
    className: 'cam-pin-icon',
    html:
      `<span class="cam-pin cam-pin--${kind} ${deptClass(cam.department)} health-${health} ${tier}` +
      `${selected ? ' is-selected' : ''}" data-cam="${id}">` +
      `<span class="cam-pin-dot" aria-hidden="true"></span>` +
      `<span class="cam-pin-label" aria-hidden="true">${id}</span>` +
      `<span class="visually-hidden">${spoken}</span></span>`,
    iconSize: [PIN_BOX, PIN_BOX],
    iconAnchor: [PIN_BOX / 2, PIN_BOX / 2],
  })
  iconCache.set(key, icon)
  return icon
}

/** Bubble diameter (px) for a cluster of n cameras. */
export const bubbleSize = (n) => Math.round(Math.min(64, 30 + 4.2 * Math.sqrt(n)))

/** The divIcon for a cluster count bubble: the count in the middle, a
 *  ring split by department share, and — when the Gaps layer is on — a
 *  badge with the number of offline / degraded / unknown-health cameras. */
export function bubbleIcon({ id, name, members, gapCount = 0 }) {
  const n = members.length
  const counts = new Map()
  for (const c of members) counts.set(deptKey(c.department), (counts.get(deptKey(c.department)) || 0) + 1)
  const slices = DEPARTMENTS.filter((d) => counts.has(d))
  const key = [id, n, slices.map((d) => `${d}:${counts.get(d)}`).join(','), gapCount].join('|')
  const hit = iconCache.get(key)
  if (hit) return hit
  let at = 0
  const stops = slices.map((d) => {
    const from = at
    at += (counts.get(d) / n) * 100
    return `var(--dept-${d.toLowerCase()}) ${from.toFixed(2)}% ${at.toFixed(2)}%`
  })
  const size = bubbleSize(n)
  const label = esc(
    `${name ? `${name} cluster` : 'Cluster'}: ${n} cameras, ${slices.length} ` +
      `department${slices.length === 1 ? '' : 's'}. Zoom in.`
  )
  const icon = L.divIcon({
    className: 'cl-bubble-icon',
    html:
      `<span class="cl-bubble" data-count="${n}" style="width:${size}px;height:${size}px;` +
      `background:conic-gradient(${stops.join(',')})">` +
      `<span class="cl-bubble-core" aria-hidden="true">${n}</span>` +
      (gapCount > 0
        ? `<span class="cl-bubble-gap" aria-hidden="true">${gapCount}</span>`
        : '') +
      `<span class="visually-hidden">${label}</span></span>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  })
  iconCache.set(key, icon)
  return icon
}
