import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { MatchChip, ProvenanceBadge, SeverityWord } from '../components/Badges.jsx'
import { api, deptColor } from '../lib/api.js'
import { canonical, coerce, corrections, normalise, plateLike, spaced } from '../lib/plates.js'
import { formatTs } from '../lib/time.js'
import '../styles/search.css'

// Search — the ANPR search window (ANPR search lane, 25 Sep). A plate in,
// every read of it out: OCR-tolerant by default (GET /api/sightings
// match=anpr: exact -> ambiguity -> fuzzy), with a live preview of how the
// plate grammar reads what is typed, "plates to try" from
// /api/plates/suggest (demo plates badged DEMO, live ones LIVE — rule 12),
// a per-registration summary (reads, cameras + departments, first/last
// seen in IST, watchlist hit, best crop, route) and the reads table.
//
// The URL is the search state: ?plate= ?match= ?camera= ?provenance=
// ?min_conf= ?class= deep-link a search, and every submit writes them back
// so a search can be shared. Vehicle class also narrows the fetched page
// instantly between submits ('unknown' = rows with no stored class, a
// bucket the server filter cannot express) — the count line says so.
//
// Ported from the S3.3 Search (itself from D:\projects\Sentinel_Repo\ui\
// src\pages\Search.jsx, F52); the grammar preview mirrors
// backend/core/plates.py through src/lib/plates.js (display only — the
// response's `query` echo is authoritative).

// the classes the detector actually emits (ml/anpr/detect.py COCO_KEEP)
// plus 'unknown' for rows with no stored class — never a dead option
const CLASSES = ['car', 'truck', 'bus', 'motorcycle', 'bicycle', 'unknown']
const PROVENANCES = ['live', 'harvest', 'demo', 'test']
const MODES = [
  {
    id: 'anpr',
    label: 'ANPR-tolerant',
    help: 'Exact reads first, then OCR look-alikes (8↔B, 0↔O, 1↔I, 5↔S, 2↔Z, 6↔G), then registrations one character away.',
  },
  { id: 'exact', label: 'Exact', help: 'Only reads stored exactly as typed.' },
  {
    id: 'contains',
    label: 'Contains',
    help: 'Every read containing the typed characters, newest first.',
  },
]
const TIER = { exact: 0, ambiguity: 1, fuzzy: 2, contains: 3 }
const GROUPS_SHOWN = 6

/** A known match mode from a URL value, else the ANPR-tolerant default. */
const modeOf = (value) => (MODES.some((m) => m.id === value) ? value : 'anpr')

/** The query the URL describes (the source of truth for a search). */
function queryFromParams(params) {
  const plate = params.get('plate') || ''
  return {
    plate,
    match: plate ? modeOf(params.get('match')) : undefined,
    camera_id: params.get('camera') || undefined,
    provenance: params.get('provenance') || undefined,
    min_confidence: Number(params.get('min_conf')) || undefined,
    vclass: params.get('class') || '',
  }
}

export default function Search() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const paramKey = params.toString()

  // the form (edited freely; a submit writes it to the URL)
  const [plate, setPlate] = useState(params.get('plate') || '')
  const [mode, setMode] = useState(modeOf(params.get('match')))
  const [minConf, setMinConf] = useState(Number(params.get('min_conf')) || 0)
  const [provenance, setProvenance] = useState(params.get('provenance') || '')
  const [vclass, setVclass] = useState(params.get('class') || '')
  const [camera, setCamera] = useState(params.get('camera') || '')
  const [nonce, setNonce] = useState(0) // re-run an identical search

  const [state, setState] = useState({ status: 'loading', rows: [], total: 0, body: null })
  const [suggest, setSuggest] = useState({ status: 'loading', data: null })
  const [cameras, setCameras] = useState([])
  const [watch, setWatch] = useState(new Map()) // canonical -> active entry

  // side data: plates to try, the camera list, the watchlist (for the
  // watchlist-hit badge). Each failure is local — the strip reports it.
  useEffect(() => {
    let live = true
    api
      .plateSuggest(6)
      .then((data) => live && setSuggest({ status: 'ready', data }))
      .catch(() => live && setSuggest({ status: 'error', data: null }))
    api
      .cameras()
      .then((d) => live && setCameras(d.cameras || []))
      .catch(() => live && setCameras([]))
    api
      .watchlist()
      .then((rows) => {
        if (!live) return
        const now = Date.now()
        const m = new Map()
        for (const w of rows) {
          if (!w.active || (w.expires_at && new Date(w.expires_at).getTime() <= now)) continue
          m.set(w.plate_canonical || canonical(w.plate), w)
        }
        setWatch(m)
      })
      .catch(() => live && setWatch(new Map()))
    return () => {
      live = false
    }
  }, [])

  // every URL change (deep link, submit, chip, back/forward) runs the search
  useEffect(() => {
    let live = true
    const q = queryFromParams(params)
    setPlate(q.plate)
    if (q.match) setMode(q.match) // no plate: keep the chosen mode
    setMinConf(q.min_confidence || 0)
    setProvenance(q.provenance || '')
    setVclass(q.vclass)
    setCamera(q.camera_id || '')
    setState((s) => ({ ...s, status: 'loading' }))
    api
      .sightings({
        plate: q.plate,
        match: q.match,
        camera_id: q.camera_id,
        provenance: q.provenance,
        min_confidence: q.min_confidence,
        // 'unknown' means rows with NO stored class — the server filter
        // matches literal values only, so that bucket narrows client-side
        vehicle_class: q.vclass && q.vclass !== 'unknown' ? q.vclass : undefined,
        limit: 200,
      })
      .then((body) => live && setState({ status: 'ready', rows: body.sightings, total: body.total, body }))
      .catch(() => live && setState({ status: 'error', rows: [], total: 0, body: null }))
    return () => {
      live = false
    }
    // paramKey is the URL; nonce re-runs an identical search
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramKey, nonce])

  const go = useCallback(
    (overrides = {}) => {
      const f = { plate, mode, minConf, provenance, vclass, camera, ...overrides }
      const next = new URLSearchParams()
      const p = normalise(f.plate)
      if (p) {
        next.set('plate', p)
        next.set('match', f.mode)
      }
      if (f.camera) next.set('camera', f.camera)
      if (f.provenance) next.set('provenance', f.provenance)
      if (f.minConf) next.set('min_conf', String(f.minConf))
      if (f.vclass) next.set('class', f.vclass)
      setParams(next, { replace: false })
      setNonce((n) => n + 1)
    },
    [plate, mode, minConf, provenance, vclass, camera, setParams]
  )

  const submit = (e) => {
    e?.preventDefault()
    go()
  }

  const shown = useMemo(
    () =>
      vclass ? state.rows.filter((r) => (r.vehicle_class || 'unknown') === vclass) : state.rows,
    [state.rows, vclass]
  )
  const filtered = ['camera', 'provenance', 'min_conf', 'class'].some((k) => params.get(k))

  const query = state.body?.query || null
  const groups = useMemo(() => (query ? groupRows(shown, watch) : []), [query, shown, watch])

  return (
    <div className="page anpr-page">
      <form
        className="card anpr-hero"
        onSubmit={submit}
        role="search"
        aria-label="ANPR search"
      >
        <div className="anpr-hero-grid">
          <div className="anpr-query">
            <div className="anpr-title">
              <h2>ANPR search</h2>
              <span className="muted">
                Every read of a registration across the camera network — OCR-tolerant.
              </span>
            </div>
            <label htmlFor="s-plate" className="anpr-label">
              Registration number
            </label>
            <div className="plate-input-row">
              <div className="plate-input">
                <span className="plate-ind" aria-hidden="true">
                  <span className="plate-ind-seal" />
                  IND
                </span>
                <input
                  id="s-plate"
                  className="plate"
                  placeholder="GJ01AB1234"
                  autoComplete="off"
                  spellCheck="false"
                  maxLength={24}
                  value={plate}
                  onChange={(e) => setPlate(e.target.value.toUpperCase())}
                />
                {plate && (
                  <button
                    type="button"
                    className="plate-clear"
                    aria-label="Clear the plate"
                    onClick={() => setPlate('')}
                  >
                    ×
                  </button>
                )}
              </div>
              <button className="primary anpr-go" type="submit">
                {state.status === 'loading' ? 'Searching…' : 'Search'}
              </button>
            </div>
            <PlatePreview value={plate} />
            <div className="mode-row">
              <div className="segmented" role="radiogroup" aria-label="Match mode">
                {MODES.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    role="radio"
                    data-mode={m.id}
                    aria-checked={mode === m.id}
                    className={mode === m.id ? 'on' : ''}
                    onClick={() => {
                      setMode(m.id)
                      // results for this very plate on screen: re-run them
                      // in the new mode; otherwise wait for Search
                      const p = normalise(plate)
                      if (p && p === params.get('plate') && m.id !== mode) go({ mode: m.id })
                    }}
                  >
                    {m.label}
                  </button>
                ))}
              </div>
              <span className="mode-help">
                {normalise(plate)
                  ? MODES.find((m) => m.id === mode)?.help
                  : 'Applies once a plate is entered — with no plate, the newest reads are listed.'}
              </span>
            </div>
            <Refine
              cameras={cameras}
              camera={camera}
              setCamera={setCamera}
              minConf={minConf}
              setMinConf={setMinConf}
              provenance={provenance}
              setProvenance={setProvenance}
              vclass={vclass}
              setVclass={setVclass}
            />
          </div>
          <TryPanel suggest={suggest} onPick={(p) => go({ plate: p, mode: 'anpr' })} />
        </div>
      </form>

      <section className="card anpr-results">
        <h2>
          Reads{' '}
          <span className="count num" aria-live="polite">
            {state.status === 'ready' ? countLine(shown, state, groups) : '…'}
          </span>
          {query && state.status === 'ready' && (
            <span className="query-echo">
              {MODES.find((m) => m.id === state.body.match)?.label || state.body.match} for{' '}
              <b className="plate">{query.normalised}</b>
              {query.coerced && query.coerced !== query.normalised && (
                <>
                  {' '}
                  (reads as <b className="plate">{query.coerced}</b>)
                </>
              )}
            </span>
          )}
        </h2>

        {state.status === 'loading' && (
          <div className="skeleton-rows" aria-label="Loading sightings">
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i} className="skeleton" style={{ height: 34 }} />
            ))}
          </div>
        )}
        {state.status === 'error' && (
          <div className="state-error">
            Search failed — the platform did not answer. See the status strip above.
          </div>
        )}
        {state.status === 'ready' && shown.length === 0 && (
          <EmptyState
            query={query}
            match={state.body?.match}
            narrowed={state.rows.length > 0}
            filtered={filtered}
            onContains={() => go({ mode: 'contains' })}
          />
        )}
        {state.status === 'ready' && shown.length > 0 && (
          <>
            {groups.length > 0 && <PlateGroups groups={groups} />}
            <table className="search-table">
              <thead>
                <tr>
                  <th aria-label="Crop" />
                  <th>Plate</th>
                  <th>Match</th>
                  <th>Confidence</th>
                  <th>Class</th>
                  <th>Camera · department</th>
                  <th>Seen (IST)</th>
                  <th>Data</th>
                  <th aria-label="Route" />
                </tr>
              </thead>
              <tbody>
                {shown.map((r) => {
                  const routePlate = coerce(r.plate) || r.plate
                  const raw = normalise(r.plate_raw)
                  return (
                    <tr
                      key={r.sighting_id}
                      className={`clickable match-row-${r.match_type || 'none'}`}
                      onClick={() => navigate(`/route/${encodeURIComponent(routePlate)}`)}
                    >
                      <td className="crop-cell">
                        {r.crop_url ? (
                          <img className="crop-thumb" src={r.crop_url} alt={`plate crop ${r.plate}`} />
                        ) : (
                          <span className="crop-none">no crop</span>
                        )}
                      </td>
                      <td>
                        <StoredPlate plate={r.plate} registration={routePlate} />
                        {raw && raw !== r.plate && (
                          <span className="ocr-raw" title="exactly what OCR returned (plate_raw)">
                            OCR <span className="plate">{r.plate_raw}</span>
                          </span>
                        )}
                      </td>
                      <td>
                        {r.match_type ? (
                          <MatchChip matchType={r.match_type} distance={r.match_distance} />
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                      <td>
                        <ConfBar value={r.confidence} />
                      </td>
                      <td className="vclass">{r.vehicle_class || 'unknown'}</td>
                      <td>
                        <span className="mono">{r.camera_id}</span>
                        <span className="dept-inline">
                          <i className="dept-dot" style={{ background: deptColor(r.department) }} />
                          {r.department || 'Unknown'}
                        </span>
                        {r.location_name && <span className="loc-inline">{r.location_name}</span>}
                      </td>
                      <td className="num">{formatTs(r.seen_at)}</td>
                      <td>
                        <ProvenanceBadge provenance={r.provenance} />
                      </td>
                      <td onClick={(e) => e.stopPropagation()}>
                        <Link className="chip" to={`/route/${encodeURIComponent(routePlate)}`}>
                          route ›
                        </Link>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </>
        )}
      </section>
    </div>
  )
}

function Refine({
  cameras,
  camera,
  setCamera,
  minConf,
  setMinConf,
  provenance,
  setProvenance,
  vclass,
  setVclass,
}) {
  return (
    <div className="anpr-filters" role="group" aria-label="Refine">
      <span className="anpr-filters-title">Refine</span>
      <div className="field field-camera">
        <label htmlFor="s-camera">Camera</label>
        <select id="s-camera" value={camera} onChange={(e) => setCamera(e.target.value)}>
          <option value="">All cameras</option>
          {camera && !cameras.some((c) => c.camera_id === camera) && (
            <option value={camera}>{camera}</option>
          )}
          {cameras.map((c) => (
            <option key={c.camera_id} value={c.camera_id}>
              {c.camera_id} · {c.department || 'Unknown'}
              {c.location_name ? ` — ${c.location_name}` : ''}
            </option>
          ))}
        </select>
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
          className="conf-input"
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
    </div>
  )
}

function countLine(shown, state, groups) {
  const reads = (n) => `${n} read${n === 1 ? '' : 's'}`
  if (shown.length !== state.rows.length) {
    return `${shown.length} of ${state.rows.length} on this page · ${state.total} total — press Search to filter the full set`
  }
  const plates = groups.length ? ` · ${groups.length} registration${groups.length === 1 ? '' : 's'}` : ''
  return `${reads(state.rows.length)} shown · ${state.total} total${plates}`
}

/** Rows grouped by registration (the coerced form, else the stored plate). */
function groupRows(rows, watch) {
  const by = new Map()
  for (const r of rows) {
    const key = coerce(r.plate) || r.plate
    let g = by.get(key)
    if (!g) {
      g = {
        key,
        rows: [],
        spellings: new Set(),
        cameras: new Map(),
        provenances: new Set(),
        tier: 9,
        matchType: null,
        matchDistance: null,
        first: null,
        last: null,
        best: null,
      }
      by.set(key, g)
    }
    g.rows.push(r)
    g.spellings.add(r.plate)
    g.cameras.set(r.camera_id, r.department || 'Unknown')
    g.provenances.add(r.provenance)
    const t = TIER[r.match_type] ?? 9
    if (t < g.tier) {
      g.tier = t
      g.matchType = r.match_type
      g.matchDistance = r.match_distance
    }
    if (!g.first || r.seen_at < g.first) g.first = r.seen_at
    if (!g.last || r.seen_at > g.last) g.last = r.seen_at
    if (r.crop_url && (!g.best || r.confidence > g.best.confidence)) g.best = r
  }
  const out = [...by.values()].map((g) => ({
    ...g,
    watch: watch.get(canonical(g.key)) || null,
    departments: [...new Set(g.cameras.values())],
  }))
  out.sort((a, b) => a.tier - b.tier || b.rows.length - a.rows.length || (a.last < b.last ? 1 : -1))
  return out
}

function PlatePreview({ value }) {
  const n = normalise(value)
  if (!n) {
    return (
      <p className="plate-preview muted">
        Type a registration — spaces, dots and dashes are ignored; case does not matter.
      </p>
    )
  }
  const kind = plateLike(n)
  const fixed = coerce(n)
  const fixes = corrections(n)
  if (kind === 'full') {
    const at = new Map(fixes.map((f) => [f.index, f]))
    const series = fixed.slice(2, 4) === 'BH' && /^[0-9]/.test(fixed) ? 'BH-series' : 'standard series'
    return (
      <p className="plate-preview" data-kind="full">
        <span className="preview-tag ok">Full registration</span>
        {fixes.length > 0 && <span className="preview-label">Reads as</span>}
        <span className="preview-plate plate" title={spaced(fixed)}>
          {[...fixed].map((ch, i) =>
            at.has(i) ? (
              <mark key={i} title={`OCR look-alike: ${at.get(i).from} → ${ch}`}>
                {ch}
              </mark>
            ) : (
              <span key={i}>{ch}</span>
            )
          )}
        </span>
        <span className="preview-note">
          {fixes.length > 0
            ? `${fixes.map((f) => `${f.from}→${f.to}`).join(', ')} corrected by position — an OCR look-alike · ${series}`
            : series}
        </span>
      </p>
    )
  }
  return (
    <p className="plate-preview" data-kind={kind || 'none'}>
      <span className={`preview-tag ${kind ? 'partial' : 'none'}`}>
        {kind ? 'Partial plate' : 'Not a plate shape'}
      </span>
      <span className="preview-plate plate">{n}</span>
      <span className="preview-note">
        ANPR-tolerant matches it as an OCR-tolerant fragment; Contains matches it literally.
      </span>
    </p>
  )
}

function TryPanel({ suggest, onPick }) {
  const data = suggest.data
  // capped so the panel stays level with the query column; the server
  // orders each list best-first (watchlisted demo plates, seen entries)
  const sections = data
    ? [
        { id: 'demo', title: 'Demo vehicle (seeded)', badge: 'demo', items: data.demo.slice(0, 3) },
        { id: 'live', title: 'Most read live', badge: 'live', items: data.top_live.slice(0, 4) },
        { id: 'watchlist', title: 'On the watchlist', badge: null, items: data.watchlist.slice(0, 3) },
      ]
    : []
  const any = sections.some((s) => s.items.length > 0)
  return (
    <aside className="anpr-try" aria-label="Plates to try">
      <h3>Plates to try</h3>
      {suggest.status === 'loading' && (
        <div className="try-loading">
          <div className="skeleton" />
          <div className="skeleton" />
        </div>
      )}
      {suggest.status === 'error' && (
        <p className="try-empty">Suggestions unavailable — type any plate instead.</p>
      )}
      {suggest.status === 'ready' && !any && (
        <p className="try-empty">
          No plates read yet. Once the workers read traffic — or the labelled demo vehicle is
          injected — the plates worth trying appear here.
        </p>
      )}
      {sections
        .filter((s) => s.items.length > 0)
        .map((s) => (
          <div key={s.id} className="try-section" data-section={s.id}>
            <span className="try-title">{s.title}</span>
            <div className="try-chips">
              {s.items.map((it) => (
                <button
                  key={`${s.id}-${it.plate}`}
                  type="button"
                  className="try-chip"
                  data-plate={it.plate}
                  onClick={() => onPick(it.plate)}
                  title={
                    it.reads
                      ? `${it.reads} read(s) on ${it.cameras} camera(s) — last seen ${formatTs(it.last_seen)}`
                      : 'on the watchlist — not seen yet'
                  }
                >
                  <span className="plate">{it.plate}</span>
                  {(s.badge || it.provenance) && it.reads > 0 && (
                    <ProvenanceBadge provenance={s.badge || it.provenance} />
                  )}
                  {it.on_watchlist && s.id !== 'watchlist' && (
                    <span className="wl-dot" aria-label="on the watchlist" title="on the watchlist" />
                  )}
                  <span className="try-meta num">
                    {it.reads ? `${it.reads}× · ${it.cameras} cam` : 'not seen'}
                  </span>
                </button>
              ))}
            </div>
          </div>
        ))}
      {any && (
        <p className="try-legend">
          <span className="wl-dot" aria-hidden="true" /> on the watchlist · a click searches the
          plate ANPR-tolerant
        </p>
      )}
    </aside>
  )
}

function PlateGroups({ groups }) {
  const shown = groups.slice(0, GROUPS_SHOWN)
  return (
    <div className="plate-groups" aria-label="Registrations found">
      {shown.map((g) => (
        <article key={g.key} className={`plate-group tier-${g.matchType || 'none'}`} data-plate={g.key}>
          <div className="group-crop">
            {g.best ? (
              <img src={g.best.crop_url} alt={`best crop of ${g.key}`} />
            ) : (
              <span className="crop-none">no crop</span>
            )}
          </div>
          <div className="group-id">
            <b className="plate group-plate">{g.key}</b>
            <div className="group-badges">
              <MatchChip matchType={g.matchType} distance={g.matchDistance} />
              {[...g.provenances].map((p) => (
                <ProvenanceBadge key={p} provenance={p} />
              ))}
            </div>
            {g.spellings.size > 1 || !g.spellings.has(g.key) ? (
              <div className="group-spellings">
                also read as
                {[...g.spellings]
                  .filter((s) => s !== g.key)
                  .map((s) => (
                    <span key={s} className="plate">
                      {s}
                    </span>
                  ))}
              </div>
            ) : null}
          </div>
          <div className="group-facts">
            <div className="group-stats">
              <span className="group-stat">
                <b className="num">{g.rows.length}</b> read{g.rows.length === 1 ? '' : 's'}
              </span>
              <span className="group-stat">
                <b className="num">{g.cameras.size}</b> camera{g.cameras.size === 1 ? '' : 's'}
              </span>
              <span className="group-depts">
                {g.departments.map((d) => (
                  <span key={d} className="dept-inline">
                    <i className="dept-dot" style={{ background: deptColor(d) }} />
                    {d}
                  </span>
                ))}
              </span>
            </div>
            <div className="group-times num">
              <span>
                <em>First</em> {formatTs(g.first)}
              </span>
              <span>
                <em>Last</em> {formatTs(g.last)}
              </span>
            </div>
          </div>
          <div className="group-actions">
            {g.watch ? (
              <span className="wl-hit" title={g.watch.description || 'watchlist entry'}>
                Watchlist hit · {String(g.watch.category || '').replace(/_/g, ' ')} ·{' '}
                <SeverityWord severity={g.watch.severity} />
              </span>
            ) : (
              <span className="wl-clear">Not on the watchlist</span>
            )}
            <Link className="btn group-route" to={`/route/${encodeURIComponent(g.key)}`}>
              Show route ›
            </Link>
          </div>
        </article>
      ))}
      {groups.length > GROUPS_SHOWN && (
        <p className="groups-more muted">
          +{groups.length - GROUPS_SHOWN} more registration(s) in the reads below.
        </p>
      )}
    </div>
  )
}

/** A stored plate with the characters that differ from its registration
 *  (the coerced form) marked — an OCR look-alike is visible at a glance. */
function StoredPlate({ plate, registration }) {
  if (!registration || registration === plate || registration.length !== plate.length) {
    return <b className="plate row-plate">{plate}</b>
  }
  return (
    <b className="plate row-plate" title={`registration ${registration}`}>
      {[...plate].map((ch, i) =>
        ch === registration[i] ? (
          <span key={i}>{ch}</span>
        ) : (
          <mark key={i} className="ocr-char" title={`OCR look-alike of ${registration[i]}`}>
            {ch}
          </mark>
        )
      )}
    </b>
  )
}

function ConfBar({ value }) {
  const v = Number(value)
  if (!Number.isFinite(v)) return <span className="muted">—</span>
  const pct = Math.max(0, Math.min(100, Math.round(v * 100)))
  return (
    <span className={`conf ${v < 0.6 ? 'low' : ''}`} title={`OCR confidence ${v.toFixed(3)}`}>
      <span className="conf-bar" aria-hidden="true">
        <i style={{ width: `${pct}%` }} />
      </span>
      <span className="num">{v.toFixed(2)}</span>
    </span>
  )
}

function EmptyState({ query, match, narrowed, filtered, onContains }) {
  if (narrowed) {
    return (
      <div className="state-empty">
        No sightings of that vehicle class on this page.
        <span className="hint">Press Search to filter the full set on the server.</span>
      </div>
    )
  }
  if (!query) {
    return filtered ? (
      <div className="state-empty">
        No sightings match these filters.
        <span className="hint">Widen the filters — the camera, provenance or confidence.</span>
      </div>
    ) : (
      <div className="state-empty">
        No sightings recorded yet.
        <span className="hint">
          Reads appear here as soon as the ANPR workers see traffic; the labelled demo vehicle
          appears once it is injected.
        </span>
      </div>
    )
  }
  return (
    <div className="state-empty">
      No sightings of <b className="plate">{query.normalised}</b>
      {match === 'anpr' ? ' — not even an OCR look-alike.' : ` (${match}).`}
      <span className="hint">
        Check the characters, widen the filters, or search a shorter fragment.
      </span>
      {match !== 'contains' && (
        <button type="button" className="empty-action" onClick={onContains}>
          Search as Contains
        </button>
      )}
    </div>
  )
}
