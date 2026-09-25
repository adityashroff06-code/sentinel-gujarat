"""Sightings, route, watchlist, alerts + SSE, events, workers (docs/api.md §7).

Ported from ``D:\\projects\\Sentinel_Repo\\src\\api\\routes_analytics.py``
(F52) and adapted to this repo's contract:

- pagination ``total`` reuses the row query's WHERE (B11 — old defect D8);
- ``from``/``to`` are canonicalised at the boundary to the stored ``+00:00``
  form, never compared as mixed-shape ISO strings (B6);
- **one** background tailer polls ``alerts`` past its cursor every 2 s and
  fans out to every SSE subscriber (C15, F27, B8); frames carry
  ``id: <alert_seq>`` and ``Last-Event-ID`` replays the gap from the table;
- auth on every path via the existing dependencies (backend/app/auth.py):
  the session cookie is accepted on ``GET /api/alerts/stream`` because
  ``EventSource`` cannot send headers; mutations require evaluator or
  admin (F41: acknowledge and watchlist add/remove are evaluator actions).
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Iterator, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from backend.app import schemas
from backend.app.audit import set_audit
from backend.app.auth import RateLimiter, require_auth, require_evaluator
from backend.core import config, plates
from backend.core import db as dbmod
from backend.core.logging_setup import setup
from backend.services import plate_search
from backend.services.route import crop_url, reconstruct_route

log = setup("api-analytics")

router = APIRouter(prefix="/api", tags=["analytics"])

_SSE_POLL_S = 2.0
_SSE_KEEPALIVE_S = 15.0

#: docs/api.md §9: the route query is rate-limited per identity (S3.1b).
#: Generous — an analyst working a case, not a scraper; 429 over queueing.
_limit_route = RateLimiter("route", limit=120, window_s=60.0)

_ALERT_SELECT = (
    "SELECT a.*, s.crop_path AS _crop_path, c.department, c.location_name"
    " FROM alerts a"
    " LEFT JOIN sightings s ON s.sighting_id = a.sighting_id"
    " LEFT JOIN cameras c ON c.camera_id = a.camera_id"
)


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


def _alert_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["crop_url"] = crop_url(d.pop("_crop_path", None))
    return d


# ------------------------------------------------------------------ sightings

@router.get("/sightings", response_model=schemas.SightingListOut)
def list_sightings(
    request: Request,
    con: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_auth),
    plate: str | None = Query(default=None, max_length=64),
    match: schemas.SightingMatch = "contains",
    camera_id: str | None = Query(default=None, pattern=schemas.CAMERA_ID_PATTERN),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    provenance: schemas.Provenance | None = None,
    vehicle_class: str | None = Query(default=None, pattern=r"^[a-z_]{1,32}$"),
    limit: int = Query(default=200, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
):
    """ANPR search over sightings with filters; paginated; ``total`` is
    computed with the same WHERE as the rows (B11).

    ``match``: ``contains`` (default — newest first, unchanged), ``exact``,
    or ``anpr`` — OCR-tolerant, ranked exact → ambiguity (canonical
    equality) → fuzzy (the canonical-prefix bucket, both sides full,
    weighted distance ≤ 1.0), then newest first; a partial ``anpr`` query
    matches as an OCR-tolerant fragment. Rows carry ``match_type`` and
    ``match_distance``; ``query`` echoes how the grammar read the plate.
    A plate query is audited with the plate searched (B12)."""
    body = plate_search.search_sightings(
        con, plate=plate, match=match, camera_id=camera_id,
        from_iso=_canonical_ts(from_, "from") if from_ else None,
        to_iso=_canonical_ts(to, "to") if to else None,
        min_confidence=min_confidence, provenance=provenance,
        vehicle_class=vehicle_class, limit=limit, offset=offset,
    )
    if plate:
        # the middleware logs the path; the plate lives in the query string,
        # so the handler names it — the ANPR-misuse audit trail (B12)
        set_audit(request, entity="plate_search", entity_id=plates.normalise(plate),
                  after={"match": match, "camera_id": camera_id,
                         "provenance": provenance, "total": body["total"]})
    return body


@router.get("/plates/suggest", response_model=schemas.PlateSuggestOut)
def plate_suggest(
    con: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_auth),
    limit: int = Query(default=8, ge=1, le=50),
):
    """Plates worth typing into Search: ``demo`` (labelled demo plates,
    watchlisted first), ``watchlist`` (active entries, seen first) and
    ``top_live`` (most-read full live plates). Audited by the middleware
    like every ``/api/plates/*`` query (B12)."""
    return plate_search.suggest(con, limit)


@router.get("/plates/{plate}/route", response_model=schemas.RouteOut)
def plate_route(
    plate: str,
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    con: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_auth),
    __: None = Depends(_limit_route),
):
    """THE scored endpoint — a vehicle's timestamped, location-wise route
    across the camera network (docs/api.md §7; audited by middleware;
    rate-limited per identity, §9)."""
    return reconstruct_route(con, plate, min_confidence)


# ------------------------------------------------------------------ watchlist

@router.get("/watchlist", response_model=list[schemas.WatchlistOut])
def list_watchlist(
    con: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_auth),
):
    """The watchlist, highest severity first."""
    return [
        dict(r)
        for r in con.execute(
            "SELECT * FROM watchlist ORDER BY CASE severity"
            " WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, plate"
        )
    ]


@router.post("/watchlist", response_model=schemas.WatchlistOut, status_code=201)
def add_watchlist(
    request: Request,
    entry: schemas.WatchlistIn,
    con: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_evaluator),
):
    """Add a plate to the watchlist (normalised and canonical-folded at the
    boundary); 409 when it is already listed. Evaluator or admin (F41)."""
    norm = plates.normalise(entry.plate)
    if not norm:
        raise HTTPException(status_code=422, detail="plate is empty after normalisation")
    try:
        cur = con.execute(
            "INSERT INTO watchlist (plate, plate_canonical, category, severity,"
            " description, source_ref, active, added_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
            (norm, plates.canonical(norm), entry.category, entry.severity,
             entry.description, entry.source_ref, dbmod.utcnow()),
        )
        con.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail=f"'{norm}' is already on the watchlist")
    row = dict(
        con.execute("SELECT * FROM watchlist WHERE watchlist_id = ?", (cur.lastrowid,)).fetchone()
    )
    set_audit(request, entity="watchlist", entity_id=str(row["watchlist_id"]), after=row)
    return row


@router.delete("/watchlist/{watchlist_id}", response_model=schemas.WatchlistDeleteOut)
def delete_watchlist(
    request: Request,
    watchlist_id: int,
    con: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_evaluator),
):
    """Remove a watchlist entry; 404 when it does not exist. Evaluator or
    admin (F41: watchlist add and remove)."""
    before = con.execute(
        "SELECT * FROM watchlist WHERE watchlist_id = ?", (watchlist_id,)
    ).fetchone()
    if before is None:
        raise HTTPException(status_code=404, detail="watchlist entry not found")
    con.execute("DELETE FROM watchlist WHERE watchlist_id = ?", (watchlist_id,))
    con.commit()
    set_audit(request, entity="watchlist", entity_id=str(watchlist_id), before=dict(before))
    return {"deleted": watchlist_id}


# --------------------------------------------------------------------- alerts

@router.get("/alerts", response_model=list[schemas.AlertOut])
def list_alerts(
    con: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_auth),
    severity: Literal["high", "medium", "low", "critical"] | None = None,
    acknowledged: bool | None = None,
    kind: Literal["watchlist", "zone"] | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
):
    """Recent alerts (both kinds), newest first."""
    sql, args = _ALERT_SELECT + " WHERE 1=1", []
    if severity:
        sql += " AND a.severity = ?"
        args.append(severity)
    if acknowledged is True:
        sql += " AND a.acknowledged_at IS NOT NULL"
    elif acknowledged is False:
        sql += " AND a.acknowledged_at IS NULL"
    if kind:
        sql += " AND a.kind = ?"
        args.append(kind)
    sql += " ORDER BY a.fired_at DESC, a.alert_seq DESC LIMIT ?"
    args.append(limit)
    return [_alert_dict(r) for r in con.execute(sql, args)]


@router.post("/alerts/{alert_id}/ack", response_model=schemas.AlertOut)
def ack_alert(
    request: Request,
    alert_id: str,
    con: sqlite3.Connection = Depends(get_db),
    role: str = Depends(require_evaluator),
):
    """Acknowledge an alert (by its ``alert_id``, or the numeric
    ``alert_seq``), persisting who acknowledged it. Evaluator or admin
    (F41: acknowledge)."""
    if alert_id.isdigit():
        clause, key = "a.alert_seq = ?", int(alert_id)
    else:
        clause, key = "a.alert_id = ?", alert_id
    before = con.execute(_ALERT_SELECT + " WHERE " + clause, (key,)).fetchone()
    if before is None:
        raise HTTPException(status_code=404, detail=f"unknown alert {alert_id!r}")
    # The actor is the signed-in username once sessions exist (S3.0);
    # for key-authenticated calls it is the role.
    actor = (
        getattr(request.state, "actor", None)
        or getattr(request.state, "username", None)
        or role
    )
    con.execute(
        "UPDATE alerts SET acknowledged_at = ?, acknowledged_by = ? WHERE alert_seq = ?",
        (dbmod.utcnow(), actor, before["alert_seq"]),
    )
    con.commit()
    after = _alert_dict(
        con.execute(_ALERT_SELECT + " WHERE a.alert_seq = ?", (before["alert_seq"],)).fetchone()
    )
    set_audit(request, entity="alerts", entity_id=str(before["alert_id"]),
              before=_alert_dict(before), after=after)
    return after


# ----------------------------------------------------------------- SSE tailer

def _alerts_after(after_seq: int) -> list[dict[str, Any]]:
    """Alerts past *after_seq*, oldest first, on a fresh connection."""
    con = dbmod.connect()
    try:
        return [
            _alert_dict(r)
            for r in con.execute(
                _ALERT_SELECT + " WHERE a.alert_seq > ? ORDER BY a.alert_seq",
                (after_seq,),
            )
        ]
    finally:
        con.close()


def _max_alert_seq() -> int:
    con = dbmod.connect()
    try:
        return int(con.execute("SELECT COALESCE(MAX(alert_seq), 0) FROM alerts").fetchone()[0])
    finally:
        con.close()


class _AlertTailer:
    """The ONE background tailer over ``alerts`` (C15, F27, B8).

    Polls the table past its cursor every 2 s and fans each new row out to
    every subscriber queue. ``alert_seq`` is AUTOINCREMENT, so the cursor
    stays monotonic even after a purge. Restarts itself if the event loop
    changed (each TestClient runs its own loop) or the task died.
    """

    def __init__(self) -> None:
        self._queues: set[asyncio.Queue] = set()
        self._task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._last_seq = 0

    def subscribe(self) -> asyncio.Queue:
        loop = asyncio.get_running_loop()
        if self._task is None or self._task.done() or self._loop is not loop:
            self._queues.clear()  # queues of a dead loop are unreachable
            self._loop = loop
            # Cursor set synchronously so a row committed right after
            # subscribing can never fall between task start and first poll.
            self._last_seq = _max_alert_seq()
            self._task = loop.create_task(self._run(), name="alert-sse-tailer")
        q: asyncio.Queue = asyncio.Queue()
        self._queues.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._queues.discard(q)

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(_SSE_POLL_S)
            try:
                rows = await asyncio.to_thread(_alerts_after, self._last_seq)
            except Exception:
                log.exception("alert tailer poll failed; retrying")
                continue
            for row in rows:
                self._last_seq = max(self._last_seq, int(row["alert_seq"]))
                for q in list(self._queues):
                    q.put_nowait(row)


_TAILER = _AlertTailer()


def _sse_frame(row: dict[str, Any]) -> str:
    return (
        f"id: {row['alert_seq']}\nevent: alert\n"
        f"data: {json.dumps(row, default=str)}\n\n"
    )


@router.get(
    "/alerts/stream",
    responses={
        200: {
            "description": "Server-sent alert events; frames carry id: <alert_seq> "
            "and Last-Event-ID replays the gap.",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        }
    },
)
async def alerts_stream(request: Request, _: str = Depends(require_auth)) -> StreamingResponse:
    """SSE — live alert push (both kinds, one table, one tailer).

    Alerts fire in the worker process, so this tails the ``alerts`` table
    (never an in-process bus, F27). The session cookie is accepted here
    because ``EventSource`` cannot send headers.
    """
    header = request.headers.get("Last-Event-ID")
    try:
        replay_from: int | None = int(header) if header else None
    except ValueError:
        replay_from = None

    async def stream() -> AsyncIterator[str]:
        queue = _TAILER.subscribe()
        try:
            yield ": connected\n\n"
            sent = 0
            if replay_from is not None:
                sent = replay_from
                for row in await asyncio.to_thread(_alerts_after, replay_from):
                    sent = max(sent, int(row["alert_seq"]))
                    yield _sse_frame(row)
            while True:
                try:
                    row = await asyncio.wait_for(queue.get(), timeout=_SSE_KEEPALIVE_S)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if int(row["alert_seq"]) <= sent:
                    continue  # already replayed
                sent = int(row["alert_seq"])
                yield _sse_frame(row)
        finally:
            _TAILER.unsubscribe(queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


# --------------------------------------------------------------------- events

@router.get("/events", response_model=list[schemas.EventOut])
def list_events(
    con: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_auth),
    camera_id: str | None = Query(default=None, pattern=schemas.CAMERA_ID_PATTERN),
    event_type: Literal["intrusion", "line_cross", "object_detected"] | None = None,
    limit: int = Query(default=200, ge=1, le=2000),
):
    """Zone and object events, newest first."""
    sql, args = "SELECT * FROM events WHERE 1=1", []
    if camera_id:
        sql += " AND camera_id = ?"
        args.append(camera_id)
    if event_type:
        sql += " AND event_type = ?"
        args.append(event_type)
    sql += " ORDER BY occurred_at DESC, event_id DESC LIMIT ?"
    args.append(limit)
    return [dict(r) for r in con.execute(sql, args)]


@router.get("/events/summary", response_model=schemas.EventsSummaryOut)
def events_summary(
    con: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_auth),
    minutes: int = Query(default=60, ge=1, le=1440),
):
    """Per-camera object/zone event counts over the last *minutes* of the
    recording timeline (event timestamps live on that shared timeline, so
    the window is anchored at the newest event, not the wall clock)."""
    latest = con.execute("SELECT MAX(occurred_at) FROM events").fetchone()[0]
    cameras: dict[str, dict[str, Any]] = {}
    total = 0
    if latest:
        edge = datetime.fromisoformat(latest)
        if edge.tzinfo is None:
            edge = edge.replace(tzinfo=timezone.utc)
        since = dbmod.iso(edge - timedelta(minutes=minutes))
        for cam, etype, oclass, n in con.execute(
            "SELECT camera_id, event_type, object_class, COUNT(*) AS n"
            " FROM events WHERE occurred_at >= ?"
            " GROUP BY camera_id, event_type, object_class",
            (since,),
        ):
            c = cameras.setdefault(cam, {"objects": {}, "intrusion": 0, "line_cross": 0})
            if etype == "object_detected":
                key = oclass or "unknown"
                c["objects"][key] = c["objects"].get(key, 0) + n
            elif etype in ("intrusion", "line_cross"):
                c[etype] += n
            total += n
    return {"minutes": minutes, "total": total, "cameras": cameras}


# -------------------------------------------------------------------- workers

def _worker_stats_path() -> Path:
    return config.REPO_ROOT / "data" / "worker_stats.json"


@router.get("/workers", response_model=schemas.WorkersOut)
def worker_stats(_: str = Depends(require_auth)):
    """The worker supervisor's last stats snapshot (data/worker_stats.json):
    sustained fps, skip rate, detections/min, per-camera counters."""
    try:
        data = json.loads(_worker_stats_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return schemas.WorkersOut(available=False)
    if not isinstance(data, dict):
        return schemas.WorkersOut(available=False)
    return schemas.WorkersOut(available=True, **data)
