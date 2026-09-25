import { useState } from 'react'
import { deptClass } from '../../lib/pins.js'

// The Map page legend: departments with counts, what a pin's shape, ring
// and opacity mean, and what each analysis layer shows. Nothing is said
// by colour alone — every swatch has a word beside it.

// open by default only where it leaves the map room (a 1366x768 laptop
// starts with it folded; one click opens it)
const roomy = () => window.innerHeight >= 900

export default function MapLegend({ depts, counts, layers, hours, bubbleZoom }) {
  const [open, setOpen] = useState(roomy)
  return (
    <section className={`gis-legend ${open ? 'is-open' : ''}`} aria-label="Map legend" id="map-legend">
      <button
        type="button"
        className="gis-legend-toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        Legend <span aria-hidden="true">{open ? '▾' : '▸'}</span>
      </button>
      {open && (
        <div className="gis-legend-body">
          <h4>Departments</h4>
          <ul className="gis-legend-depts">
            {depts.map((d) => (
              <li key={d.dept}>
                <span className={`lg-swatch ${deptClass(d.dept)}`} aria-hidden="true" />
                <span className="lg-name">{d.dept}</span>
                <span className="lg-count num" title={`${d.online} online of ${d.total}`}>
                  {d.online}/{d.total}
                </span>
              </li>
            ))}
          </ul>
          <p className="lg-foot">online / registered</p>

          <h4>Cameras</h4>
          <ul className="gis-legend-keys">
            <li>
              <span className="lg-pin lg-pin--sandbox" aria-hidden="true" />
              Sandbox grid <span className="lg-count num">{counts.sandbox}</span>
            </li>
            <li>
              <span className="lg-pin lg-pin--local" aria-hidden="true" />
              Local / onboarded feed <span className="lg-count num">{counts.local}</span>
            </li>
            <li>
              <span className="lg-pin lg-pin--sandbox lg-pin--ring" aria-hidden="true" />
              Analysed — ANPR worker <span className="lg-count num">{counts.analysed}</span>
            </li>
            <li>
              <span className="lg-pin lg-pin--sandbox lg-pin--faded" aria-hidden="true" />
              Faded — offline or health unknown
            </li>
            <li>
              <span className="lg-bubble" aria-hidden="true">5</span>
              Cluster count, below zoom {bubbleZoom}
            </li>
          </ul>
          {counts.unlocated > 0 && (
            <p className="lg-foot">{counts.unlocated} registered without coordinates — not on the map</p>
          )}

          <h4>Layers</h4>
          <ul className="gis-legend-keys">
            <li className={layers.coverage ? '' : 'is-off'}>
              <span className="lg-wedge" aria-hidden="true" />
              Coverage — field of view, street zoom; dashed = assumed
            </li>
            <li className={layers.activity ? '' : 'is-off'}>
              <span className="lg-activity" aria-hidden="true" />
              Activity — plate reads, last {hours} h; red edge = alerts
            </li>
            <li className={layers.clusters ? '' : 'is-off'}>
              <span className="lg-hull" aria-hidden="true" />
              Clusters — cameras within 15 km
            </li>
            <li className={layers.gaps ? '' : 'is-off'}>
              <span className="lg-gap" aria-hidden="true" />
              Gaps — offline, or no neighbour within 5 km
            </li>
          </ul>
        </div>
      )}
    </section>
  )
}
