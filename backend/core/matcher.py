"""Watchlist matching — local, cached, index-first (root CLAUDE.md §4).

``WatchlistCache`` holds the active watchlist in memory with two indexes:
exact probes go through the canonical index; fuzzy candidates are limited
to rows sharing the first four canonical characters (docs/api.md B9). The
caller refreshes the cache every ~10 s; matching never round-trips to the
database per detection.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from backend.core import db as dbmod
from backend.core import plates

_PREFIX_LEN = 4


class WatchlistCache:
    """In-memory active watchlist with canonical and prefix indexes."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self._by_canonical: dict[str, list[dict[str, Any]]] = {}
        self._by_prefix: dict[str, list[dict[str, Any]]] = {}

    def refresh(self, con: sqlite3.Connection) -> int:
        """Reload active, unexpired rows (decision F39); returns the count."""
        now = dbmod.utcnow()
        rows = [
            dict(r)
            for r in con.execute(
                "SELECT * FROM watchlist WHERE active = 1"
                " AND (expires_at IS NULL OR expires_at > ?)",
                (now,),
            )
        ]
        by_canonical: dict[str, list[dict[str, Any]]] = {}
        by_prefix: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            can = row["plate_canonical"] or plates.canonical(row["plate"])
            row["plate_canonical"] = can
            by_canonical.setdefault(can, []).append(row)
            by_prefix.setdefault(can[:_PREFIX_LEN], []).append(row)
        self.rows, self._by_canonical, self._by_prefix = rows, by_canonical, by_prefix
        return len(rows)

    def find_match(self, plate: str) -> tuple[dict[str, Any], str, float] | None:
        """``(watchlist_row, rule, distance)`` for the best match, or None.

        Exact-first: probe the canonical index (yields ``exact`` or
        ``ambiguity``); then fuzzy only over rows sharing the first four
        canonical characters, only for structurally full reads (partial
        reads never fuzzy-match — docs/api.md §6).
        """
        norm = plates.normalise(plate)
        can = plates.canonical(norm)
        for row in self._by_canonical.get(can, ()):
            matched, distance, rule = plates.plate_match(norm, row["plate"])
            if matched and rule in ("exact", "ambiguity"):
                return row, rule, distance
        if plates.plate_like(norm) != "full":
            return None
        best: tuple[dict[str, Any], str, float] | None = None
        for row in self._by_prefix.get(can[:_PREFIX_LEN], ()):
            matched, distance, rule = plates.plate_match(norm, row["plate"])
            if matched and rule == "fuzzy" and (best is None or distance < best[2]):
                best = (row, rule, distance)
        return best


def alertable(rule: str) -> bool:
    """Alert policy passthrough (decision F21)."""
    return plates.alertable(rule)
