import { useEffect, useState } from 'react'
import { onStatus } from '../lib/api.js'

const LABELS = {
  network: 'offline',
  auth: 'auth',
  forbidden: 'denied',
  'not-found': 'missing',
  conflict: 'conflict',
  validation: 'invalid',
  'rate-limit': 'throttled',
  server: 'error',
}

// Global connection/status strip (frontend/CLAUDE.md: no silent failure —
// every data-layer error is visible here; a successful call clears it).
export default function StatusStrip() {
  const [event, setEvent] = useState(null)
  useEffect(() => onStatus(setEvent), [])
  if (!event) return null
  return (
    <div className="status-strip" role="alert">
      <span className="kind">{LABELS[event.kind] || 'error'}</span>
      <span className="msg">{event.message}</span>
      <button className="ghost" onClick={() => setEvent(null)} aria-label="Dismiss">
        ×
      </button>
    </div>
  )
}
