import { DEPT_COLORS } from '../lib/api.js'

// Department colour legend — the one shared palette (docs/api.md §1).
// `depts` limits the rows to departments actually present.
export default function DeptLegend({ depts }) {
  const rows = Object.entries(DEPT_COLORS).filter(
    ([d]) => !depts || depts.includes(d)
  )
  return (
    <div className="legend" aria-label="Department colours">
      {rows.map(([d, col]) => (
        <div className="row" key={d}>
          <span className="sw" style={{ background: col }} aria-hidden="true" /> {d}
        </div>
      ))}
    </div>
  )
}
