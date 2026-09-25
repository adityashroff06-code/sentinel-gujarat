import { formatTs } from '../lib/time.js'

// The F46 feed-status strip: tells apart "no traffic on this camera",
// "feed down" and "pipeline dead" from /api/workers state plus the last
// read time per camera — never a silent blank dashboard. New in this
// build (the old Dashboard had only a workers table, defect D13's
// "quiet night vs pipeline dead" gap).

const HEARTBEAT_STALE_MS = 90_000 // the supervisor writes every 10 s
const READ_RECENT_MS = 5 * 60_000

function cameraState(snap, lastReadAt, now) {
  if (snap.alive === false) {
    return { cls: 'down', word: 'FEED DOWN', hint: 'worker lost the stream — reconnecting' }
  }
  if (lastReadAt && now - lastReadAt < READ_RECENT_MS) {
    return { cls: 'reading', word: 'READING', hint: 'streaming, plates being read' }
  }
  return { cls: 'quiet', word: 'NO TRAFFIC', hint: 'streaming, no recent reads on this camera' }
}

/** `workers` is the polled /api/workers body (or null while loading);
 *  `lastReadByCam` maps camera_id -> epoch ms of its newest sighting. */
export default function FeedStatus({ workers, lastReadByCam = {} }) {
  const now = Date.now()

  if (workers === null || workers === undefined) {
    return (
      <div className="feed-status" aria-label="Feed status">
        <span className="feed-title">Feeds</span>
        <span className="muted">checking the pipeline…</span>
      </div>
    )
  }

  const writtenAt = workers.written_at ? Date.parse(workers.written_at) : NaN
  const heartbeatOk =
    workers.available === true && Number.isFinite(writtenAt) && now - writtenAt < HEARTBEAT_STALE_MS

  if (!heartbeatOk) {
    return (
      <div className="feed-status dead" role="status" aria-label="Feed status">
        <span className="feed-title">Feeds</span>
        <span className="feed-dead-msg">
          Analytics pipeline down — no worker heartbeat
          {workers.available && workers.written_at
            ? ` since ${formatTs(workers.written_at)}`
            : ''}
          . Live tiles and alerts will not update until the worker process is
          started.
        </span>
      </div>
    )
  }

  const cams = Object.entries(workers.cameras || {})
  return (
    <div className="feed-status" role="status" aria-label="Feed status">
      <span className="feed-title">Feeds</span>
      {cams.length === 0 && (
        <span className="muted">pipeline up — no camera workers running yet</span>
      )}
      {cams.map(([cid, snap]) => {
        const st = cameraState(snap, lastReadByCam[cid], now)
        return (
          <span key={cid} className={`feed-chip ${st.cls}`} title={st.hint}>
            <span className="mono">{cid}</span> {st.word}
          </span>
        )
      })}
      <span className="muted feed-hb num">heartbeat {formatTs(workers.written_at)}</span>
    </div>
  )
}
