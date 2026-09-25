"""Re-store historical plates in their coerced form (ANPR search lane, 25 Sep).

Until 25 Sep the pipeline stored a structurally full read exactly as OCR
spelt it, so the live DB held ``6J23H1548`` beside ``GJ23H1548``,
``GJ1157924`` beside ``GJ11S7924`` and ``GJO3XH0407`` beside
``GJ03XH0407`` — one registration, two plates for search. The pipeline
now stores ``plates.coerce(read)`` (docs/api.md §6); this tool brings the
rows written before that change into the same form.

Rules:

- **dry run by default** — prints every ``before -> after`` plate with its
  row count and the distinct-plate totals; ``--apply`` writes, in one
  transaction, after a ``VACUUM INTO`` snapshot under ``data/backup/``
  (``--no-backup`` skips it when the caller has already taken one);
- only ``provenance IN ('live', 'harvest')`` rows whose coerced form
  differs; **demo and test rows are never touched** (the demo scenario is
  scripted — its ``GJ01A81234`` near-miss is deliberate — and test rows
  are the record of a replay);
- ``plate_raw`` is never touched; ``plate_canonical`` is unchanged by
  construction (coercion moves characters only inside their ambiguity
  class) — asserted for every group **before** anything is written, and
  the tool refuses to write at all if any group disagrees;
- a watchlist alert whose sighting is re-stored gets the same ``plate``
  (the alert's plate is a copy of its sighting's).

CLI (from the repo root, with the project venv)::

    python -m backend.tools.renormalise_plates            # dry run
    python -m backend.tools.renormalise_plates --apply    # write
    python -m backend.tools.renormalise_plates --db data/soak.db
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from backend.core import config, plates
from backend.core import db as dbmod

#: The only provenances this tool rewrites (root rule 12: never demo/test).
TOUCHED = ("live", "harvest")
_IN = "('live', 'harvest')"


@dataclass(frozen=True)
class Change:
    """One stored plate to re-store as its coerced form."""

    old: str
    new: str
    canonical: str
    rows: int


class CanonicalMismatch(RuntimeError):
    """A group's stored ``plate_canonical`` disagrees with its coerced
    plate — the tool refuses to write anything."""


def plan(con: sqlite3.Connection) -> list[Change]:
    """Every live/harvest plate whose coerced form differs, oldest spelling
    first. Raises :class:`CanonicalMismatch` if any group's stored
    ``plate_canonical`` would not stay the canonical of the new plate."""
    changes: list[Change] = []
    bad: list[str] = []
    for row in con.execute(
        "SELECT plate, plate_canonical, COUNT(*) AS n FROM sightings"
        f" WHERE provenance IN {_IN} GROUP BY plate, plate_canonical ORDER BY plate"
    ):
        new = plates.coerce(row["plate"])
        if new is None or new == row["plate"]:
            continue
        if plates.canonical(new) != row["plate_canonical"]:
            bad.append(f"{row['plate']} -> {new}: stored canonical "
                       f"{row['plate_canonical']!r} != {plates.canonical(new)!r}")
            continue
        changes.append(Change(row["plate"], new, row["plate_canonical"], int(row["n"])))
    if bad:
        raise CanonicalMismatch("; ".join(bad))
    return changes


def _distinct_plates(con: sqlite3.Connection) -> int:
    return int(con.execute(
        f"SELECT COUNT(DISTINCT plate) FROM sightings WHERE provenance IN {_IN}"
    ).fetchone()[0])


def _alerts_affected(con: sqlite3.Connection, change: Change) -> int:
    return int(con.execute(
        "SELECT COUNT(*) FROM alerts WHERE kind = 'watchlist' AND plate = ?"
        " AND sighting_id IN (SELECT sighting_id FROM sightings"
        f"  WHERE plate = ? AND provenance IN {_IN})",
        (change.old, change.old),
    ).fetchone()[0])


def apply(con: sqlite3.Connection, changes: list[Change]) -> dict[str, int]:
    """Write *changes* in one transaction; returns ``{"rows", "alerts"}``.

    Re-checks inside the transaction that every touched row keeps its
    ``plate_canonical`` (it is never written) and rolls back otherwise.
    """
    counts = {"rows": 0, "alerts": 0}
    try:
        con.execute("BEGIN IMMEDIATE")
        for ch in changes:
            ids = [r[0] for r in con.execute(
                "SELECT sighting_id FROM sightings WHERE plate = ? AND plate_canonical = ?"
                f" AND provenance IN {_IN}", (ch.old, ch.canonical))]
            if not ids:
                continue
            marks = ",".join("?" for _ in ids)
            counts["alerts"] += con.execute(
                f"UPDATE alerts SET plate = ? WHERE kind = 'watchlist' AND plate = ?"
                f" AND sighting_id IN ({marks})", (ch.new, ch.old, *ids)).rowcount
            counts["rows"] += con.execute(
                f"UPDATE sightings SET plate = ? WHERE sighting_id IN ({marks})",
                (ch.new, *ids)).rowcount
            drift = con.execute(
                f"SELECT COUNT(*) FROM sightings WHERE sighting_id IN ({marks})"
                " AND (plate != ? OR plate_canonical != ?)",
                (*ids, ch.new, ch.canonical)).fetchone()[0]
            if drift:
                raise CanonicalMismatch(f"{ch.old} -> {ch.new}: {drift} rows drifted")
        con.commit()
    except Exception:
        con.rollback()
        raise
    return counts


def backup(con: sqlite3.Connection, db_path: Path) -> Path:
    """``VACUUM INTO`` a consistent snapshot beside the DB; returns its path."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = db_path.parent / "backup" / f"{db_path.stem}-pre-renormalise-{stamp}.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    con.execute("VACUUM INTO ?", (str(target),))
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Re-store live/harvest plates in their coerced form (dry run by default).")
    parser.add_argument("--apply", action="store_true", help="write the changes")
    parser.add_argument("--db", help="database path (default: SENTINEL_DB)")
    parser.add_argument("--no-backup", action="store_true",
                        help="skip the VACUUM INTO snapshot before --apply")
    args = parser.parse_args(argv)
    db_path = Path(args.db) if args.db else config.db_path()
    if not db_path.is_file():
        print(f"no database at {db_path}", file=sys.stderr)
        return 2
    con = dbmod.connect(db_path)
    try:
        try:
            changes = plan(con)
        except CanonicalMismatch as exc:
            print(f"REFUSING: plate_canonical would not hold - {exc}", file=sys.stderr)
            return 1
        before = _distinct_plates(con)
        merged = {ch.new for ch in changes}
        existing = {r[0] for r in con.execute(
            f"SELECT DISTINCT plate FROM sightings WHERE provenance IN {_IN}")}
        after = len((existing - {ch.old for ch in changes}) | merged)
        untouched = dict(con.execute(
            "SELECT provenance, COUNT(*) FROM sightings"
            f" WHERE provenance NOT IN {_IN} GROUP BY provenance").fetchall())
        alerts = sum(_alerts_affected(con, ch) for ch in changes)

        mode = "APPLY" if args.apply else "DRY RUN - nothing written; pass --apply to write"
        print(f"renormalise_plates ({mode})  db={db_path.name}")
        for ch in changes:
            print(f"  {ch.old:<12} -> {ch.new:<12} {ch.rows:>4} row(s)")
        print(f"distinct live/harvest plates: {before} before -> {after} after"
              f" ({before - after} merged into an existing twin)")
        print(f"rows to re-store: {sum(ch.rows for ch in changes)}"
              f" | watchlist alerts to re-store: {alerts}"
              f" | plate_canonical unchanged: asserted for {len(changes)} plate(s)")
        print("untouched (never rewritten): "
              + (", ".join(f"{k}={v}" for k, v in sorted(untouched.items())) or "none"))
        if not args.apply or not changes:
            return 0
        if not args.no_backup:
            print(f"backup: {backup(con, db_path)}")
        counts = apply(con, changes)
        print(f"applied: {counts['rows']} row(s), {counts['alerts']} alert(s);"
              f" distinct live/harvest plates now {_distinct_plates(con)}")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
