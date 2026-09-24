// IST display through ONE formatter (frontend/CLAUDE.md; old defect D13:
// never slice() an ISO string, never show raw UTC). Storage stays UTC.

const full = new Intl.DateTimeFormat('en-IN', {
  timeZone: 'Asia/Kolkata',
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
})

const timeOnly = new Intl.DateTimeFormat('en-IN', {
  timeZone: 'Asia/Kolkata',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
})

/** Date + time in IST, e.g. "24 Sep 2026, 21:14:09 IST". '—' for empty,
 *  the raw value for anything unparseable (visible, never invented). */
export function formatTs(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return String(iso)
  return `${full.format(d)} IST`
}

/** Time-of-day in IST, e.g. "21:14:09" — for dense tables. */
export function formatTimeIST(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return String(iso)
  return timeOnly.format(d)
}
