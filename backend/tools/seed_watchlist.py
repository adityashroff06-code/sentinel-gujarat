"""Seed the watchlist (decision C11): idempotent, 25 invented entries
across every category and severity, with the demo hero plate present as
``stolen_vehicle / high``. Representative data created by us, which the
rules permit; every entry is invented (`authority`/`source_ref` are
notional). ``--from-sightings N`` additionally lists observed full plates.

    python -m backend.tools.seed_watchlist
    python -m backend.tools.seed_watchlist --from-sightings 5
"""

from __future__ import annotations

import argparse
import sqlite3

from backend.core import db as dbmod
from backend.core import plates

# (plate, category, severity, description, reason, authority, source_ref)
ENTRIES: list[tuple[str, str, str, str, str, str, str]] = [
    ("GJ01AB1234", "stolen_vehicle", "high", "White demo hatchback (the walkthrough vehicle)",
     "Reported stolen", "Junagadh City PS", "FIR-118-2026"),
    ("GJ01CD5678", "stolen_vehicle", "high", "Silver sedan", "Reported stolen", "Ahmedabad Zone 1", "FIR-204-2026"),
    ("GJ03EF9012", "stolen_vehicle", "medium", "Blue motorcycle", "Reported stolen", "Rajkot City PS", "FIR-097-2026"),
    ("GJ05GH3456", "stolen_vehicle", "medium", "Grey pickup", "Reported stolen", "Navsari PS", "FIR-152-2026"),
    ("GJ18JK7890", "stolen_vehicle", "low", "Auto-rickshaw", "Reported stolen", "Junagadh Rural PS", "FIR-063-2026"),
    ("GJ01LM2345", "wanted_person", "high", "Registered owner wanted for questioning",
     "Warrant outstanding", "Gujarat CID", "W-2026-0412"),
    ("GJ06NP6789", "wanted_person", "high", "Vehicle linked to absconding suspect",
     "Warrant outstanding", "Surat City PS", "W-2026-0388"),
    ("GJ11QR1234", "wanted_person", "medium", "Owner sought in fraud case",
     "Summons unserved", "EOW Ahmedabad", "EOW-2026-77"),
    ("GJ23ST5678", "wanted_person", "medium", "Vehicle seen near incident scene",
     "Investigation", "Bhavnagar PS", "CR-221-2026"),
    ("GJ27UV9012", "wanted_person", "low", "Witness vehicle", "Statement pending", "Vadodara PS", "CR-305-2026"),
    ("GJ02WX3456", "missing_person", "high", "Vehicle of missing adult", "Missing since 14 Sep",
     "Junagadh City PS", "MP-2026-51"),
    ("GJ08YZ7890", "missing_person", "high", "Family vehicle, missing minor case",
     "AMBER-equivalent", "Rajkot City PS", "MP-2026-58"),
    ("GJ12AB8901", "missing_person", "medium", "Missing senior citizen's car",
     "Missing since 18 Sep", "Navsari PS", "MP-2026-64"),
    ("GJ16CD2345", "missing_person", "low", "Vehicle associated with runaway case",
     "Follow-up", "Patan PS", "MP-2026-70"),
    ("GJ21EF6789", "missing_person", "low", "Relative's vehicle", "Follow-up", "Mehsana PS", "MP-2026-73"),
    ("GJ04GH1234", "blacklisted", "high", "Repeat toll evasion + forged permit",
     "Permit forged", "RTO Ahmedabad", "RTO-BL-1188"),
    ("GJ09JK5678", "blacklisted", "medium", "Commercial vehicle, expired fitness",
     "Fitness lapsed", "RTO Rajkot", "RTO-BL-1204"),
    ("GJ14LM9012", "blacklisted", "medium", "Overloaded goods carrier",
     "Repeat offence", "RTO Surat", "RTO-BL-1216"),
    ("GJ19NP3456", "blacklisted", "low", "Unpaid challans", "Recovery pending", "Traffic HQ", "CHL-2026-9917"),
    ("GJ24QR7890", "blacklisted", "low", "Modified silencer, repeat notice", "Notice served", "Traffic HQ", "CHL-2026-9954"),
    ("GJ05JB4321", "suspect", "high", "Seen leaving scene in Junagadh case",
     "Under investigation", "Junagadh City PS", "CR-233-2026"),
    ("GJ07ST1234", "suspect", "medium", "Pattern movement near warehouses",
     "Surveillance request", "Rajkot Crime Branch", "CB-2026-140"),
    ("GJ13UV5678", "suspect", "medium", "Linked to bootlegging route",
     "Surveillance request", "SMC Prohibition", "PR-2026-88"),
    ("GJ26WX9012", "suspect", "low", "Anonymous tip", "Verification", "Control Room", "TIP-2026-501"),
    ("GJ29YZ3456", "suspect", "low", "Repeated night circling, market area",
     "Verification", "Bilimora Out-post", "TIP-2026-517"),
]


def seed(con: sqlite3.Connection) -> int:
    now = dbmod.utcnow()
    for plate, category, severity, description, reason, authority, source_ref in ENTRIES:
        con.execute(
            "INSERT INTO watchlist (plate, plate_canonical, category, severity,"
            " description, reason, authority, source_ref, active, added_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)"
            " ON CONFLICT(plate) DO UPDATE SET plate_canonical = excluded.plate_canonical,"
            " category = excluded.category, severity = excluded.severity,"
            " description = excluded.description, reason = excluded.reason,"
            " authority = excluded.authority, source_ref = excluded.source_ref,"
            " active = 1",
            (plate, plates.canonical(plate), category, severity, description,
             reason, authority, source_ref, now),
        )
    return len(ENTRIES)


def add_from_sightings(con: sqlite3.Connection, n: int) -> int:
    """Add up to *n* observed full plates as low-severity suspects, recorded
    as seeded-from-observation (C11 / docs/api.md §3)."""
    now = dbmod.utcnow()
    added = 0
    rows = con.execute(
        "SELECT DISTINCT plate FROM sightings WHERE provenance = 'live'"
        " ORDER BY seen_at DESC"
    ).fetchall()
    for (plate,) in rows:
        if added >= n:
            break
        if plates.plate_like(plate) != "full":
            continue
        cursor = con.execute(
            "INSERT INTO watchlist (plate, plate_canonical, category, severity,"
            " description, reason, authority, source_ref, active, added_at)"
            " VALUES (?, ?, 'suspect', 'low', 'Observed in live feed', 'Seeded from"
            " observation', 'Demo', 'OBSERVED', 1, ?) ON CONFLICT(plate) DO NOTHING",
            (plate, plates.canonical(plate), now),
        )
        added += cursor.rowcount
    return added


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-sightings", type=int, default=0, metavar="N")
    args = parser.parse_args()

    con = dbmod.connect()
    try:
        dbmod.migrate(con)
        seeded = seed(con)
        observed = add_from_sightings(con, args.from_sightings) if args.from_sightings else 0
        con.commit()
        total = con.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
    finally:
        con.close()
    print(f"watchlist: {seeded} seeded (+{observed} from sightings), {total} rows total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
