import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'
import { api, deptColor } from '../lib/api.js'
import { roleAtLeast, useSession } from '../lib/session.js'
import { formatTs } from '../lib/time.js'
import { MatchChip, ProvenanceBadge, SeverityWord } from './Badges.jsx'

// One alert card — used by the Command feed and the Alerts page.
// Ported from the card markup of D:\projects\Sentinel_Repo\ui\src\pages\
// Alerts.jsx (F52), rebuilt on tokens and with D13 fixed: every severity
// value is styled incl. critical, times render in IST, the acknowledge
// result is applied from the real response, and the route link exists
// only for kind='watchlist' (zone alerts have no plate to trace).
// S7.2 (F73): when the alert stored an evidence frame, the thumbnail IS
// that frame, and clicking it opens a lightbox with the full frame, its
// audit-trail SHA-256 and why it was stored.

/** The evidence lightbox: the full annotated frame, its SHA-256
 *  (copyable), and the storage justification (F73's governing rule —
 *  video becomes permanent only where a logged watchlist match says so).
 *  Rendered into document.body: inside a card it inherited the acked
 *  card's opacity and stacking context, so it showed faded and the
 *  mini-map's Leaflet panes painted over it. */
export function EvidenceLightbox({ alert: a, onClose }) {
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  async function copySha() {
    try {
      await navigator.clipboard.writeText(a.evidence_sha256)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // clipboard unavailable (permissions, http) — the hash stays selectable
    }
  }

  return createPortal(
    <div
      className="evidence-lightbox"
      role="dialog"
      aria-modal="true"
      aria-label={`Evidence frame for ${a.alert_id}`}
      onClick={onClose}
    >
      <div className="evidence-frame" onClick={(e) => e.stopPropagation()}>
        <img src={a.evidence_url} alt={`evidence frame for ${a.plate || a.alert_id}`} />
        <div className="evidence-meta">
          <span className="evidence-why">
            stored because: watchlist match (<b>{a.match_type}</b>) ·{' '}
            <span className="mono">{a.alert_id}</span>
          </span>
          <ProvenanceBadge clockSource={a.clock_source} />
          {a.evidence_sha256 && (
            <span className="evidence-sha">
              SHA-256 <code className="mono">{a.evidence_sha256}</code>
              <button type="button" className="chip" onClick={copySha}>
                {copied ? 'copied' : 'copy'}
              </button>
            </span>
          )}
          <button type="button" className="chip evidence-close" onClick={onClose}>
            close
          </button>
        </div>
      </div>
    </div>,
    document.body
  )
}

export default function AlertCard({ alert: a, compact = false, onAck }) {
  const session = useSession()
  const canAck = roleAtLeast(session?.role, 'evaluator')
  const [lightbox, setLightbox] = useState(false)

  async function ack() {
    try {
      const updated = await api.ack(a.alert_id)
      onAck?.(updated)
    } catch {
      // already surfaced on the global status strip by the data layer
    }
  }

  const isZone = a.kind === 'zone'
  const title = isZone ? `ZONE ${a.zone_id ?? ''}`.trim() : a.plate
  const thumb = a.evidence_url || a.crop_url // demo rows fall back to the crop

  return (
    <div
      className={`alert-card sev-${a.severity || 'low'} ${a.acknowledged_at ? 'acked' : ''}`}
      data-alert-id={a.alert_id}
    >
      {thumb ? (
        a.evidence_url ? (
          <button
            type="button"
            className="evidence-thumb-btn"
            onClick={() => setLightbox(true)}
            title="open the evidence frame"
          >
            <img className="crop-thumb evidence" src={thumb} alt={`evidence for ${title}`} />
          </button>
        ) : (
          <img className="crop-thumb" src={thumb} alt={`crop for ${title}`} />
        )
      ) : (
        <div className="crop-thumb placeholder" aria-hidden="true" />
      )}
      <div className="alert-body">
        <div className="alert-title">
          <b className={isZone ? 'mono' : 'plate'}>{title}</b>
          <SeverityWord severity={a.severity} />
          {a.category && <span className="muted">{a.category}</span>}
          <MatchChip matchType={a.match_type} distance={a.match_distance} />
          <ProvenanceBadge clockSource={a.clock_source} />
        </div>
        <div className="alert-meta muted">
          <span className="mono">{a.camera_id}</span>
          {a.location_name && <span>{a.location_name}</span>}
          {a.department && (
            <span style={{ color: deptColor(a.department) }}>{a.department}</span>
          )}
          <span className="num">{formatTs(a.fired_at)}</span>
          {a.acknowledged_at && (
            <span>
              ack&apos;d by {a.acknowledged_by || '?'} · {formatTs(a.acknowledged_at)}
            </span>
          )}
        </div>
      </div>
      {!compact && (
        <div className="alert-actions">
          {!isZone && a.plate && (
            <Link className="chip" to={`/route/${encodeURIComponent(a.plate)}`}>
              route ›
            </Link>
          )}
          {canAck && !a.acknowledged_at && (
            <button className="chip ack" onClick={ack}>
              ack
            </button>
          )}
        </div>
      )}
      {lightbox && <EvidenceLightbox alert={a} onClose={() => setLightbox(false)} />}
    </div>
  )
}
