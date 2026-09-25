import AlertCard from '../components/AlertCard.jsx'
import { useAlertStream } from '../lib/poll.js'

// Alerts — the live alert panel over SSE, newest first, severity-coded
// for EVERY severity value including critical (old defect D13), each
// card with crop, camera, department, IST timestamp, category, match
// type and a provenance badge; acknowledge persists through the real
// POST /ack response; the route link exists only for kind='watchlist';
// the list is capped at 200 by the shared stream hook.
// Ported from D:\projects\Sentinel_Repo\ui\src\pages\Alerts.jsx (F52):
// the SSE wiring moved into lib/poll.js useAlertStream (shared with
// Command), and the new backend streams full alert rows for both kinds,
// so the old client-side zone re-mapping is gone.
export default function Alerts() {
  const { alerts, loaded, stream, applyAck } = useAlertStream(200)

  return (
    <div className="page">
      <div className="card">
        <h2>
          Live alerts{' '}
          <span className={`count stream-${stream}`}>
            {stream === 'live' ? 'streaming' : stream}
          </span>
        </h2>
        {!loaded && (
          <div className="skeleton-rows" aria-label="Loading alerts">
            {[0, 1, 2].map((i) => (
              <div key={i} className="skeleton" style={{ height: 64 }} />
            ))}
          </div>
        )}
        {loaded && alerts.length === 0 && (
          <div className="state-empty">
            No alerts yet.
            <span className="hint">
              A watchlisted plate passing an active camera, or a high-severity
              zone hit, appears here within seconds — no reload needed.
            </span>
          </div>
        )}
        <div className="alert-list">
          {alerts.map((a) => (
            <AlertCard key={a.alert_seq} alert={a} onAck={applyAck} />
          ))}
        </div>
      </div>
    </div>
  )
}
