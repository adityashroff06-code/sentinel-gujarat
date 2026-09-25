import { provenanceOf } from '../lib/api.js'

// Small shared badges (decision F46): provenance on every row in Search,
// Route, Alerts and Reports — a judge must never mistake a seeded row for
// a live read — plus the match-type and severity words (nothing is said
// by colour alone, frontend/CLAUDE.md).

/** Provenance badge. Pass `provenance` (sightings/route/events rows) or
 *  `clockSource` (alert rows, which store only the clock). */
export function ProvenanceBadge({ provenance, clockSource }) {
  const p = provenance || provenanceOf(clockSource)
  return (
    <span className={`prov-badge prov-${p}`} title={`data provenance: ${p}`}>
      {p}
    </span>
  )
}

/** Match-type chip: exact is quiet; ambiguity/fuzzy are flagged with the
 *  confusion-weighted distance so a near-miss is visibly a near-miss. */
export function MatchChip({ matchType, distance }) {
  if (!matchType || matchType === 'none') return null
  const d = Number(distance)
  return (
    <span className={`match-chip match-${matchType}`}>
      {matchType}
      {matchType !== 'exact' && Number.isFinite(d) ? ` d=${d}` : ''}
    </span>
  )
}

/** Severity word, colour-coded but always spelled out (incl. critical). */
export function SeverityWord({ severity }) {
  const s = severity || 'low'
  return <span className={`sev-word sev-${s}`}>{s.toUpperCase()}</span>
}
