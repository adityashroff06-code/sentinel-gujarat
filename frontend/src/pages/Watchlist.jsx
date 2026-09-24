import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api.js'
import { roleAtLeast, useSession } from '../lib/session.js'
import { formatTs } from '../lib/time.js'

// Watchlist (docs/api.md §3): table, add form (category/severity/reason),
// remove. Add and remove are evaluator+ actions — hidden below that role,
// and the API refuses them anyway (decision F41). New screen in this
// build — the demo script shows this table (frontend/CLAUDE.md).

const CATEGORIES = [
  'stolen_vehicle',
  'wanted_person',
  'missing_person',
  'blacklisted',
  'suspect',
]
const SEVERITIES = ['high', 'medium', 'low']

const SEV_VAR = {
  critical: 'var(--sev-critical)',
  high: 'var(--sev-high)',
  medium: 'var(--sev-medium)',
  low: 'var(--sev-low)',
}

const EMPTY = { plate: '', category: 'stolen_vehicle', severity: 'high', reason: '', source_ref: '' }

export default function Watchlist() {
  const session = useSession()
  const canEdit = roleAtLeast(session?.role, 'evaluator')

  const [state, setState] = useState({ status: 'loading', rows: [] })
  const [form, setForm] = useState(EMPTY)
  const [formError, setFormError] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      const rows = await api.watchlist()
      setState({ status: 'ready', rows })
    } catch {
      setState({ status: 'error', rows: [] })
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function add(e) {
    e.preventDefault()
    setBusy(true)
    setFormError(null)
    try {
      await api.addWatchlist({
        plate: form.plate.trim(),
        category: form.category,
        severity: form.severity,
        // the API stores the operator's reason in `description`
        // (docs/api.md §7: POST takes plate, category, severity,
        // description?, source_ref?)
        description: form.reason.trim() || null,
        source_ref: form.source_ref.trim() || null,
      })
      setForm(EMPTY)
      await load()
    } catch (err) {
      setFormError(err.detail || 'Could not add the plate.')
    } finally {
      setBusy(false)
    }
  }

  async function remove(id) {
    try {
      await api.removeWatchlist(id)
      await load()
    } catch {
      // surfaced on the status strip by the data layer
    }
  }

  return (
    <div className="page">
      <div className="card">
        <h2>
          Watchlist <span className="count num">{state.rows.length} plates</span>
        </h2>

        {state.status === 'loading' && (
          <div className="skeleton-rows" aria-label="Loading watchlist">
            {[0, 1, 2].map((i) => (
              <div key={i} className="skeleton" style={{ height: 30 }} />
            ))}
          </div>
        )}
        {state.status === 'error' && (
          <div className="state-error">
            Could not load the watchlist — see the status strip above.
          </div>
        )}
        {state.status === 'ready' && state.rows.length === 0 && (
          <div className="state-empty">
            The watchlist is empty.
            {canEdit ? (
              <span className="hint">Add a plate with the form below.</span>
            ) : (
              <span className="hint">An evaluator or admin can add plates.</span>
            )}
          </div>
        )}
        {state.status === 'ready' && state.rows.length > 0 && (
          <table className="watchlist-table">
            <thead>
              <tr>
                <th>Plate</th>
                <th>Category</th>
                <th>Severity</th>
                <th>Reason</th>
                <th>Case ref</th>
                <th>Added</th>
                <th>Status</th>
                {canEdit && <th aria-label="Actions" />}
              </tr>
            </thead>
            <tbody>
              {state.rows.map((w) => (
                <tr key={w.watchlist_id}>
                  <td className="plate">{w.plate}</td>
                  <td>{w.category.replace(/_/g, ' ')}</td>
                  <td>
                    <span
                      className="badge outline"
                      style={{ color: SEV_VAR[w.severity] ? undefined : 'var(--text-muted)' }}
                    >
                      <span style={{ color: SEV_VAR[w.severity] || 'var(--text-muted)' }}>
                        {w.severity}
                      </span>
                    </span>
                  </td>
                  <td>{w.description || w.reason || '—'}</td>
                  <td className="mono">{w.source_ref || '—'}</td>
                  <td className="num">{formatTs(w.added_at)}</td>
                  <td>{w.active ? 'active' : 'inactive'}</td>
                  {canEdit && (
                    <td>
                      <button className="danger" onClick={() => remove(w.watchlist_id)}>
                        Remove
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {canEdit && (
        <div className="card" id="add-watchlist">
          <h2>Add a plate</h2>
          <form className="form-row" onSubmit={add}>
            <div className="field">
              <label htmlFor="wl-plate">Registration *</label>
              <input
                id="wl-plate"
                className="plate"
                required
                placeholder="GJ01AB1234"
                value={form.plate}
                onChange={set('plate')}
              />
            </div>
            <div className="field">
              <label htmlFor="wl-category">Category</label>
              <select id="wl-category" value={form.category} onChange={set('category')}>
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c.replace(/_/g, ' ')}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="wl-severity">Severity</label>
              <select id="wl-severity" value={form.severity} onChange={set('severity')}>
                {SEVERITIES.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </div>
            <div className="field" style={{ flex: 1, minWidth: 200 }}>
              <label htmlFor="wl-reason">Reason</label>
              <input id="wl-reason" value={form.reason} onChange={set('reason')} />
            </div>
            <div className="field">
              <label htmlFor="wl-ref">Case ref</label>
              <input id="wl-ref" value={form.source_ref} onChange={set('source_ref')} />
            </div>
            <button className="primary" type="submit" disabled={busy}>
              {busy ? 'Adding…' : 'Add to watchlist'}
            </button>
          </form>
          {formError && <p className="form-error" role="alert">{formError}</p>}
        </div>
      )}
    </div>
  )
}
