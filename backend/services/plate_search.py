"""ANPR search over ``sightings`` and the "plates to try" suggestions
(ANPR search lane, 25 Sep; docs/api.md §7 ``GET /sightings``,
``GET /plates/suggest``).

Match modes for a plate query ``q`` (normalised, canonical ``qc``):

- ``contains`` (the default — unchanged behaviour): ``plate LIKE %q%``,
  newest first;
- ``exact``: ``plate = q``;
- ``anpr`` — OCR-tolerant, ranked **exact → ambiguity → fuzzy**, then
  newest first:

  * exact: ``plate = q``;
  * ambiguity: ``plate_canonical = qc`` (same registration up to the OCR
    ambiguity classes, §6) — served by the canonical index;
  * fuzzy (only when ``q`` is structurally ``full``): ``plates.plate_match``
    over the plates sharing the first four canonical characters (the B9
    bucket, a range scan on the canonical index — never the whole table),
    both sides full, confusion-weighted distance ≤ 1.0;
  * a **partial** query never fuzzy-matches (§6); instead it matches
    OCR-tolerantly as a fragment — ``plate_canonical LIKE %qc%`` — so
    ``GJ0I`` still finds every ``GJ01…`` read (``match_type='contains'``).

Every row carries ``match_type`` and ``match_distance`` (0 for exact and
ambiguity, the weighted distance for fuzzy, null for contains); ``total``
reuses the rows' WHERE (B11). Pure functions over a connection: the route
handler owns validation, auth and audit.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from backend.core import plates
from backend.core.db import utcnow
from backend.services.route import crop_url

#: Fuzzy candidates share this many canonical prefix characters (B9;
#: mirrors backend.core.matcher and backend.services.route).
FUZZY_PREFIX_LEN = 4

_TIER = {"exact": 0, "ambiguity": 1, "fuzzy": 2, "contains": 3}


def describe_query(plate: str) -> dict[str, Any]:
    """How the grammar reads a query: normalised, canonical, kind, coerced."""
    q = plates.normalise(plate)
    return {
        "plate": plate,
        "normalised": q,
        "canonical": plates.canonical(q),
        "kind": plates.plate_like(q),
        "coerced": plates.coerce(q),
    }


def fuzzy_plates(con: sqlite3.Connection, q: str, qc: str) -> dict[str, float]:
    """``{stored_plate: distance}`` for fuzzy neighbours of the full query *q*.

    Candidates are the distinct plates in *qc*'s four-character canonical
    bucket (an index range scan) other than *qc* itself; only
    ``plate_match`` rule ``fuzzy`` survives (both full, distance ≤ 1.0).
    """
    if plates.plate_like(q) != "full" or len(qc) < FUZZY_PREFIX_LEN:
        return {}
    prefix = qc[:FUZZY_PREFIX_LEN]
    out: dict[str, float] = {}
    for (candidate,) in con.execute(
        "SELECT DISTINCT plate FROM sightings"
        " WHERE plate_canonical >= ? AND plate_canonical < ? AND plate_canonical != ?",
        # canonical text is A-Z0-9 only, so prefix + '~' bounds the bucket
        (prefix, prefix + "~", qc),
    ):
        matched, distance, rule = plates.plate_match(q, candidate)
        if matched and rule == "fuzzy":
            out[candidate] = distance
    return out


def search_sightings(
    con: sqlite3.Connection,
    *,
    plate: str | None,
    match: str,
    camera_id: str | None,
    from_iso: str | None,
    to_iso: str | None,
    min_confidence: float,
    provenance: str | None,
    vehicle_class: str | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    """The ``GET /api/sightings`` body: ``{match, query, total, count,
    sightings}``. *from_iso*/*to_iso* are already canonicalised (B6)."""
    where: list[str] = ["s.confidence >= ?"]
    params: list[Any] = [min_confidence]
    if vehicle_class:
        where.append("s.vehicle_class = ?")
        params.append(vehicle_class)
    if camera_id:
        where.append("s.camera_id = ?")
        params.append(camera_id)
    if from_iso:
        where.append("s.seen_at >= ?")
        params.append(from_iso)
    if to_iso:
        where.append("s.seen_at <= ?")
        params.append(to_iso)
    if provenance:
        where.append("s.provenance = ?")
        params.append(provenance)

    q = plates.normalise(plate) if plate else ""
    qc = plates.canonical(q)
    query = describe_query(plate) if plate else None
    fuzzy: dict[str, float] = {}
    order = "s.seen_at DESC, s.sighting_id DESC"
    order_params: list[Any] = []
    if q:
        if match == "exact":
            where.append("s.plate = ?")
            params.append(q)
        elif match == "anpr":
            clauses, cparams = ["s.plate = ?", "s.plate_canonical = ?"], [q, qc]
            if plates.plate_like(q) == "full":
                fuzzy = fuzzy_plates(con, q, qc)
                if fuzzy:
                    clauses.append(f"s.plate IN ({','.join('?' for _ in fuzzy)})")
                    cparams.extend(fuzzy)
            else:
                # a fragment: OCR-tolerant contains on the canonical fold
                clauses.append("s.plate_canonical LIKE ?")
                cparams.append(f"%{qc}%")
            where.append("(" + " OR ".join(clauses) + ")")
            params.extend(cparams)
            tier_sql = "CASE WHEN s.plate = ? THEN 0 WHEN s.plate_canonical = ? THEN 1"
            order_params = [q, qc]
            if fuzzy:
                tier_sql += f" WHEN s.plate IN ({','.join('?' for _ in fuzzy)}) THEN 2"
                order_params.extend(fuzzy)
            order = tier_sql + " ELSE 3 END, " + order
        else:  # contains — the unchanged default
            where.append("s.plate LIKE ?")
            params.append(f"%{q}%")

    base = (" FROM sightings s JOIN cameras c ON c.camera_id = s.camera_id WHERE "
            + " AND ".join(where))
    rows = [
        dict(r)
        for r in con.execute(
            "SELECT s.*, c.department, c.location_name" + base
            + f" ORDER BY {order} LIMIT ? OFFSET ?",
            [*params, *order_params, limit, offset],
        )
    ]
    total = con.execute("SELECT COUNT(*)" + base, params).fetchone()[0]
    for r in rows:
        r["crop_url"] = crop_url(r.get("crop_path"))
        r["match_type"], r["match_distance"] = _classify(r, q, qc, match, fuzzy)
    return {"match": match, "query": query, "total": total, "count": len(rows),
            "sightings": rows}


def _classify(row: dict[str, Any], q: str, qc: str, match: str,
              fuzzy: dict[str, float]) -> tuple[str | None, float | None]:
    """``(match_type, match_distance)`` of one row against the query."""
    if not q:
        return None, None
    if row["plate"] == q:
        return "exact", 0.0
    if match == "anpr" and row["plate_canonical"] == qc:
        return "ambiguity", 0.0
    if row["plate"] in fuzzy:
        return "fuzzy", fuzzy[row["plate"]]
    return "contains", None


# ----------------------------------------------------------------- suggest

def _watch_canonicals(con: sqlite3.Connection) -> set[str]:
    """Canonical forms of the active, unexpired watchlist (F39) — the
    same rows the matcher caches (the demo seeder stores an empty
    ``plate_canonical``, so the fold is recomputed like the matcher does)."""
    now = utcnow()
    return {
        r["plate_canonical"] or plates.canonical(r["plate"])
        for r in con.execute(
            "SELECT plate, plate_canonical FROM watchlist WHERE active = 1"
            " AND (expires_at IS NULL OR expires_at > ?)", (now,))
    }


def _demo_groups(con: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in con.execute(
            "SELECT plate, MAX(plate_canonical) AS plate_canonical, COUNT(*) AS reads,"
            " COUNT(DISTINCT camera_id) AS cameras, MAX(seen_at) AS last_seen"
            " FROM sightings WHERE provenance = 'demo' GROUP BY plate"
        )
    ]


def suggest(con: sqlite3.Connection, limit: int) -> dict[str, list[dict[str, Any]]]:
    """``{demo, watchlist, top_live}`` — plates worth typing into Search.

    - ``demo``: the labelled demo plates (provenance ``demo``), watchlisted
      ones first, then by reads;
    - ``watchlist``: active entries, seen ones first (reads over every
      provenance, joined on the canonical fold), then by severity;
    - ``top_live``: the most-read structurally full plates with provenance
      ``live``, grouped by their coerced form so an OCR twin that predates
      the coercion (``6J23H1548``/``GJ23H1548``) counts as one plate.
    """
    watch = _watch_canonicals(con)

    demo = _demo_groups(con)
    for g in demo:
        g["provenance"] = "demo"
        g["on_watchlist"] = g["plate_canonical"] in watch
    demo.sort(key=lambda g: (not g["on_watchlist"], -g["reads"], -g["cameras"],
                             _desc(g["last_seen"]), g["plate"]))

    wl_items: list[dict[str, Any]] = []
    sev_rank = {"high": 0, "medium": 1, "low": 2}
    now = utcnow()
    for w in con.execute(
        "SELECT plate, plate_canonical, severity FROM watchlist WHERE active = 1"
        " AND (expires_at IS NULL OR expires_at > ?)", (now,)
    ):
        can = w["plate_canonical"] or plates.canonical(w["plate"])
        seen = con.execute(
            "SELECT COUNT(*) AS reads, COUNT(DISTINCT camera_id) AS cameras,"
            " MAX(seen_at) AS last_seen FROM sightings WHERE plate_canonical = ?",
            (can,)).fetchone()
        latest = con.execute(
            "SELECT provenance FROM sightings WHERE plate_canonical = ?"
            " ORDER BY seen_at DESC, sighting_id DESC LIMIT 1", (can,)).fetchone()
        wl_items.append({
            "plate": w["plate"], "reads": int(seen["reads"]),
            "cameras": int(seen["cameras"]), "last_seen": seen["last_seen"],
            "provenance": latest["provenance"] if latest else None,
            "on_watchlist": True, "_sev": sev_rank.get(w["severity"], 3),
        })
    wl_items.sort(key=lambda g: (g["reads"] == 0, g["_sev"], -g["reads"], g["plate"]))
    for g in wl_items:
        g.pop("_sev")

    live: dict[str, dict[str, Any]] = {}
    for plate, camera, reads, last_seen in con.execute(
        "SELECT plate, camera_id, COUNT(*), MAX(seen_at) FROM sightings"
        " WHERE provenance = 'live' GROUP BY plate, camera_id"
    ):
        key = plates.coerce(plate)
        if key is None:
            continue  # partial or rejected reads are not worth suggesting
        item = live.setdefault(key, {
            "plate": key, "reads": 0, "_cams": set(), "last_seen": None,
            "provenance": "live", "on_watchlist": plates.canonical(key) in watch})
        item["reads"] += reads
        item["_cams"].add(camera)
        item["last_seen"] = max(filter(None, (item["last_seen"], last_seen)), default=None)
    top_live = []
    for item in live.values():
        cams = item.pop("_cams")
        item["cameras"] = len(cams)
        item["camera_ids"] = sorted(cams)
        top_live.append(item)
    top_live.sort(key=lambda g: (-g["reads"], -g["cameras"], _desc(g["last_seen"]), g["plate"]))

    def clean(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{**{k: g[k] for k in ("plate", "reads", "cameras", "last_seen",
                                      "provenance", "on_watchlist")},
                 "camera_ids": g.get("camera_ids", [])} for g in items[:limit]]

    return {"demo": clean(demo), "watchlist": clean(wl_items), "top_live": clean(top_live)}


def _desc(ts: str | None) -> float:
    """Sort key putting the newest timestamp first (None last)."""
    if not ts:
        return float("inf")
    parsed = datetime.fromisoformat(ts)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return -parsed.timestamp()
