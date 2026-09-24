import { useCallback, useEffect, useState } from 'react'
import { api, deptColor, DEPT_COLORS } from '../lib/api.js'
import { roleAtLeast, useSession } from '../lib/session.js'
import { formatTs } from '../lib/time.js'

// Camera registry (Model 1): table with filters, manual onboarding form
// (evaluator+), CSV bulk import with per-row results and record editing
// incl. tier/ROI/zones JSON (admin only — actions above the role are
// hidden, not just refused; decision F41). New screen in this build —
// the previous UI never had it although the API did (frontend/CLAUDE.md).

const DEPTS = Object.keys(DEPT_COLORS)
const TRANSPORTS = ['hls', 'rtsp', 'replay', 'none']
const TIERS = ['active', 'registered']
const HEALTHS = ['online', 'degraded', 'offline']

const HEALTH_VAR = {
  online: 'var(--health-online)',
  degraded: 'var(--health-degraded)',
  offline: 'var(--health-offline)',
}

const EMPTY_FORM = {
  camera_id: '',
  department: '',
  location_name: '',
  lat: '',
  lon: '',
  transport: 'none',
  rtsp_url_template: '',
  hls_url: '',
  fps_tier: 'registered',
  notes: '',
}

function numOrNull(v) {
  if (v === '' || v == null) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

function strOrNull(v) {
  const s = (v || '').trim()
  return s === '' ? null : s
}

export default function Cameras() {
  const session = useSession()
  const canOnboard = roleAtLeast(session?.role, 'evaluator')
  const canAdmin = roleAtLeast(session?.role, 'admin')

  const [filters, setFilters] = useState({ department: '', health: '', tier: '', q: '' })
  const [state, setState] = useState({ status: 'loading', cameras: [], total: 0 })
  const [editing, setEditing] = useState(null) // full camera record being edited
  const [importResult, setImportResult] = useState(null)

  const load = useCallback(async (f) => {
    setState((s) => ({ ...s, status: 'loading' }))
    try {
      const d = await api.cameras(f)
      setState({ status: 'ready', cameras: d.cameras, total: d.total })
    } catch {
      setState({ status: 'error', cameras: [], total: 0 })
    }
  }, [])

  useEffect(() => {
    load(filters)
  }, [filters, load])

  const setF = (k) => (e) => setFilters((f) => ({ ...f, [k]: e.target.value }))

  return (
    <div className="page">
      <div className="card">
        <h2>
          Registry <span className="count num">{state.total} cameras</span>
        </h2>
        <div className="toolbar" role="group" aria-label="Registry filters">
          <div className="field">
            <label htmlFor="f-dept">Department</label>
            <select id="f-dept" value={filters.department} onChange={setF('department')}>
              <option value="">All</option>
              {DEPTS.map((d) => (
                <option key={d}>{d}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="f-health">Health</label>
            <select id="f-health" value={filters.health} onChange={setF('health')}>
              <option value="">All</option>
              {HEALTHS.map((h) => (
                <option key={h}>{h}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="f-tier">Tier</label>
            <select id="f-tier" value={filters.tier} onChange={setF('tier')}>
              <option value="">All</option>
              {TIERS.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="f-q">Search</label>
            <input
              id="f-q"
              placeholder="id, location, department"
              value={filters.q}
              onChange={setF('q')}
            />
          </div>
        </div>

        {state.status === 'loading' && (
          <div className="skeleton-rows" aria-label="Loading cameras">
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i} className="skeleton" style={{ height: 30 }} />
            ))}
          </div>
        )}
        {state.status === 'error' && (
          <div className="state-error">
            Could not load the registry — see the status strip above.
          </div>
        )}
        {state.status === 'ready' && state.cameras.length === 0 && (
          <div className="state-empty">
            No cameras match these filters.
            <span className="hint">Clear a filter, or onboard a camera below.</span>
          </div>
        )}
        {state.status === 'ready' && state.cameras.length > 0 && (
          <table className="cameras-table">
            <thead>
              <tr>
                <th>Camera</th>
                <th>Department</th>
                <th>Location</th>
                <th>Health</th>
                <th>Transport</th>
                <th>Tier</th>
                <th>Codec</th>
                <th>Resolution</th>
                <th>Last seen</th>
                {canAdmin && <th aria-label="Actions" />}
              </tr>
            </thead>
            <tbody>
              {state.cameras.map((c) => (
                <tr key={c.camera_id}>
                  <td className="mono">{c.camera_id}</td>
                  <td>
                    <span className="badge" style={{ background: deptColor(c.department) }}>
                      {c.department || 'Unknown'}
                    </span>
                  </td>
                  <td>{c.location_name || '—'}</td>
                  <td>
                    <span
                      className="health-dot"
                      style={{ background: HEALTH_VAR[c.health] || 'var(--text-faint)' }}
                      aria-hidden="true"
                    />
                    {c.health || 'unknown'}
                  </td>
                  <td>{c.transport || '—'}</td>
                  <td>{c.fps_tier || '—'}</td>
                  <td>{c.codec || '—'}</td>
                  <td className="num">{c.width ? `${c.width}×${c.height}` : '—'}</td>
                  <td className="num">{formatTs(c.last_seen)}</td>
                  {canAdmin && (
                    <td>
                      <button className="ghost" onClick={() => setEditing(c)}>
                        Edit
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {canOnboard && <AddCamera onAdded={() => load(filters)} />}
      {canAdmin && (
        <ImportCsv
          result={importResult}
          onResult={(r) => {
            setImportResult(r)
            load(filters)
          }}
        />
      )}
      {editing && canAdmin && (
        <EditCamera
          camera={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            load(filters)
          }}
        />
      )}
    </div>
  )
}

// ---- manual onboarding (Model 1 deliverable; evaluator+) -------------------

function AddCamera({ onAdded }) {
  const [form, setForm] = useState(EMPTY_FORM)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.createCamera({
        camera_id: form.camera_id.trim(),
        department: form.department || 'Unknown',
        location_name: strOrNull(form.location_name),
        lat: numOrNull(form.lat),
        lon: numOrNull(form.lon),
        transport: form.transport,
        rtsp_url_template: strOrNull(form.rtsp_url_template),
        hls_url: strOrNull(form.hls_url),
        fps_tier: form.fps_tier,
        notes: strOrNull(form.notes),
        source: 'manual',
      })
      setForm(EMPTY_FORM)
      onAdded()
    } catch (err) {
      setError(err.detail || 'Could not add the camera.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card" id="add-camera">
      <h2>Onboard a camera</h2>
      <form onSubmit={submit}>
        <div className="form-row">
          <div className="field">
            <label htmlFor="add-id">Camera id *</label>
            <input
              id="add-id"
              required
              pattern="[A-Za-z0-9_-]{1,64}"
              title="letters, digits, _ and - only"
              value={form.camera_id}
              onChange={set('camera_id')}
            />
          </div>
          <div className="field">
            <label htmlFor="add-dept">Department</label>
            <select id="add-dept" value={form.department} onChange={set('department')}>
              <option value="">—</option>
              {DEPTS.map((d) => (
                <option key={d}>{d}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="add-loc">Location name</label>
            <input id="add-loc" value={form.location_name} onChange={set('location_name')} />
          </div>
          <div className="field">
            <label htmlFor="add-lat">Latitude</label>
            <input id="add-lat" type="number" step="any" min="-90" max="90"
              value={form.lat} onChange={set('lat')} />
          </div>
          <div className="field">
            <label htmlFor="add-lon">Longitude</label>
            <input id="add-lon" type="number" step="any" min="-180" max="180"
              value={form.lon} onChange={set('lon')} />
          </div>
        </div>
        <div className="form-row" style={{ marginTop: 'var(--s-3)' }}>
          <div className="field">
            <label htmlFor="add-transport">Transport</label>
            <select id="add-transport" value={form.transport} onChange={set('transport')}>
              {TRANSPORTS.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </div>
          <div className="field" style={{ flex: 1, minWidth: 220 }}>
            <label htmlFor="add-rtsp">RTSP URL template (no credentials)</label>
            <input id="add-rtsp" value={form.rtsp_url_template} onChange={set('rtsp_url_template')} />
          </div>
          <div className="field" style={{ flex: 1, minWidth: 220 }}>
            <label htmlFor="add-hls">HLS URL (no credentials)</label>
            <input id="add-hls" value={form.hls_url} onChange={set('hls_url')} />
          </div>
          <div className="field">
            <label htmlFor="add-tier">Tier</label>
            <select id="add-tier" value={form.fps_tier} onChange={set('fps_tier')}>
              {TIERS.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </div>
          <div className="field" style={{ flex: 1, minWidth: 180 }}>
            <label htmlFor="add-notes">Notes</label>
            <input id="add-notes" value={form.notes} onChange={set('notes')} />
          </div>
          <button className="primary" type="submit" disabled={busy}>
            {busy ? 'Adding…' : 'Add camera'}
          </button>
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
      </form>
    </div>
  )
}

// ---- CSV bulk import (Model 1 deliverable; admin only) ---------------------

function ImportCsv({ result, onResult }) {
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function submit(e) {
    e.preventDefault()
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      onResult(await api.importCameras(file))
    } catch (err) {
      setError(err.detail || 'Import failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card" id="import-csv">
      <h2>Bulk import (CSV)</h2>
      <p className="muted" style={{ marginBottom: 'var(--s-3)' }}>
        Header row with <span className="mono">camera_id</span> plus any
        registry columns; at most 2&nbsp;MB / 5,000 rows. Every row is
        accepted or rejected with a reason — one transaction, no partial
        commit.
      </p>
      <form className="form-row" onSubmit={submit}>
        <div className="field">
          <label htmlFor="import-file">CSV file</label>
          <input
            id="import-file"
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
        </div>
        <button className="primary" type="submit" disabled={!file || busy}>
          {busy ? 'Importing…' : 'Import'}
        </button>
      </form>
      {error && <p className="form-error" role="alert">{error}</p>}
      {result && (
        <div className="import-results" role="status">
          <div>
            <b className="accepted num">{result.accepted.length} accepted</b>
            {' · '}
            <b className="rejected num">{result.rejected.length} rejected</b>
          </div>
          {result.accepted.length > 0 && (
            <ul className="accepted-list">
              {result.accepted.map((id) => (
                <li key={id} className="accepted">+ {id}</li>
              ))}
            </ul>
          )}
          {result.rejected.length > 0 && (
            <ul className="rejected-list">
              {result.rejected.map((r) => (
                <li key={`${r.row}-${r.reason}`} className="rejected">
                  row {r.row}: {r.reason}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

// ---- record edit incl. tier / ROI / zones JSON (admin only) ----------------

function EditCamera({ camera, onClose, onSaved }) {
  const [form, setForm] = useState({
    department: camera.department || '',
    location_name: camera.location_name || '',
    lat: camera.lat ?? '',
    lon: camera.lon ?? '',
    health: camera.health || '',
    fps_tier: camera.fps_tier || 'registered',
    roi_json: camera.roi_json || '',
    zones_json: camera.zones_json || '',
    notes: camera.notes || '',
  })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  function validJsonOrNull(text, name) {
    const s = (text || '').trim()
    if (s === '') return null
    try {
      JSON.parse(s)
      return s
    } catch {
      throw new Error(`${name} is not valid JSON`)
    }
  }

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const patch = {
        department: strOrNull(form.department),
        location_name: strOrNull(form.location_name),
        lat: numOrNull(form.lat),
        lon: numOrNull(form.lon),
        health: strOrNull(form.health),
        fps_tier: form.fps_tier,
        roi_json: validJsonOrNull(form.roi_json, 'ROI'),
        zones_json: validJsonOrNull(form.zones_json, 'Zones'),
        notes: strOrNull(form.notes),
      }
      await api.patchCamera(camera.camera_id, patch)
      onSaved()
    } catch (err) {
      setError(err.detail || err.message || 'Could not save the camera.')
      setBusy(false)
    }
  }

  return (
    <div className="card" id="edit-camera">
      <h2>
        Edit <span className="mono">{camera.camera_id}</span>
        <button className="ghost" style={{ marginLeft: 'auto' }} onClick={onClose}>
          Cancel
        </button>
      </h2>
      <form onSubmit={submit}>
        <div className="form-row">
          <div className="field">
            <label htmlFor="edit-dept">Department</label>
            <select id="edit-dept" value={form.department} onChange={set('department')}>
              <option value="">—</option>
              {DEPTS.map((d) => (
                <option key={d}>{d}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="edit-loc">Location name</label>
            <input id="edit-loc" value={form.location_name} onChange={set('location_name')} />
          </div>
          <div className="field">
            <label htmlFor="edit-lat">Latitude</label>
            <input id="edit-lat" type="number" step="any" min="-90" max="90"
              value={form.lat} onChange={set('lat')} />
          </div>
          <div className="field">
            <label htmlFor="edit-lon">Longitude</label>
            <input id="edit-lon" type="number" step="any" min="-180" max="180"
              value={form.lon} onChange={set('lon')} />
          </div>
          <div className="field">
            <label htmlFor="edit-health">Health</label>
            <select id="edit-health" value={form.health} onChange={set('health')}>
              <option value="">—</option>
              {HEALTHS.map((h) => (
                <option key={h}>{h}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="edit-tier">Tier</label>
            <select id="edit-tier" value={form.fps_tier} onChange={set('fps_tier')}>
              {TIERS.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="form-row" style={{ marginTop: 'var(--s-3)' }}>
          <div className="field" style={{ flex: 1, minWidth: 260 }}>
            <label htmlFor="edit-roi">ROI polygon JSON ([[x,y],…] normalised 0–1)</label>
            <textarea id="edit-roi" rows={3} value={form.roi_json} onChange={set('roi_json')} />
          </div>
          <div className="field" style={{ flex: 1, minWidth: 260 }}>
            <label htmlFor="edit-zones">Intrusion zones JSON</label>
            <textarea id="edit-zones" rows={3} value={form.zones_json} onChange={set('zones_json')} />
          </div>
        </div>
        <div className="form-row" style={{ marginTop: 'var(--s-3)' }}>
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor="edit-notes">Notes</label>
            <input id="edit-notes" value={form.notes} onChange={set('notes')} />
          </div>
          <button className="primary" type="submit" disabled={busy}>
            {busy ? 'Saving…' : 'Save changes'}
          </button>
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
      </form>
    </div>
  )
}
