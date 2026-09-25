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
export default function AlertCard({ alert: a, compact = false, onAck }) {
  const session = useSession()
  const canAck = roleAtLeast(session?.role, 'evaluator')

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

  return (
    <div
      className={`alert-card sev-${a.severity || 'low'} ${a.acknowledged_at ? 'acked' : ''}`}
      data-alert-id={a.alert_id}
    >
      {a.crop_url ? (
        <img className="crop-thumb" src={a.crop_url} alt={`crop for ${title}`} />
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
    </div>
  )
}
