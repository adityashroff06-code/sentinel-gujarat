import { useEffect, useRef, useState } from 'react'
import Hls from 'hls.js'
import { api } from '../lib/api.js'
import { roleAtLeast, useSession } from '../lib/session.js'

// Zones — draw intrusion polygons and crossing lines over a camera's
// live tile. Zones save in the CANONICAL shape of docs/api.md §5
// ({zone_id, name, type, severity, points} with points normalised 0–1)
// through PATCH /api/cameras/{id}; the save reports the REAL result
// (old defect D13: the old page swallowed failures), and the notice
// states the true reload behaviour: the supervisor hot-reloads zone
// edits on its ~10 s poll — no worker restart needed.
// Ported from D:\projects\Sentinel_Repo\ui\src\pages\Zones.jsx (F52).
// Zone/tier edits are admin-only (docs/api.md §7 roles) — the page is
// hidden from the nav below admin and shows a needs-access state here.

const zoneId = () => `z${Date.now().toString(36)}${Math.floor(Math.random() * 36).toString(36)}`

export default function Zones() {
  const session = useSession()
  const [cams, setCams] = useState([])
  const [camId, setCamId] = useState(null)
  const [zones, setZones] = useState([])
  const [draft, setDraft] = useState(null) // {type, severity, points:[[nx,ny]]}
  const [saved, setSaved] = useState(true)
  const [saveMsg, setSaveMsg] = useState(null) // {kind:'ok'|'err', text}
  const [streamErr, setStreamErr] = useState(null)
  const videoRef = useRef(null)
  const boxRef = useRef(null)

  const isAdmin = roleAtLeast(session?.role, 'admin')

  useEffect(() => {
    if (!isAdmin) return undefined
    let alive = true
    api
      .cameras()
      .then((d) => {
        if (!alive) return
        const list = d.cameras
        setCams(list)
        setCamId((cur) => {
          if (cur) return cur
          // open on a camera that already has zones (never a blank page),
          // else an active-tier camera (has a live tee to draw on)
          const withZones = list.find((x) => x.zones_json && x.zones_json !== 'null')
          const active = list.find((x) => x.fps_tier === 'active')
          return (withZones || active || list[0])?.camera_id ?? null
        })
      })
      .catch(() => alive && setCams([]))
    return () => {
      alive = false
    }
  }, [isAdmin])

  // the selected camera's zones + its live stream
  useEffect(() => {
    if (!camId || !isAdmin) return undefined
    let alive = true
    api
      .camera(camId)
      .then((c) => {
        if (!alive) return
        try {
          setZones(c.zones_json ? JSON.parse(c.zones_json) : [])
        } catch {
          setZones([]) // unparseable stored JSON: start clean, save overwrites
        }
        setSaved(true)
        setSaveMsg(null)
      })
      .catch(() => alive && setZones([]))

    const video = videoRef.current
    let hls = null
    setStreamErr(null)
    if (video) {
      if (Hls.isSupported()) {
        hls = new Hls({ lowLatencyMode: false, maxBufferLength: 20 })
        hls.on(Hls.Events.ERROR, (_e, data) => {
          if (data.fatal && alive) setStreamErr(data.details || 'stream unavailable')
        })
        hls.loadSource(api.streamUrl(camId))
        hls.attachMedia(video)
      } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
        video.src = api.streamUrl(camId)
      }
    }
    return () => {
      alive = false
      if (hls) hls.destroy()
      if (video) {
        video.removeAttribute('src')
        video.load()
      }
    }
  }, [camId, isAdmin])

  if (!isAdmin) {
    return (
      <div className="page">
        <div className="state-empty needs-access">
          Zone editing needs admin access.
          <span className="hint">
            Zones and tier changes are admin actions (roles: viewer &lt;
            evaluator &lt; admin) — sign in with an admin account.
          </span>
        </div>
      </div>
    )
  }

  const clickPoint = (e) => {
    if (!draft || !boxRef.current) return
    const r = boxRef.current.getBoundingClientRect()
    const nx = Math.min(Math.max((e.clientX - r.left) / r.width, 0), 1)
    const ny = Math.min(Math.max((e.clientY - r.top) / r.height, 0), 1)
    const pts = [...draft.points, [nx, ny]]
    if (draft.type === 'line' && pts.length === 2) {
      setZones([...zones, finishZone({ ...draft, points: pts })])
      setDraft(null)
      setSaved(false)
    } else {
      setDraft({ ...draft, points: pts })
    }
  }

  const finishZone = (d) => ({
    zone_id: zoneId(),
    name: d.name || `${d.type} ${zones.length + 1}`,
    type: d.type,
    severity: d.severity,
    points: d.points,
  })

  const finishPolygon = () => {
    if (!draft || draft.points.length < 3) return
    setZones([...zones, finishZone(draft)])
    setDraft(null)
    setSaved(false)
  }

  async function save() {
    setSaveMsg(null)
    try {
      await api.patchCamera(camId, { zones_json: JSON.stringify(zones) })
      setSaved(true)
      setSaveMsg({
        kind: 'ok',
        text: `Saved — ${zones.length} zone(s) on ${camId}. Running workers hot-reload zone edits within ~10 s (supervisor poll); no restart needed.`,
      })
    } catch (err) {
      setSaveMsg({ kind: 'err', text: `Save failed: ${err.detail || err.message}` })
    }
  }

  const toPath = (pts, close) =>
    pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x * 100},${y * 100}`).join(' ') + (close ? ' Z' : '')

  return (
    <div className="page zones-page">
      <div className="card zones-editor">
        <h2>Zone editor</h2>
        <div className="toolbar">
          <div className="field">
            <label htmlFor="zone-cam">Camera</label>
            <select
              id="zone-cam"
              value={camId || ''}
              onChange={(e) => {
                setCamId(e.target.value)
                setDraft(null)
              }}
            >
              {cams.map((c) => (
                <option key={c.camera_id} value={c.camera_id}>
                  {c.camera_id} — {c.location_name || c.department || ''}
                </option>
              ))}
            </select>
          </div>
          <button
            className="chip"
            onClick={() => setDraft({ type: 'intrusion', severity: 'high', points: [] })}
          >
            + intrusion zone
          </button>
          <button
            className="chip"
            onClick={() => setDraft({ type: 'line', severity: 'medium', points: [] })}
          >
            + crossing line
          </button>
          {draft?.type === 'intrusion' && (
            <button className="chip on" onClick={finishPolygon}>
              finish polygon ({draft.points.length} pts)
            </button>
          )}
          {draft && (
            <button className="chip" onClick={() => setDraft(null)}>
              cancel
            </button>
          )}
          <button id="save-zones" className="primary" onClick={save} disabled={saved}>
            {saved ? 'Saved' : 'Save zones'}
          </button>
        </div>

        <div
          ref={boxRef}
          className="zone-canvas"
          style={{ cursor: draft ? 'crosshair' : 'default' }}
          onClick={clickPoint}
        >
          <video ref={videoRef} autoPlay muted playsInline />
          {streamErr && (
            <div className="zone-stream-note">
              {camId}: {streamErr} — the last frame (or a blank tile) is still
              drawable; zones are stored normalised 0–1.
            </div>
          )}
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            {zones.map((z) =>
              z.type === 'line' ? (
                <path
                  key={z.zone_id}
                  className="zone-line"
                  d={toPath(z.points, false)}
                  vectorEffect="non-scaling-stroke"
                />
              ) : (
                <path
                  key={z.zone_id}
                  className="zone-poly"
                  d={toPath(z.points, true)}
                  vectorEffect="non-scaling-stroke"
                />
              )
            )}
            {draft && draft.points.length > 0 && (
              <path
                className="zone-draft"
                d={toPath(draft.points, false)}
                vectorEffect="non-scaling-stroke"
              />
            )}
          </svg>
        </div>
        {saveMsg && (
          <p className={saveMsg.kind === 'ok' ? 'zone-save-ok' : 'form-error'} role="status">
            {saveMsg.text}
          </p>
        )}
        <p className="muted footnote">
          Click on the video to place points — intrusion = polygon (3+ points,
          then finish), line = exactly 2 points; a line fires once, on a
          downward crossing. Coordinates are stored normalised 0–1 so zones
          survive resolution changes (docs/api.md §5).
        </p>
      </div>

      <div className="card zones-table">
        <h2>
          Zones on <span className="mono">{camId || '—'}</span>
        </h2>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Severity</th>
              <th aria-label="Remove" />
            </tr>
          </thead>
          <tbody>
            {zones.map((z, i) => (
              <tr key={z.zone_id}>
                <td>
                  <input
                    aria-label={`Zone ${i + 1} name`}
                    value={z.name}
                    onChange={(e) => {
                      const zz = [...zones]
                      zz[i] = { ...z, name: e.target.value }
                      setZones(zz)
                      setSaved(false)
                    }}
                  />
                </td>
                <td>{z.type}</td>
                <td>
                  <select
                    aria-label={`Zone ${i + 1} severity`}
                    value={z.severity}
                    onChange={(e) => {
                      const zz = [...zones]
                      zz[i] = { ...z, severity: e.target.value }
                      setZones(zz)
                      setSaved(false)
                    }}
                  >
                    <option>high</option>
                    <option>medium</option>
                    <option>low</option>
                  </select>
                </td>
                <td>
                  <button
                    className="ghost"
                    aria-label={`Remove ${z.name}`}
                    onClick={() => {
                      setZones(zones.filter((_, j) => j !== i))
                      setSaved(false)
                    }}
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
            {zones.length === 0 && (
              <tr>
                <td colSpan={4} className="muted">
                  No zones on this camera yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        <p className="muted footnote">
          High-severity zone hits also raise an alert on the live stream; every
          zone hit lands in the events table and the Reports page.
        </p>
      </div>
    </div>
  )
}
