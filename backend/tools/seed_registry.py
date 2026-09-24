"""Seed the camera registry (decisions C8, F35, F45).

Upserts **every** id from the committed ``data/cameras_raw.json`` first —
either published catalogue shape (task S3.7): the sandbox's ``cameras.json``
or the Integrator's Guide's ``GET /api/ingest``. Whatever the catalogue
supplies is written verbatim (``source='catalogue'`` either way); the
disclosed ``data/camera_seed.csv`` then fills only what the catalogue did
not carry (department, location, coordinates), plus the seed-owned
``fps_tier``. ``SENTINEL_CATALOGUE_URL`` naming a local JSON file replaces
the committed catalogue; fetching a URL is the probe's business — the
seeder never touches the network. Idempotent: running twice leaves the
same rows.

    python -m backend.tools.seed_registry
    python -m backend.tools.seed_registry --add local01 Municipal rtsp://127.0.0.1:8554/stream/local01 --tier active
    python -m backend.tools.seed_registry --replay tests/fixtures/synthetic_60s.mp4 rep01 rep02
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path
from typing import Any

from backend.core import config
from backend.core import db as dbmod
from backend.tools import probe  # the shared catalogue normaliser (F45)

CATALOGUE = config.REPO_ROOT / "data" / "cameras_raw.json"
SEED_CSV = config.REPO_ROOT / "data" / "camera_seed.csv"

# The registry columns a catalogue may supply (docs/api.md §1). transport,
# tier and the seed-owned fields stay out: probing and the seed own those.
CATALOGUE_COLUMNS = (
    "department", "location_name", "lat", "lon", "codec", "width", "height",
    "declared_fps", "bitrate_kbps", "hls_url", "rtsp_url_template",
    "whep_url_template", "health",
)


def _catalogue_path() -> Path:
    """``data/cameras_raw.json``, unless ``SENTINEL_CATALOGUE_URL`` names a
    local JSON file (an http(s) URL is ignored here — the probe fetches and
    commits it; the seeder is offline by design, F35)."""
    src = config.catalogue_url()
    if src and not src.lower().startswith(("http://", "https://")):
        path = Path(src)
        return path if path.is_absolute() else config.REPO_ROOT / path
    return CATALOGUE


def _catalogue_entries() -> list[dict[str, Any]]:
    return probe.load_catalogue_file(_catalogue_path())


def upsert_catalogue(con: sqlite3.Connection,
                     entries: list[dict[str, Any]] | None = None) -> int:
    """Upsert every catalogue id (both shapes, F45). Catalogue-supplied
    fields overwrite; fields it does not carry are left for
    :func:`apply_seed`. Returns the number of entries applied."""
    if entries is None:
        entries = _catalogue_entries()
    now = dbmod.utcnow()
    for rec in entries:
        cols = [c for c in CATALOGUE_COLUMNS if c in rec]
        fields = ["camera_id", *cols, "transport", "source", "created_at", "updated_at"]
        values = [rec["camera_id"], *(rec[c] for c in cols),
                  "none", "catalogue", now, now]
        updates = ", ".join(f"{c} = excluded.{c}" for c in [*cols, "updated_at"])
        con.execute(
            f"INSERT INTO cameras ({', '.join(fields)})"
            f" VALUES ({', '.join('?' * len(fields))})"
            f" ON CONFLICT(camera_id) DO UPDATE SET {updates}",
            values,
        )
    return len(entries)


def apply_seed(con: sqlite3.Connection) -> int:
    """Fill from the disclosed seed only what the catalogue did not carry
    (F45): department, location, coordinates fall back; ``fps_tier`` is
    seed-owned (no catalogue shape carries a tier). Updates only rows the
    catalogue created — a camera absent from the catalogue is never
    invented. Returns the number of registry rows the seed matched."""
    applied = 0
    now = dbmod.utcnow()
    with open(SEED_CSV, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            cur = con.execute(
                "UPDATE cameras SET department = COALESCE(department, ?),"
                " location_name = COALESCE(location_name, ?),"
                " lat = COALESCE(lat, ?), lon = COALESCE(lon, ?),"
                " fps_tier = ?, updated_at = ? WHERE camera_id = ?",
                (
                    row["department"], row["location_name"], float(row["lat"]),
                    float(row["lon"]), row["fps_tier"], now, row["camera_id"],
                ),
            )
            applied += cur.rowcount
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
    catalogue_ids = {e["camera_id"] for e in _catalogue_entries()}
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
