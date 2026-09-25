import { Link } from 'react-router-dom'
import { fieldOfView, formatLatLon, isLocated } from '../../lib/geo.js'
import { deptClass, deptKey, feedKind, healthKey, isAnalysed } from '../../lib/pins.js'
import { formatTs } from '../../lib/time.js'

// The camera record opened by a pin click on the Map page (Model 1): the
// registry row, its field of view (flagged "assumed" when not surveyed),
// its last-24 h read activity split by provenance (a demo read never
// passes as a live one), and the two ways onward — the live view and the
// camera's recent reads. Every value is from the registry or the API;
// nothing on this panel is invented.

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`

function Row({ k, children }) {
  return (
    <div className="kv">
      <span>{k}</span>
      <span>{children ?? '—'}</span>
    </div>
  )
}

export default function CameraRecord({ cam, activity, hours, onClose, onZoom }) {
  const kind = feedKind(cam)
  const health = healthKey(cam.health)
  const view = fieldOfView(cam)
  const id = encodeURIComponent(cam.camera_id)
  const res = cam.width && cam.height ? `${cam.width}×${cam.height}` : null
  const codec = cam.codec ? cam.codec.toUpperCase() : null

  return (
    <aside className="gis-record" aria-label={`Camera ${cam.camera_id}`} id="camera-record">
      <div className="gis-record-head">
        <div>
          <h3>
            <span className="mono">{cam.camera_id}</span>
            <span className={`badge dept-fill ${deptClass(cam.department)}`}>
              {deptKey(cam.department)}
            </span>
          </h3>
          <div className="loc">{cam.location_name || 'unnamed location'}</div>
        </div>
        <button className="ghost close" onClick={onClose} aria-label="Close camera record">
          ×
        </button>
      </div>

      <div className="gis-record-tags">
        <span className={`tag health-${health}`}>
          <span className="health-dot" aria-hidden="true" />
          {health === 'unknown' ? 'health unknown' : health}
        </span>
        <span className="tag">{kind === 'local' ? 'local feed' : 'sandbox grid'}</span>
        <span className={`tag ${isAnalysed(cam) ? 'tag-analysed' : ''}`}>
          {isAnalysed(cam) ? 'analysed · ANPR' : 'view only'}
        </span>
      </div>

      <div className="gis-record-actions">
        <Link className="btn primary" to={`/wall?cam=${id}`} id="record-open-live">
          Open live ›
        </Link>
        <Link className="btn" to={`/search?camera=${id}`} id="record-recent-reads">
          Recent reads ›
        </Link>
        {isLocated(cam) && (
          <button type="button" className="ghost" onClick={() => onZoom(cam)}>
            Zoom to
          </button>
        )}
      </div>

      <h4>Registry record</h4>
      <Row k="Department">{deptKey(cam.department)}</Row>
      <Row k="Location">{cam.location_name}</Row>
      <Row k="Transport">{cam.transport ? cam.transport.toUpperCase() : null}</Row>
      <Row k="Tier">
        {cam.fps_tier === 'active' ? 'active — ANPR worker' : cam.fps_tier || null}
      </Row>
      <Row k="Health">{health}</Row>
      <Row k="Codec · resolution">
        {codec || res ? [codec, res].filter(Boolean).join(' · ') : null}
      </Row>
      <Row k="Coordinates">
        {isLocated(cam) ? <span className="num">{formatLatLon(cam.lat, cam.lon)}</span> : 'not located'}
      </Row>
      <Row k="Field of view">
        <span className="num">
          {Math.round(view.bearing)}° · {Math.round(view.fov)}° · {Math.round(view.range)} m
        </span>
        {view.assumed && <span className="tip-assumed"> (assumed)</span>}
      </Row>
      <Row k="Last health check">{cam.last_seen ? formatTs(cam.last_seen) : null}</Row>
      <Row k="Source">{cam.source}</Row>

      <h4>
        Activity · last {hours} h
      </h4>
      {activity ? (
        <>
          <div className="gis-record-activity">
            <div>
              <b className="num">{activity.sightings}</b>
              <span>reads</span>
            </div>
            <div>
              <b className="num">{activity.plates}</b>
              <span>plates</span>
            </div>
            <div>
              <b className="num">{activity.alerts}</b>
              <span>alerts</span>
            </div>
          </div>
          {Object.keys(activity.by_provenance || {}).length > 0 && (
            <div className="gis-record-prov">
              {Object.entries(activity.by_provenance).map(([p, n]) => (
                <span key={p} className={`prov-badge prov-${p}`}>
                  {n} {p}
                </span>
              ))}
            </div>
          )}
          <Row k="Last read">{activity.last_seen ? formatTs(activity.last_seen) : null}</Row>
        </>
      ) : (
        <p className="muted gis-record-quiet">
          No plate reads or alerts in the last {plural(hours, 'hour')}
          {isAnalysed(cam) ? '.' : ' — this camera is view only (no ANPR worker).'}
        </p>
      )}
      {cam.notes && <p className="muted gis-record-notes">{cam.notes}</p>}
    </aside>
  )
}
