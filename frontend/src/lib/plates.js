// Plate grammar for DISPLAY ONLY — the live preview under the Search input
// and the grouping of result rows by registration. It mirrors
// backend/core/plates.py (docs/api.md §6), which stays the one
// implementation that decides anything: the search response's `query`
// echo ({normalised, canonical, kind, coerced}) is authoritative, and
// tests/test_plates_js_parity.py runs this file under node against the
// Python module so the two cannot drift silently.

// ambiguity classes: letter -> digit fold, and the reverse where a letter
// is expected (Q is not a target: 0 coerces to O)
const TO_DIGIT = { O: '0', I: '1', S: '5', B: '8', Z: '2', G: '6', Q: '0' }
const TO_LETTER = { 0: 'O', 1: 'I', 5: 'S', 8: 'B', 2: 'Z', 6: 'G' }

const STATE_CODES = new Set(
  (
    'AN AP AR AS BR CG CH DD DL DN GA GJ HP HR JH JK KA KL LA LD MH ML MN MP ' +
    'MZ NL OD OR PB PY RJ SK TN TR TS UK UP WB'
  ).split(' ')
)

const STD_RE = /^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{4}$/
const BH_RE = /^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$/
const STD_SHAPES = [1, 2, 3].map((k) => 'LLDD' + 'L'.repeat(k) + 'DDDD')
const BH_SHAPES = [1, 2].map((k) => 'DDBHDDDD' + 'L'.repeat(k))

const isAlpha = (c) => c >= 'A' && c <= 'Z'
const isDigit = (c) => c >= '0' && c <= '9'

/** Uppercase and strip everything that is not A-Z0-9. */
export function normalise(raw) {
  return String(raw || '')
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, '')
}

/** The ambiguity fold used for indexing (O->0, I->1, S->5, B->8, Z->2, G->6, Q->0). */
export function canonical(plate) {
  return [...normalise(plate)].map((c) => TO_DIGIT[c] || c).join('')
}

function coerceOnto(s, shape) {
  if (s.length !== shape.length) return null
  let out = ''
  for (let i = 0; i < s.length; i += 1) {
    let c = s[i]
    const want = shape[i]
    if (want === 'L') {
      c = TO_LETTER[c] || c
      if (!isAlpha(c)) return null
    } else if (want === 'D') {
      c = TO_DIGIT[c] || c
      if (!isDigit(c)) return null
    } else {
      c = TO_LETTER[c] || c
      if (c !== want) return null
    }
    out += c
  }
  return out
}

function fullForm(s, coerce) {
  for (const shape of STD_SHAPES) {
    const cand = coerce ? coerceOnto(s, shape) : s.length === shape.length ? s : null
    if (cand && STD_RE.test(cand) && STATE_CODES.has(cand.slice(0, 2))) return cand
  }
  for (const shape of BH_SHAPES) {
    const cand = coerce ? coerceOnto(s, shape) : s.length === shape.length ? s : null
    if (cand && BH_RE.test(cand)) return cand
  }
  return null
}

function matchesPrefix(s, shape) {
  for (let i = 0; i < s.length && i < shape.length; i += 1) {
    const c = s[i]
    const want = shape[i]
    if (want === 'L' ? !isAlpha(c) : want === 'D' ? !isDigit(c) : c !== want) return false
  }
  return true
}

function isStructuralPrefix(s) {
  for (const shape of STD_SHAPES) {
    if (s.length < shape.length && matchesPrefix(s, shape)) {
      if (s.length >= 2 && !STATE_CODES.has(s.slice(0, 2))) continue
      return true
    }
  }
  return BH_SHAPES.some((shape) => s.length < shape.length && matchesPrefix(s, shape))
}

/** 'full' | 'partial' | null — the §6 classification (F40 ordering). */
export function plateLike(raw) {
  const s = normalise(raw)
  if (!s) return null
  if (fullForm(s, false)) return 'full'
  if (s.length >= 4 && isStructuralPrefix(s)) return 'partial'
  if (fullForm(s, true)) return 'full'
  return null
}

/** The coerced registration of a full read, or null (backend plates.coerce). */
export function coerce(raw) {
  const s = normalise(raw)
  if (plateLike(s) !== 'full') return null
  return fullForm(s, false) || fullForm(s, true)
}

/** Positions where the coerced form differs from the normalised one:
 *  [{index, from, to}] — the preview highlights them. */
export function corrections(raw) {
  const s = normalise(raw)
  const c = coerce(s)
  if (!c) return []
  const out = []
  for (let i = 0; i < s.length; i += 1) {
    if (s[i] !== c[i]) out.push({ index: i, from: s[i], to: c[i] })
  }
  return out
}

/** The registration as printed on a plate: "GJ 01 AB 1234" / "22 BH 1234 AA". */
export function spaced(plate) {
  const p = normalise(plate)
  if (plateLike(p) !== 'full' || coerce(p) !== p) return p
  if (p.slice(2, 4) === 'BH' && isDigit(p[0])) {
    return `${p.slice(0, 2)} BH ${p.slice(4, 8)} ${p.slice(8)}`
  }
  return `${p.slice(0, 2)} ${p.slice(2, 4)} ${p.slice(4, -4)} ${p.slice(-4)}`
}
