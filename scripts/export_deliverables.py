"""Regenerate the data deliverables from the live database (task S5.3).

Opens the configured database **read-only** (SQLite URI ``mode=ro``) and
renders every file through the backend's own report services, so the files
are exactly what the platform's report endpoints serve — without going
through HTTP and without any credential:

- ``deliverables/detection-report.{csv,html}`` — every sighting, newest first,
  with its clock and provenance (``backend.services.reports``);
- ``deliverables/route-GJ01AB1234.{csv,html}`` — the demonstration vehicle's
  route (``backend.services.route.reconstruct_route``), labelled ``demo``;
- ``deliverables/gap-analysis-report.html`` — ``backend.services.gap_analysis``;
- ``deliverables/registry-api.json`` — ``backend.tools.export_openapi``;
- ``deliverables/sample-camera-dataset.csv`` — a registry export of every
  camera, first line a disclosure of what is seeded.

``deliverables/departmental-systems-unaffected.md`` is a written document,
not generated here.

Usage::

    .venv/Scripts/python scripts/export_deliverables.py [--gap-note TEXT]

``--gap-note`` adds a context note under the gap-analysis title (e.g. an
upstream outage at generation time, stated from the platform's own logs).
Exits 1 if any output would carry a URL with userinfo (root rule 1).
"""

from __future__ import annotations

import argparse
import csv
import html
import io
import re
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.core import config, db as dbmod  # noqa: E402
from backend.services import gap_analysis, reports  # noqa: E402
from backend.services.route import reconstruct_route  # noqa: E402

OUT = REPO_ROOT / "deliverables"
ROUTE_PLATE = "GJ01AB1234"
_USERINFO = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^/\s\"'<>]*@")

DATASET_COLUMNS = [
    "camera_id", "feed_kind", "department", "location_name", "lat", "lon",
    "bearing_deg", "fov_deg", "range_m", "ownership", "transport", "fps_tier",
    "codec", "width", "height", "declared_fps", "rtsp_url_template",
    "hls_url", "source", "notes",
]


def connect_ro() -> sqlite3.Connection:
    """The configured database, opened read-only (no write can happen)."""
    path = config.db_path()
    if not path.exists():
        raise SystemExit(f"database not found: {path}")
    con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=30000")
    return con


def _write(name: str, text: str) -> Path:
    if _USERINFO.search(text):
        raise SystemExit(f"refusing to write {name}: it contains a URL with userinfo")
    path = OUT / name
    path.write_text(text, encoding="utf-8", newline="")
    return path


def _feed_kind(cam: dict) -> str:
    if cam["source"] == "catalogue":
        return "sandbox"
    tmpl = cam["rtsp_url_template"] or ""
    if "://127.0.0.1" in tmpl or "://localhost" in tmpl:
        return "local-stock"
    return "other"


def camera_dataset_csv(con: sqlite3.Connection) -> tuple[str, dict[str, int]]:
    """The registry export with its first-line disclosure."""
    cams = [dict(r) for r in con.execute("SELECT * FROM cameras ORDER BY camera_id")]
    kinds: dict[str, int] = {}
    for cam in cams:
        cam["feed_kind"] = _feed_kind(cam)
        kinds[cam["feed_kind"]] = kinds.get(cam["feed_kind"], 0) + 1
    disclosure = (
        f"# DISCLOSURE: Sentinel camera registry export, {len(cams)} cameras,"
        f" generated {dbmod.utcnow()} from data/sentinel.db."
        f" The {kinds.get('sandbox', 0)} sandbox cameras (feed_kind=sandbox) are"
        " the organisers' catalogue; their departments and coordinates are seeded"
        " demonstration assignments (data/camera_seed.csv), not official data."
        f" The {kinds.get('local-stock', 0)} local feeds (feed_kind=local-stock) are"
        " stock traffic footage published by a local mediamtx server at seeded"
        " coordinates with seeded departments (data/local_feeds.csv); they are"
        " not sandbox cameras and"
        " were not filmed by the team. No stream credential is stored or exported;"
        " sandbox stream URLs are built at run time from environment variables."
        " Health is omitted (see gap-analysis-report.html). Delete this line"
        " before re-importing through POST /api/cameras/import."
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([disclosure])
    writer.writerow(DATASET_COLUMNS)
    for cam in cams:
        writer.writerow([reports.csv_cell(cam.get(c)) for c in DATASET_COLUMNS])
    return buf.getvalue(), kinds


def gap_report_html(con: sqlite3.Connection, note: str | None) -> str:
    page = reports.gap_html(gap_analysis.generate(con))
    if note:
        block = (
            '<div class="note"><b>Generation note.</b> '
            f"{html.escape(note)}</div>"
        )
        # After the standing provenance note, before the first section.
        page = page.replace("<h2>1. ", block + "<h2>1. ", 1)
    return page


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--gap-note", default=None,
                    help="context note placed under the gap-analysis title")
    args = ap.parse_args()

    con = connect_ro()
    try:
        total = con.execute("SELECT COUNT(*) FROM sightings").fetchone()[0]
        if total > reports.MAX_ROWS:
            print(f"warning: {total} sightings; the report carries the newest {reports.MAX_ROWS}")
        rows = reports.detection_rows(con, limit=reports.MAX_ROWS)
        by_prov: dict[str, int] = {}
        for r in rows:
            by_prov[r["provenance"]] = by_prov.get(r["provenance"], 0) + 1
        _write("detection-report.csv", reports.detections_csv(rows))
        _write("detection-report.html", reports.detections_html(rows, {}))
        print(f"detection-report: {len(rows)} rows, by provenance {by_prov}")

        route = reconstruct_route(con, ROUTE_PLATE)
        _write(f"route-{ROUTE_PLATE}.csv", reports.route_csv(route))
        _write(f"route-{ROUTE_PLATE}.html", reports.route_html(route))
        provs = sorted({s["provenance"] for s in route["stops"]})
        print(f"route-{ROUTE_PLATE}: {len(route['stops'])} stops,"
              f" match {route['match_mode']}, provenance {provs}")

        _write("gap-analysis-report.html", gap_report_html(con, args.gap_note))
        g = gap_analysis.generate(con)
        print(f"gap-analysis: {g['cameras_total']} cameras, {g['online']} online,"
              f" {len(g['cameras_offline_or_degraded'])} offline/degraded,"
              f" {len(g['isolated_coverage'])} isolated")

        text, kinds = camera_dataset_csv(con)
        _write("sample-camera-dataset.csv", text)
        print(f"sample-camera-dataset: {sum(kinds.values())} cameras {kinds}")
    finally:
        con.close()

    from backend.tools import export_openapi

    export_openapi.main()
    spec_text = export_openapi.OUT_PATH.read_text(encoding="utf-8")
    if _USERINFO.search(spec_text):
        print("registry-api.json contains a URL with userinfo", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
