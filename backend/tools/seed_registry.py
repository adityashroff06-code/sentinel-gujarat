"""Seed the camera registry (decisions C8, F35).

Upserts **every** id from the committed ``data/cameras_raw.json`` first
(``transport='none'``, ``source='catalogue'``), so a fresh database gets
all 30 rows without the sandbox, then applies the disclosed
``data/camera_seed.csv`` (department, location, coordinates, tier).
Idempotent: running twice leaves the same rows.

    python -m backend.tools.seed_registry
    python -m backend.tools.seed_registry --add local01 Municipal rtsp://127.0.0.1:8554/stream/local01 --tier active
    python -m backend.tools.seed_registry --replay tests/fixtures/synthetic_60s.mp4 rep01 rep02
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3

from backend.core import config
from backend.core import db as dbmod

CATALOGUE = config.REPO_ROOT / "data" / "cameras_raw.json"
SEED_CSV = config.REPO_ROOT / "data" / "camera_seed.csv"


def upsert_catalogue(con: sqlite3.Connection) -> int:
    entries = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    now = dbmod.utcnow()
    for entry in entries:
        con.execute(
            "INSERT INTO cameras (camera_id, location_name, transport, source,"
            " created_at, updated_at) VALUES (?, ?, 'none', 'catalogue', ?, ?)"
            " ON CONFLICT(camera_id) DO NOTHING",
            (entry["id"], entry["name"], now, now),
        )
    return len(entries)


def apply_seed(con: sqlite3.Connection) -> int:
    applied = 0
    now = dbmod.utcnow()
    with open(SEED_CSV, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            con.execute(
                "UPDATE cameras SET department = ?, location_name = ?, lat = ?,"
                " lon = ?, fps_tier = ?, updated_at = ? WHERE camera_id = ?",
                (
                    row["department"], row["location_name"], float(row["lat"]),
                    float(row["lon"]), row["fps_tier"], now, row["camera_id"],
                ),
            )
            applied += 1
    return applied


def add_manual(con: sqlite3.Connection, camera_id: str, department: str,
               url: str, tier: str) -> None:
    now = dbmod.utcnow()
    con.execute(
        "INSERT INTO cameras (camera_id, department, rtsp_url_template, transport,"
        " fps_tier, source, created_at, updated_at)"
        " VALUES (?, ?, ?, 'rtsp', ?, 'manual', ?, ?)"
        " ON CONFLICT(camera_id) DO UPDATE SET department = excluded.department,"
        " rtsp_url_template = excluded.rtsp_url_template, transport = 'rtsp',"
        " fps_tier = excluded.fps_tier, updated_at = excluded.updated_at",
        (camera_id, department, url, tier, now, now),
    )


def add_replay(con: sqlite3.Connection, path: str, camera_ids: list[str]) -> None:
    now = dbmod.utcnow()
    for camera_id in camera_ids:
        # fps_tier='active': a replay row exists to be pulled (the soak's
        # supervisor selects transport IN ('rtsp','replay') AND active — S2.5).
        con.execute(
            "INSERT INTO cameras (camera_id, rtsp_url_template, transport, source,"
            " fps_tier, created_at, updated_at)"
            " VALUES (?, ?, 'replay', 'manual', 'active', ?, ?)"
            " ON CONFLICT(camera_id) DO UPDATE SET rtsp_url_template = excluded"
            ".rtsp_url_template, transport = 'replay', fps_tier = 'active',"
            " updated_at = excluded.updated_at",
            (camera_id, path, now, now),
        )


def summarise(con: sqlite3.Connection) -> tuple[int, int, int, bool]:
    total = con.execute("SELECT COUNT(*) FROM cameras").fetchone()[0]
    active = con.execute(
        "SELECT COUNT(*) FROM cameras WHERE fps_tier = 'active'"
    ).fetchone()[0]
    departments = con.execute(
        "SELECT COUNT(DISTINCT department) FROM cameras"
        " WHERE fps_tier = 'active' AND department IS NOT NULL"
    ).fetchone()[0]
    catalogue_ids = {e["id"] for e in json.loads(CATALOGUE.read_text(encoding="utf-8"))}
    present = {
        r[0] for r in con.execute("SELECT camera_id FROM cameras").fetchall()
    }
    ok = catalogue_ids <= present and active >= 5 and departments >= 5
    return total, active, departments, ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--add", nargs=3, metavar=("ID", "DEPARTMENT", "URL"))
    parser.add_argument("--tier", default="registered", choices=["active", "registered"])
    parser.add_argument("--replay", nargs="+", metavar="FILE_THEN_IDS")
    args = parser.parse_args()

    con = dbmod.connect()
    try:
        dbmod.migrate(con)
        upsert_catalogue(con)
        apply_seed(con)
        if args.add:
            add_manual(con, args.add[0], args.add[1], args.add[2], args.tier)
        if args.replay:
            if len(args.replay) < 2:
                parser.error("--replay needs a file and at least one camera id")
            add_replay(con, args.replay[0], args.replay[1:])
        con.commit()
        total, active, departments, ok = summarise(con)
    finally:
        con.close()
    print(
        f"cameras: {total} rows, {active} active across {departments} departments"
        f" — ACCEPTANCE: {'PASS' if ok else 'FAIL'}"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
