"""Report generation — the named deliverables, rendered live (docs/api.md §7).

Ported from ``D:\\projects\\Sentinel_Repo\\src\\tools\\report.py`` (F52) and
adapted to this repo's contract:

- reports are generated **in memory** on every request and streamed, never
  written into ``deliverables/`` at request time (the old build wrote files
  there, which races concurrent requests and leaves stale copies);
- every report carries a **provenance** column (docs/api.md B14) so a demo
  row can never pass as a live one (root rule 12);
- HTML output escapes every input (docs/api.md B11 — the old build already
  escaped; kept, with the filter echo escaped too);
- CSV cells beginning ``= + - @`` are prefixed with ``'`` so a spreadsheet
  never executes a formula smuggled through a plate or location (B11 — new
  in the fresh build; the old CSV wrote raw cells, defect class D7/D8).

Pure functions over an open connection; one short read per report.
"""

from __future__ import annotations

import csv
import html
import io
import sqlite3
from typing import Any

from backend.core import db as dbmod

#: Report table rows are capped; the CSV/HTML export is a summary document,
#: not a bulk data dump (rule 6: never bulk-download; B11 body limits).
MAX_ROWS = 2000
DEFAULT_ROWS = 500

_FORMULA_PREFIXES = ("=", "+", "-", "@")

# Ported verbatim from src/tools/report.py — the printable house style.
_STYLE = """
<style>
  body{font-family:'DM Sans',system-ui,Segoe UI,Roboto,sans-serif;
       color:#12212f;margin:32px;line-height:1.5}
  h1{font-size:22px;margin:0 0 4px} h2{font-size:15px;margin:24px 0 8px;
     color:#20344a;border-bottom:1px solid #d8e0ea;padding-bottom:4px}
  .sub{color:#5a6b7d;font-size:12px;margin-bottom:16px}
  table{border-collapse:collapse;width:100%;font-size:12px;margin:8px 0}
  th,td{border:1px solid #d8e0ea;padding:6px 8px;text-align:left}
  th{background:#f0f4f8;font-weight:600}
  .pill{display:inline-block;padding:1px 8px;border-radius:10px;font-size:11px}
  .off{background:#fde2e2;color:#a01919} .deg{background:#fdf0d5;color:#8a6100}
  .ok{background:#dff0e0;color:#1d6b2b}
  .demo{background:#e8e2fd;color:#4a2fa0} .live{background:#dff0e0;color:#1d6b2b}
  .note{background:#f0f4f8;border-left:3px solid #3d6b9e;padding:8px 12px;
        font-size:12px;color:#3a4d5f;margin:12px 0}
  @media print{body{margin:0}}
</style>
"""

_PROVENANCE_NOTE = (
    "Every row carries its provenance: rows marked 'demo' or 'test' are "
    "demonstration data injected through the real pipeline, never live reads "
    "(docs/api.md B14)."
)


def _esc(v: object) -> str:
    """HTML-escape any value for report output (None renders as an em dash)."""
    return html.escape(str(v if v is not None else "\u2014"))


def csv_cell(v: object) -> str:
    """One CSV cell, formula-prefix escaped (docs/api.md B11).

    A cell beginning ``= + - @`` is prefixed with ``'`` so opening the CSV
    in a spreadsheet cannot execute it. None becomes the empty string.
    """
    s = "" if v is None else str(v)
    if s.startswith(_FORMULA_PREFIXES):
        return "'" + s
    return s


def _csv(header: list[str], rows: list[list[object]]) -> str:
    """Render a CSV document (CRLF, quoted as needed, cells escaped)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    for row in rows:
        writer.writerow([csv_cell(v) for v in row])
    return buf.getvalue()


def _page(title: str, subtitle: str, body: str) -> str:
    """One self-contained printable page (open, Ctrl-P to PDF)."""
    return (
        f'<!doctype html><html><head><meta charset="utf-8">'
        f"<title>{_esc(title)}</title>{_STYLE}</head><body>"
        f"<h1>{_esc(title)}</h1>"
        f'<div class="sub">{subtitle}</div>'
        f'<div class="note">{_esc(_PROVENANCE_NOTE)}</div>'
        f"{body}</body></html>"
    )


def _prov_pill(p: object) -> str:
    cls = "live" if p == "live" else "demo"
    return f"<span class='pill {cls}'>{_esc(p)}</span>"


# ------------------------------------------------------------- detections

DETECTION_COLUMNS = [
    "seen_at_utc", "plate", "plate_raw", "confidence", "vehicle_class",
    "camera_id", "department", "location", "clock_source", "provenance",
]


def detection_rows(
    con: sqlite3.Connection,
    *,
    camera_id: str | None = None,
    from_iso: str | None = None,
    to_iso: str | None = None,
    plate: str | None = None,
    limit: int = DEFAULT_ROWS,
) -> list[dict[str, Any]]:
    """The filtered detection rows, newest first (timestamps already
    canonicalised by the caller — docs/api.md B6)."""
    sql = (
        "SELECT s.seen_at, s.plate, s.plate_raw, s.confidence, s.vehicle_class,"
        " s.camera_id, c.department, c.location_name, s.clock_source, s.provenance"
        " FROM sightings s JOIN cameras c ON c.camera_id = s.camera_id WHERE 1=1"
    )
    args: list[object] = []
    if camera_id:
        sql += " AND s.camera_id = ?"
        args.append(camera_id)
    if from_iso:
        sql += " AND s.seen_at >= ?"
        args.append(from_iso)
    if to_iso:
        sql += " AND s.seen_at <= ?"
        args.append(to_iso)
    if plate:
        sql += " AND s.plate LIKE ?"
        args.append(f"%{plate.upper()}%")
    sql += " ORDER BY s.seen_at DESC, s.sighting_id DESC LIMIT ?"
    args.append(min(int(limit), MAX_ROWS))
    return [dict(r) for r in con.execute(sql, args)]


def detections_csv(rows: list[dict[str, Any]]) -> str:
    return _csv(
        DETECTION_COLUMNS,
        [
            [
                r["seen_at"], r["plate"], r["plate_raw"],
                None if r["confidence"] is None else f"{r['confidence']:.2f}",
                r["vehicle_class"], r["camera_id"], r["department"],
                r["location_name"], r["clock_source"], r["provenance"],
            ]
            for r in rows
        ],
    )


def detections_html(rows: list[dict[str, Any]], filters: dict[str, Any]) -> str:
    """The printable detection report; every input HTML-escaped (B11)."""
    applied = " · ".join(f"{k} {_esc(v)}" for k, v in filters.items() if v)
    trows = "".join(
        f"<tr><td>{_esc(r['seen_at'])}</td><td><b>{_esc(r['plate'])}</b></td>"
        f"<td>{_esc(r['plate_raw'])}</td>"
        f"<td>{_esc(None if r['confidence'] is None else round(r['confidence'], 2))}</td>"
        f"<td>{_esc(r['vehicle_class'])}</td><td>{_esc(r['camera_id'])}</td>"
        f"<td>{_esc(r['department'])}</td><td>{_esc(r['location_name'])}</td>"
        f"<td>{_esc(r['clock_source'])}</td><td>{_prov_pill(r['provenance'])}</td></tr>"
        for r in rows
    ) or "<tr><td colspan=10>No detections</td></tr>"
    body = (
        "<table><tr><th>Timestamp (UTC)</th><th>Plate</th><th>Raw read</th>"
        "<th>Conf.</th><th>Class</th><th>Camera</th><th>Department</th>"
        f"<th>Location</th><th>Clock</th><th>Provenance</th></tr>{trows}</table>"
    )
    subtitle = (
        f"Generated {_esc(dbmod.utcnow())} · {len(rows)} detections"
        + (f" · filters: {applied}" if applied else "")
    )
    return _page("Sentinel \u2014 Vehicle Detection Report", subtitle, body)


# ------------------------------------------------------------------ route

ROUTE_COLUMNS = [
    "sequence", "seen_at_utc", "camera_id", "department", "location", "lat",
    "lon", "plate_raw", "confidence", "match_type", "match_distance",
    "suspect", "elapsed_from_previous_s", "implied_speed_kmh",
    "clock_source", "provenance",
]


def route_csv(route: dict[str, Any]) -> str:
    return _csv(
        ROUTE_COLUMNS,
        [
            [
                s["sequence"], s["seen_at"], s["camera_id"], s["department"],
                s["location_name"], s["lat"], s["lon"], s["plate_raw"],
                f"{s['confidence']:.2f}", s["match_type"], s["match_distance"],
                s["suspect"], s["elapsed_from_previous_s"],
                s["implied_speed_kmh"], s["clock_source"], s["provenance"],
            ]
            for s in route["stops"]
        ],
    )


def route_html(route: dict[str, Any]) -> str:
    """The printable route report for one plate (the scored artefact)."""
    stops = route["stops"]
    trows = "".join(
        f"<tr><td>{s['sequence']}</td><td>{_esc(s['seen_at'])}</td>"
        f"<td>{_esc(s['camera_id'])}</td><td>{_esc(s['department'])}</td>"
        f"<td>{_esc(s['location_name'])}</td><td>{_esc(s['plate_raw'])}</td>"
        f"<td>{_esc(round(s['confidence'], 2))}</td><td>{_esc(s['match_type'])}</td>"
        f"<td>{_esc(s['elapsed_from_previous_s'])}</td>"
        f"<td>{_esc(s['implied_speed_kmh'])}</td>"
        f"<td>{'suspect' if s['suspect'] else ''}</td>"
        f"<td>{_esc(s['clock_source'])}</td><td>{_prov_pill(s['provenance'])}</td></tr>"
        for s in stops
    ) or "<tr><td colspan=13>No sightings for this plate</td></tr>"
    gaps = "".join(
        f"<li>after stop {g['after_sequence']}: {g['minutes']} min \u2014 {_esc(g['note'])}</li>"
        for g in route["gaps"]
    )
    warnings = "".join(f"<li>{_esc(w)}</li>" for w in route["warnings"])
    header = (
        f"<h2>Summary</h2><table>"
        f"<tr><th>Plate (query)</th><td>{_esc(route['query_plate'])}</td></tr>"
        f"<tr><th>Normalised</th><td>{_esc(route['normalised'])}</td></tr>"
        f"<tr><th>Match mode</th><td>{_esc(route['match_mode'])}</td></tr>"
        f"<tr><th>Sightings</th><td>{route['total_sightings']}</td></tr>"
        f"<tr><th>First seen</th><td>{_esc(route['first_seen'])}</td></tr>"
        f"<tr><th>Last seen</th><td>{_esc(route['last_seen'])}</td></tr>"
        f"<tr><th>Duration (s)</th><td>{_esc(route['duration_seconds'])}</td></tr>"
        f"<tr><th>Distance (km)</th><td>{_esc(route['distance_km'])}</td></tr>"
        f"<tr><th>Departments crossed</th>"
        f"<td>{_esc(', '.join(route['departments_crossed']) or None)}</td></tr>"
        f"</table>"
    )
    body = header + (
        "<h2>Stops</h2>"
        "<table><tr><th>#</th><th>Seen at (UTC)</th><th>Camera</th>"
        "<th>Department</th><th>Location</th><th>Raw read</th><th>Conf.</th>"
        "<th>Match</th><th>Elapsed (s)</th><th>Speed (km/h)</th><th></th>"
        f"<th>Clock</th><th>Provenance</th></tr>{trows}</table>"
    )
    if gaps:
        body += f"<h2>Coverage gaps</h2><ul>{gaps}</ul>"
    if warnings:
        body += f"<h2>Warnings</h2><ul>{warnings}</ul>"
    subtitle = f"Generated {_esc(dbmod.utcnow())} · plate {_esc(route['query_plate'])}"
    return _page("Sentinel \u2014 Route Report", subtitle, body)


# ---------------------------------------------------------- gap analysis

def gap_html(g: dict[str, Any]) -> str:
    """The printable gap-analysis report (Model 1 deliverable), rendered
    from :func:`backend.services.gap_analysis.generate`."""
    off_rows = "".join(
        f"<tr><td>{_esc(c['camera_id'])}</td><td>{_esc(c['department'])}</td>"
        f"<td><span class='pill {'off' if c['health'] == 'offline' else 'deg'}'>"
        f"{_esc(c['health'] or 'unknown')}</span></td>"
        f"<td>{_esc(c['last_seen'])}</td></tr>"
        for c in g["cameras_offline_or_degraded"]
    ) or "<tr><td colspan=4>None</td></tr>"
    iso_rows = "".join(
        f"<tr><td>{_esc(c['camera_id'])}</td>"
        f"<td>{_esc(c['nearest_neighbour_km'])} km</td>"
        f"<td>{_esc(c['radius_km'])} km</td></tr>"
        for c in g["isolated_coverage"]
    ) or "<tr><td colspan=3>None</td></tr>"
    dept_rows = "".join(
        f"<tr><td>{_esc(d)}</td><td>{v['total']}</td><td>{v['online']}</td></tr>"
        for d, v in sorted(g["department_summary"].items())
    )
    body = (
        f"<h2>1. Offline &amp; degraded cameras"
        f" ({len(g['cameras_offline_or_degraded'])})</h2>"
        "<table><tr><th>Camera</th><th>Department</th><th>Health</th>"
        f"<th>Last seen</th></tr>{off_rows}</table>"
        f"<h2>2. Coverage gaps \u2014 isolated cameras"
        f" ({len(g['isolated_coverage'])})</h2>"
        '<p class="sub">Cameras whose nearest neighbour exceeds the isolation'
        " radius \u2014 corridors a single failure would leave unwatched.</p>"
        "<table><tr><th>Camera</th><th>Nearest neighbour</th>"
        f"<th>Radius</th></tr>{iso_rows}</table>"
        "<h2>3. Department-wise coverage</h2>"
        "<table><tr><th>Department</th><th>Total</th><th>Online</th></tr>"
        f"{dept_rows}</table>"
    )
    subtitle = (
        f"Generated {_esc(g['generated_at'])} · {g['cameras_total']} cameras"
        f" · {g['online']} online · {g['active_tier']} active-tier"
    )
    return _page("Sentinel \u2014 Camera Network Gap Analysis", subtitle, body)
