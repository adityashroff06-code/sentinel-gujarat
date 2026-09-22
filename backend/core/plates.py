"""Plate grammar, canonicalisation and matching — the ONE implementation
(docs/api.md §6; decision F21). No other module may duplicate these rules.

All functions accept raw or normalised input; they normalise first, so the
grammar has a single entry point. The ambiguity map is applied only during
canonicalisation and matching, never to the stored `plate`/`plate_raw`.
"""

from __future__ import annotations

import re

from backend.core import config

# Ambiguity classes (docs/api.md §6): letter -> digit fold.
_TO_DIGIT = {"O": "0", "I": "1", "S": "5", "B": "8", "Z": "2", "G": "6", "Q": "0"}
# Position-aware coercion where a LETTER is expected (the reverse map; Q is
# not a target because 0 coerces to O).
_TO_LETTER = {"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z", "6": "G"}

STATE_CODES = frozenset(
    "AN AP AR AS BR CG CH DD DL DN GA GJ HP HR JH JK KA KL LA LD MH ML MN MP "
    "MZ NL OD OR PB PY RJ SK TN TR TS UK UP WB".split()
)

_STD_RE = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{4}$")
_BH_RE = re.compile(r"^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$")

# Shape strings: L = any letter, D = any digit; a literal char must match itself.
_STD_SHAPES = ["LLDD" + "L" * k + "DDDD" for k in (1, 2, 3)]        # len 9-11
_BH_SHAPES = ["DDBH" + "DDDD" + "L" * k for k in (1, 2)]            # len 9-10


def normalise(raw: str) -> str:
    """Uppercase and strip everything that is not A-Z0-9."""
    return re.sub(r"[^A-Z0-9]", "", raw.upper())


def canonical(plate: str) -> str:
    """Fold the ambiguity map to one form for indexing (O→0, I→1, S→5,
    B→8, Z→2, G→6, Q→0). Input is normalised first."""
    return "".join(_TO_DIGIT.get(c, c) for c in normalise(plate))


def _coerce(s: str, shape: str) -> str | None:
    """Coerce *s* onto *shape* position by position; None when impossible."""
    if len(s) != len(shape):
        return None
    out: list[str] = []
    for c, want in zip(s, shape):
        if want == "L":
            c = _TO_LETTER.get(c, c)
            if not c.isalpha():
                return None
        elif want == "D":
            c = _TO_DIGIT.get(c, c)
            if not c.isdigit():
                return None
        else:  # literal (the BH infix)
            c = _TO_LETTER.get(c, c)
            if c != want:
                return None
        out.append(c)
    return "".join(out)


def _is_full(s: str, coerce: bool) -> bool:
    for shape in _STD_SHAPES:
        candidate = _coerce(s, shape) if coerce else (s if len(s) == len(shape) else None)
        if candidate and _STD_RE.fullmatch(candidate) and candidate[:2] in STATE_CODES:
            return True
    for shape in _BH_SHAPES:
        candidate = _coerce(s, shape) if coerce else (s if len(s) == len(shape) else None)
        if candidate and _BH_RE.fullmatch(candidate):
            return True
    return False


def plate_like(s: str) -> str | None:
    """``"full"`` | ``"partial"`` | ``None`` per docs/api.md §6.

    An uncoerced structural prefix outranks a coercion-dependent full parse
    (decision F40): a read that is full only because a clean letter was
    coerced to a digit, but that also reads as a truncated plate as-is
    (e.g. ``GJ05JB432``), is treated as partial, never coerced into a
    different full registration.
    """
    s = normalise(s)
    if not s:
        return None
    if _is_full(s, coerce=False):
        return "full"
    if len(s) >= 4 and _is_structural_prefix(s):
        return "partial"
    if _is_full(s, coerce=True):
        return "full"
    return None


def _matches_prefix(s: str, shape: str) -> bool:
    """Does *s*, uncoerced, match the first len(s) positions of *shape*?"""
    for c, want in zip(s, shape):
        if want == "L":
            if not c.isalpha():
                return False
        elif want == "D":
            if not c.isdigit():
                return False
        elif c != want:
            return False
    return True


def _is_structural_prefix(s: str) -> bool:
    """A proper, uncoerced prefix of either full form (docs/api.md §6)."""
    for shape in _STD_SHAPES:
        if len(s) < len(shape) and _matches_prefix(s, shape):
            if len(s) >= 2 and s[:2] not in STATE_CODES:
                continue
            return True
    return any(len(s) < len(shape) and _matches_prefix(s, shape) for shape in _BH_SHAPES)


def is_partial(s: str) -> bool:
    """Partial reads never alert and never fuzzy-match."""
    return plate_like(s) != "full"


def _weighted_distance(a: str, b: str) -> float:
    """Confusion-weighted edit distance: a substitution inside an ambiguity
    class costs 0.25; any other substitution or indel costs 1.0."""
    la, lb = len(a), len(b)
    prev = [float(j) for j in range(lb + 1)]
    for i in range(1, la + 1):
        cur = [float(i)] + [0.0] * lb
        ca = a[i - 1]
        for j in range(1, lb + 1):
            cb = b[j - 1]
            if ca == cb:
                sub = prev[j - 1]
            else:
                cost = 0.25 if _TO_DIGIT.get(ca, ca) == _TO_DIGIT.get(cb, cb) else 1.0
                sub = prev[j - 1] + cost
            cur[j] = min(sub, prev[j] + 1.0, cur[j - 1] + 1.0)
        prev = cur
    return prev[lb]


def plate_match(a: str, b: str) -> tuple[bool, float, str]:
    """``(matched, distance, rule)`` with rule ∈ exact | ambiguity | fuzzy | none.

    exact → ambiguity (same length, differs only inside ambiguity classes) →
    fuzzy (both sides `full`, weighted distance ≤ 1.0) → none. Partial reads
    never fuzzy-match.
    """
    na, nb = normalise(a), normalise(b)
    if na == nb:
        return True, 0.0, "exact"
    if len(na) == len(nb) and canonical(na) == canonical(nb):
        return True, 0.0, "ambiguity"
    distance = _weighted_distance(na, nb)
    if distance <= 1.0 and plate_like(na) == "full" and plate_like(nb) == "full":
        return True, distance, "fuzzy"
    return False, distance, "none"


def alertable(rule: str) -> bool:
    """Alert policy (decision F21): exact and ambiguity always; fuzzy only
    when SENTINEL_ALERT_ON_FUZZY is set; none never."""
    return rule in ("exact", "ambiguity") or (rule == "fuzzy" and config.alert_on_fuzzy())
