"""Report endpoints — the named deliverables, generated live (docs/api.md §7).

Ported from ``D:\\projects\\Sentinel_Repo\\src\\api\\routes_reports.py`` (F52)
and adapted to this repo's contract:

- reports render **in memory** through :mod:`backend.services.reports` and
  stream straight back — never written into ``deliverables/`` per request
  (the old build served ``FileResponse`` from shared files, which races
  concurrent requests and leaves stale copies on disk);
- reports are an **evaluator** action (docs/api.md §7 roles, decision F41);
- rate-limited per identity (docs/api.md §9 names the report exports);
- ``from``/``to`` are canonicalised at the boundary (B6);
- every report carries provenance (B14) and the escaping rules of B11.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Iterator, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse

from backend.app import schemas
from backend.app.auth import RateLimiter, require_evaluator
from backend.core import db as dbmod
from backend.services import gap_analysis, reports
from backend.services.route import reconstruct_route

router = APIRouter(prefix="/api/reports", tags=["reports"])

#: docs/api.md §9: rate limits on the expensive reads. Generous — a person
#: exporting reports, not a scraper (429 rather than queueing).
_limit_reports = RateLimiter("reports", limit=60, window_s=60.0)

_HTML_RESPONSE = {
    200: {
        "description": "The rendered report",
        "content": {"text/html": {"schema": {"type": "string"}}},
    }
}
_REPORT_RESPONSE = {
    200: {
        "description": "The rendered report (HTML page or CSV export)",
        "content": {
            "text/html": {"schema": {"type": "string"}},
            "text/csv": {"schema": {"type": "string"}},
        },
    }
}


def get_db() -> Iterator[sqlite3.Connection]:
    con = dbmod.connect()
    try:
        yield con
    finally:
        con.close()


def _canonical_ts(value: str, param: str) -> str:
    """Canonicalise a query timestamp to the stored ``+00:00`` form (B6)."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{param} is not an ISO 8601 timestamp")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return dbmod.iso(parsed)


def _deliver(text: str, format: str, filename: str):
    if format == "csv":
        return PlainTextResponse(
            text,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
        )
    return HTMLResponse(text)


@router.get("/detections", responses=_REPORT_RESPONSE)
def detections_report(
    con: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_evaluator),
    __: None = Depends(_limit_reports),
    format: Literal["csv", "html"] = "html",
    camera_id: str | None = Query(default=None, pattern=schemas.CAMERA_ID_PATTERN),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    plate: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=reports.DEFAULT_ROWS, ge=1, le=reports.MAX_ROWS),
):
    """The timestamped detection report — a named deliverable. Fresh from
    the sightings table on every request; every row carries provenance;
    HTML-escaped, CSV formula-prefix escaped (docs/api.md §7, B11, B14)."""
    filters = {
        "camera": camera_id,
        "from": _canonical_ts(from_, "from") if from_ else None,
        "to": _canonical_ts(to, "to") if to else None,
        "plate": plate,
    }
    rows = reports.detection_rows(
        con,
        camera_id=camera_id,
        from_iso=filters["from"],
        to_iso=filters["to"],
        plate=plate,
        limit=limit,
    )
    if format == "csv":
        return _deliver(reports.detections_csv(rows), "csv", "detection-report")
    return _deliver(reports.detections_html(rows, filters), "html", "detection-report")


@router.get("/route/{plate}", responses=_REPORT_RESPONSE)
def route_report(
    plate: str,
    con: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_evaluator),
    __: None = Depends(_limit_reports),
    format: Literal["csv", "html"] = "html",
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
):
    """Route report export for one plate — the scored reconstruction as a
    printable page or CSV, stops carrying provenance and clock source."""
    route = reconstruct_route(con, plate, min_confidence)
    if format == "csv":
        return _deliver(reports.route_csv(route), "csv", f"route-{route['normalised'] or 'plate'}")
    return _deliver(reports.route_html(route), "html", "route-report")


@router.get("/gap-analysis", responses=_HTML_RESPONSE)
def gap_analysis_report(
    con: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_evaluator),
    __: None = Depends(_limit_reports),
):
    """The printable gap-analysis report (Model 1 deliverable), regenerated
    from the registry on every request so it is never stale."""
    return HTMLResponse(reports.gap_html(gap_analysis.generate(con)))
