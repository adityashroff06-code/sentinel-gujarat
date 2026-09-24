"""Route reconstruction — the response the whole submission turns on.

Ported from ``D:\\projects\\Sentinel_Repo\\src\\analytics\\route.py`` (F52)
and adapted to this repo's schema and ``docs/api.md`` §7:

- candidates come from the ``plate_canonical`` index — exact and ambiguity
  matches by canonical equality, fuzzy candidates only among plates sharing
  the first four canonical characters (B9; never a whole-table Levenshtein
  scan, the old build's defect D6) and only when the query itself is
  structurally ``full`` (partial reads never fuzzy-match, §6);
- stops are ordered by ``seen_at`` and **grouped by ``clock_source``**:
  elapsed time and implied speed are computed only within a group, and a
  ``warnings[]`` entry explains every boundary (B6, decision F13);
- same-camera stops within 2 minutes collapse into one (B2), Haversine
  distance and implied speed per leg, ``suspect`` on implausible speed,
  ``departments_crossed`` in order of first appearance, coverage ``gaps``.
"""

from __future__ import annotations

import datetime as dt
import math
import sqlite3
from typing import Any

from backend.core import plates

#: Consecutive sightings on the same camera (same clock) within this window
#: collapse into one stop (docs/api.md B2).
DWELL_COLLAPSE_S = 120.0
#: A same-clock time gap larger than this between stops is flagged as a
#: coverage gap (threshold configurable here; docs/api.md B2).
GAP_FLAG_MINUTES = 8.0
#: Implied speeds above this are physically implausible -> suspect stop.
SUSPECT_SPEED_KMH = 150.0
#: Fuzzy candidates are searched only among plates sharing this many
#: canonical prefix characters (docs/api.md B9, mirrors backend.core.matcher).
_FUZZY_PREFIX_LEN = 4

_SELECT = (
    "SELECT s.*, c.department, c.location_name, c.lat, c.lon"
    " FROM sightings s JOIN cameras c ON c.camera_id = s.camera_id"
    " WHERE s.confidence >= ?"
)

_MODE_RANK = {"none": 0, "exact": 1, "ambiguity": 2, "fuzzy": 3}


def crop_url(crop_path: str | None) -> str | None:
    """Public URL for a stored crop path (Windows backslashes included).

    Returns None when there is no crop.
    """
    if not crop_path:
        return None
    return f"/crops/{crop_path.replace(chr(92), '/').split('crops/')[-1]}"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _parse(ts: str) -> dt.datetime:
    d = dt.datetime.fromisoformat(ts)
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _candidates(
    con: sqlite3.Connection, qn: str, qc: str, min_confidence: float
) -> list[tuple[sqlite3.Row, str, float]]:
    """(row, match_type, match_distance) per candidate sighting, unsorted."""
    cand: list[tuple[sqlite3.Row, str, float]] = []
    for r in con.execute(_SELECT + " AND s.plate_canonical = ?", (min_confidence, qc)):
        mtype = "exact" if r["plate"] == qn else "ambiguity"
        cand.append((r, mtype, 0.0))

    # Fuzzy candidates: only full queries, only the canonical-prefix bucket.
    if plates.plate_like(qn) != "full" or len(qc) < _FUZZY_PREFIX_LEN:
        return cand
    fuzzy_plates: dict[str, float] = {}
    for (p,) in con.execute(
        "SELECT DISTINCT plate FROM sightings"
        " WHERE substr(plate_canonical, 1, ?) = ? AND plate_canonical != ?",
        (_FUZZY_PREFIX_LEN, qc[:_FUZZY_PREFIX_LEN], qc),
    ):
        matched, distance, rule = plates.plate_match(qn, p)
        if matched and rule == "fuzzy":
            fuzzy_plates[p] = distance
    if fuzzy_plates:
        marks = ",".join("?" for _ in fuzzy_plates)
        for r in con.execute(
            _SELECT + f" AND s.plate IN ({marks})",
            (min_confidence, *fuzzy_plates),
        ):
            cand.append((r, "fuzzy", fuzzy_plates[r["plate"]]))
    return cand


def reconstruct_route(
    con: sqlite3.Connection, query_plate: str, min_confidence: float = 0.0
) -> dict[str, Any]:
    """Build the ``GET /api/plates/{plate}/route`` response (docs/api.md §7).

    Returns the contract dict (stops, gaps, warnings, movement summary).
    Raises nothing on an unknown plate — the route is simply empty.
    """
    qn = plates.normalise(query_plate)
    qc = plates.canonical(qn)
    cand = _candidates(con, qn, qc, min_confidence) if qn else []
    cand.sort(key=lambda x: (_parse(x[0]["seen_at"]), x[0]["sighting_id"]))

    match_mode = "none"
    for _, mtype, _ in cand:
        if _MODE_RANK[mtype] > _MODE_RANK[match_mode]:
            match_mode = mtype

    # Collapse consecutive same-camera, same-clock sightings within the
    # dwell window, keeping the higher-confidence representative.
    collapsed: list[tuple[sqlite3.Row, str, float]] = []
    for r, mtype, distance in cand:
        if collapsed:
            pr, _pm, _pd = collapsed[-1]
            if (
                pr["camera_id"] == r["camera_id"]
                and pr["clock_source"] == r["clock_source"]
                and (_parse(r["seen_at"]) - _parse(pr["seen_at"])).total_seconds()
                <= DWELL_COLLAPSE_S
            ):
                if r["confidence"] > pr["confidence"]:
                    collapsed[-1] = (r, mtype, distance)
                continue
        collapsed.append((r, mtype, distance))

    stops: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    warnings: list[str] = []
    prev: sqlite3.Row | None = None
    prev_seen: dt.datetime | None = None
    total_km = 0.0
    for i, (r, mtype, distance) in enumerate(collapsed, 1):
        seen = _parse(r["seen_at"])
        elapsed: int | None = None
        speed: float | None = None
        if prev is not None and prev_seen is not None:
            km: float | None = None
            if None not in (prev["lat"], prev["lon"], r["lat"], r["lon"]):
                km = _haversine_km(prev["lat"], prev["lon"], r["lat"], r["lon"])
                total_km += km
            if r["clock_source"] == prev["clock_source"]:
                elapsed = round((seen - prev_seen).total_seconds())
                if km is not None and elapsed > 0:
                    speed = round(km / (elapsed / 3600.0), 1)
                if elapsed > GAP_FLAG_MINUTES * 60:
                    gaps.append(
                        {
                            "after_sequence": i - 1,
                            "minutes": round(elapsed / 60),
                            "note": "no camera coverage on this corridor",
                        }
                    )
            else:
                # Never compute time or speed across clock domains (B6).
                warnings.append(
                    f"stops {i - 1}-{i} come from a different clock"
                    f" ({r['clock_source']}); elapsed time and speed not"
                    " computed across the boundary"
                )
        stops.append(
            {
                "sequence": i,
                "camera_id": r["camera_id"],
                "department": r["department"],
                "location_name": r["location_name"],
                "lat": r["lat"],
                "lon": r["lon"],
                "seen_at": r["seen_at"],
                "clock_source": r["clock_source"],
                "provenance": r["provenance"],
                "plate_raw": r["plate_raw"],
                "confidence": round(r["confidence"], 3),
                "match_type": mtype,
                "match_distance": distance,
                "suspect": bool(speed is not None and speed > SUSPECT_SPEED_KMH),
                "crop_url": crop_url(r["crop_path"]),
                "elapsed_from_previous_s": elapsed,
                "implied_speed_kmh": speed,
            }
        )
        prev, prev_seen = r, seen

    departments: list[str] = []
    for s in stops:
        if s["department"] and s["department"] not in departments:
            departments.append(s["department"])

    first = stops[0]["seen_at"] if stops else None
    last = stops[-1]["seen_at"] if stops else None
    duration = round((_parse(last) - _parse(first)).total_seconds()) if stops else None

    return {
        "query_plate": query_plate,
        "normalised": qn,
        "match_mode": match_mode,
        "total_sightings": len(cand),
        "first_seen": first,
        "last_seen": last,
        "duration_seconds": duration,
        "distance_km": round(total_km, 1),
        "departments_crossed": departments,
        "stops": stops,
        "gaps": gaps,
        "warnings": warnings,
    }
