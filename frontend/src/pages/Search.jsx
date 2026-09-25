import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ProvenanceBadge } from '../components/Badges.jsx'
import { api, deptColor } from '../lib/api.js'
import { formatTs } from '../lib/time.js'

// Search — sighting search with filters incl. provenance and vehicle
// class (F46), crop thumbnails (the session cookie carries the <img>
// requests), and row -> route. Ported from D:\projects\Sentinel_Repo\ui\
// src\pages\Search.jsx (F52): rewired to the session data layer, D13
// fixed (IST times, no silent .catch, designed states), provenance and
// class filters added, ?plate= deep link supported.
//
// Vehicle class filters twice: Search sends vehicle_class to the API
// (server-side since commit 8b8e8b8), and changing the select between
// submits also narrows the already-fetched page instantly — the count
// line says when it is showing a narrowed page.

// the classes the detector actually emits (ml/anpr/detect.py COCO_KEEP)
// plus 'unknown' for rows with no stored class — never a dead option
const CLASSES = ['car', 'truck', 'bus', 'motorcycle', 'bicycle', 'unknown']
const PROVENANCES = ['live', 'harvest', 'demo', 'test']

export default function Search() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [plate, setPlate] = useState(params.get('plate') || '')
  const [minConf, setMinConf] = useState(0)
  const [provenance, setProvenance] = useState('')
  const [vclass, setVclass] = useState('')
  const [state, setState] = useState({ status: 'loading', rows: [], total: 0 })

  const run = useCallback(async (query) => {
    setState((s) => ({ ...s, status: 'loading' }))
    try {
      const d = await api.sightings({ ...query, limit: 200 })
      setState({ status: 'ready', rows: d.sightings, total: d.total })
    } catch {
      setState({ status: 'error', rows: [], total: 0 })
    }
  }, [])

  // first load: honour a ?plate= deep link, else show the newest reads so
  // the page is never blank
  useEffect(() => {
    run({
      plate: params.get('plate') || '',
      provenance: params.get('provenance') || '',
    })
    // run once per mount; later searches go through the form
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const submit = (e) => {
    e?.preventDefault()
    run({
      plate,
      min_confidence: minConf || undefined,
      provenance,
      // 'unknown' means rows with NO stored class — the server filter
      // matches literal values only, so that bucket narrows client-side
      vehicle_class: vclass && vclass !== 'unknown' ? vclass : undefined,
    })
  }

  const shown = vclass
    ? state.rows.filter((r) => (r.vehicle_class || 'unknown') === vclass)
    : state.rows

  return (
    <div className="page">
      <div className="card">
        <h2>
          Vehicle search{' '}
          <span className="count num">
            {state.status === 'ready'
              ? shown.length !== state.rows.length
                ? `${shown.length} of ${state.rows.length} on this page · ${state.total} total — press Search to filter the full set`
                : `${state.rows.length} shown · ${state.total} total`
              : '…'}
          </span>
        </h2>
        <form className="toolbar" onSubmit={submit} role="search" aria-label="Sighting filters">
          <div className="field">
            <label htmlFor="s-plate">Plate (partial ok)</label>
            <input
              id="s-plate"
              className="plate"
              placeholder="e.g. GJ01"
              value={plate}
              onChange={(e) => setPlate(e.target.value.toUpperCase())}
            />
          </div>
          <div className="field">
            <label htmlFor="s-conf">Min confidence</label>
            <input
              id="s-conf"
              type="number"
              min="0"
              max="1"
              step="0.05"
              value={minConf}
              onChange={(e) => setMinConf(parseFloat(e.target.value) || 0)}
              style={{ width: 90 }}
            />
          </div>
          <div className="field">
            <label htmlFor="s-prov">Provenance</label>
            <select id="s-prov" value={provenance} onChange={(e) => setProvenance(e.target.value)}>
              <option value="">All</option>
              {PROVENANCES.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="s-class">Vehicle class</label>
            <select id="s-class" value={vclass} onChange={(e) => setVclass(e.target.value)}>
              <option value="">All</option>
              {CLASSES.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </div>
          <button className="primary" type="submit">
            {state.status === 'loading' ? 'Searching…' : 'Search'}
          </button>
        </form>

        {state.status === 'loading' && (
          <div className="skeleton-rows" aria-label="Loading sightings">
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i} className="skeleton" style={{ height: 34 }} />
            ))}
          </div>
        )}
        {state.status === 'error' && (
          <div className="state-error">
            Search failed — see the status strip above.
          </div>
        )}
        {state.status === 'ready' && shown.length === 0 && (
          <div className="state-empty">
            No sightings match these filters.
            <span className="hint">
              Widen the filters — or let the workers read some traffic first.
            </span>
          </div>
        )}
        {state.status === 'ready' && shown.length > 0 && (
          <table className="search-table">
            <thead>
              <tr>
                <th aria-label="Crop" />
                <th>Plate</th>
                <th>Conf.</th>
                <th>Class</th>
                <th>Camera</th>
                <th>Department</th>
                <th>Seen (IST)</th>
                <th>Data</th>
                <th aria-label="Route" />
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr
                  key={r.sighting_id}
                  className="clickable"
                  onClick={() => navigate(`/route/${encodeURIComponent(r.plate)}`)}
                >
                  <td>
                    {r.crop_url ? (
                      <img className="crop-thumb" src={r.crop_url} alt={`crop ${r.plate}`} />
                    ) : (
                      '—'
                    )}
                  </td>
                  <td>
                    <b className="plate">{r.plate}</b>
                  </td>
                  <td className="num">{r.confidence?.toFixed ? r.confidence.toFixed(2) : r.confidence}</td>
                  <td className="vclass">{r.vehicle_class || 'unknown'}</td>
                  <td className="mono">{r.camera_id}</td>
                  <td>
                    <span style={{ color: deptColor(r.department) }}>
                      {r.department || 'Unknown'}
                    </span>
                  </td>
                  <td className="num">{formatTs(r.seen_at)}</td>
                  <td>
                    <ProvenanceBadge provenance={r.provenance} />
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <Link className="chip" to={`/route/${encodeURIComponent(r.plate)}`}>
                      route ›
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
