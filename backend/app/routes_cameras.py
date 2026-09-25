"""Camera registry routes (docs/api.md §1, §7).

Route-order trap: ``/gap-analysis``, ``/activity`` and ``/import`` are
registered **before** ``/{camera_id}`` so FastAPI never swallows them as ids.
"""

from __future__ import annotations

import csv
import io
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from pydantic import ValidationError

from backend.app import schemas
from backend.app.audit import set_audit
from backend.app.auth import require_admin, require_auth, require_evaluator
from backend.core import db as dbmod

router = APIRouter(prefix="/api/cameras", tags=["cameras"])

_COLUMNS = [
    "camera_id", "department", "location_name", "lat", "lon", "bearing_deg",
    "fov_deg", "range_m", "codec", "hls_url", "rtsp_url_template",
    "whep_url_template", "transport", "ownership", "fps_tier", "roi_json",
    "zones_json", "source", "notes",
]


def get_db() -> Iterator[sqlite3.Connection]:
    con = dbmod.connect()
    try:
        yield con
    finally:
        con.close()


def _insert_camera(con: sqlite3.Connection, cam: schemas.CameraIn) -> None:
    now = dbmod.utcnow()
    values = cam.model_dump()
    con.execute(
        f"INSERT INTO cameras ({', '.join(_COLUMNS)}, created_at, updated_at)"
        f" VALUES ({', '.join('?' for _ in _COLUMNS)}, ?, ?)",
        [values[c] for c in _COLUMNS] + [now, now],
    )


@router.get("", response_model=schemas.CameraListOut)
def list_cameras(
    con: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_auth),
    department: str | None = None,
    health: str | None = None,
    tier: str | None = None,
    q: str | None = None,
):
    """List cameras with optional department/health/tier/text filters."""
    where, params = ["1=1"], []
    if department:
        where.append("department = ?"); params.append(department)
    if health:
        where.append("health = ?"); params.append(health)
    if tier:
        where.append("fps_tier = ?"); params.append(tier)
    if q:
        where.append("(camera_id LIKE ? OR location_name LIKE ? OR department LIKE ?)")
        params.extend([f"%{q}%"] * 3)
    clause = " AND ".join(where)
    rows = [dict(r) for r in con.execute(
        f"SELECT * FROM cameras WHERE {clause} ORDER BY camera_id", params
    )]
    total = con.execute(f"SELECT COUNT(*) FROM cameras WHERE {clause}", params).fetchone()[0]
    return {"total": total, "cameras": rows}


@router.get("/gap-analysis", response_model=schemas.GapAnalysisOut)
def gap_analysis(
    con: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_auth),
):
    """Coverage gap analysis: offline/degraded cameras, isolated coverage, department summary (Model 1 deliverable)."""
    from backend.services import gap_analysis as service

    return service.generate(con)


@router.get("/activity", response_model=list[schemas.CameraActivityOut])
def camera_activity(
    con: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_auth),
    hours: int = Query(default=24, ge=1, le=168),
):
    """Plate reads, distinct plates and alerts per camera over the last
    *hours*, anchored at the server's wall clock (``seen_at`` / ``fired_at``
    at or after now − hours). Cameras with no activity in the window are
    omitted; ``sightings`` is split by provenance in ``by_provenance`` and
    ``alerts`` in ``alerts_by_provenance`` (root rule 12: a demo alert never
    passes as a live one). An alert's provenance is its source row's — the
    sighting (watchlist) or event (zone) — or, with neither, its own
    ``clock_source`` mapped as the worker maps it (F26; unknown = ``test``,
    never ``live``). Registered before ``/{camera_id}`` so it is never read
    as an id."""
    since = dbmod.iso(datetime.now(timezone.utc) - timedelta(hours=hours))
    out: dict[str, dict[str, Any]] = {}

    def entry(camera_id: str) -> dict[str, Any]:
        return out.setdefault(camera_id, {
            "camera_id": camera_id, "sightings": 0, "plates": 0, "alerts": 0,
            "last_seen": None, "by_provenance": {}, "alerts_by_provenance": {},
        })

    for camera_id, n, plates, last in con.execute(
        "SELECT camera_id, COUNT(*), COUNT(DISTINCT plate), MAX(seen_at)"
        " FROM sightings WHERE seen_at >= ? GROUP BY camera_id",
        (since,),
    ):
        e = entry(camera_id)
        e.update(sightings=n, plates=plates, last_seen=last)
    for camera_id, provenance, n in con.execute(
        "SELECT camera_id, provenance, COUNT(*) FROM sightings"
        " WHERE seen_at >= ? GROUP BY camera_id, provenance",
        (since,),
    ):
        entry(camera_id)["by_provenance"][provenance] = n
    for camera_id, provenance, n in con.execute(
        "SELECT a.camera_id, COALESCE(s.provenance, e.provenance,"
        " CASE a.clock_source WHEN 'rtsp-live' THEN 'live' WHEN 'hls-vod' THEN 'harvest'"
        " WHEN 'harvest' THEN 'harvest' WHEN 'demo' THEN 'demo' ELSE 'test' END),"
        " COUNT(*) FROM alerts a"
        " LEFT JOIN sightings s ON s.sighting_id = a.sighting_id"
        " LEFT JOIN events e ON e.event_id = a.event_id"
        " WHERE a.fired_at >= ? GROUP BY 1, 2",
        (since,),
    ):
        e = entry(camera_id)
        e["alerts"] += n
        e["alerts_by_provenance"][provenance] = n
    return sorted(out.values(), key=lambda e: (-e["sightings"], -e["alerts"], e["camera_id"]))


@router.post("/import", response_model=schemas.ImportOut)
def import_csv(
    request: Request,
    file: UploadFile,
    con: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_admin),
):
    """Bulk CSV onboarding: per-row accepted/rejected with reasons; one transaction, no partial commit (Model 1 deliverable)."""
    text = file.file.read().decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    accepted_rows: list[tuple[int, schemas.CameraIn]] = []
    rejected: list[dict] = []
    for row_number, raw in enumerate(reader, start=1):
        payload = {k: v for k, v in (raw or {}).items() if k and v not in (None, "")}
        payload.setdefault("source", "csv")
        try:
            cam = schemas.CameraIn(**payload)
        except ValidationError as exc:
            first = exc.errors()[0]
            field = ".".join(str(p) for p in first["loc"]) or "row"
            rejected.append({"row": row_number, "reason": f"{field}: {first['msg']}"})
            continue
        accepted_rows.append((row_number, cam))

    # One transaction, no partial commit: a duplicate rejects that row and
    # the rest of the batch still lands together.
    inserted: list[str] = []
    try:
        for row_number, cam in accepted_rows:
            try:
                _insert_camera(con, cam)
                inserted.append(cam.camera_id)
            except sqlite3.IntegrityError:
                rejected.append(
                    {"row": row_number, "reason": f"camera_id: '{cam.camera_id}' already exists"}
                )
        con.commit()
    except Exception:
        con.rollback()
        raise
    set_audit(request, entity="cameras", entity_id="import",
              after={"accepted": inserted, "rejected": rejected})
    return {"accepted": inserted, "rejected": rejected}


@router.get("/{camera_id}", response_model=schemas.CameraOut)
def get_camera(
    camera_id: str,
    con: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_auth),
):
    """One camera, full record."""
    row = con.execute("SELECT * FROM cameras WHERE camera_id = ?", (camera_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="camera not found")
    return dict(row)


@router.get("/{camera_id}/stream", response_model=schemas.StreamOut)
def stream_url(
    camera_id: str,
    con: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_auth),
):
    """The playable HLS URL for this session — always the backend relay path, never an upstream URL."""
    row = con.execute("SELECT camera_id FROM cameras WHERE camera_id = ?", (camera_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="camera not found")
    return {"hls": f"/api/hls/{camera_id}/live.m3u8"}


@router.post("", response_model=schemas.CameraOut, status_code=201)  # §7 roles:
# the onboarding form is an evaluator action; PATCH (tier/ROI/zones) stays admin
def create_camera(
    request: Request,
    cam: schemas.CameraIn,
    con: sqlite3.Connection = Depends(get_db),
    role: str = Depends(require_evaluator),
):
    """Manual camera onboarding (Model 1 deliverable); 409 on a duplicate id.

    An evaluator onboards a camera as a registered, non-catalogue row; only
    an admin may create one straight into the analysed tier or as a
    catalogue camera (403 otherwise). 25 Sep review gate: the form let an
    evaluator set ``fps_tier='active'`` + ``source='catalogue'``, which the
    worker picks first — bypassing the admin-only tier rule of PATCH and,
    before the gateway check, steering the sandbox credentials (rule 1).
    """
    if role != "admin" and (cam.fps_tier != "registered" or cam.source == "catalogue"):
        raise HTTPException(
            status_code=403,
            detail="only an admin may onboard a camera into the analysed tier"
                   " or as a catalogue camera",
        )
    try:
        _insert_camera(con, cam)
        con.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail=f"camera '{cam.camera_id}' already exists")
    row = dict(con.execute("SELECT * FROM cameras WHERE camera_id = ?", (cam.camera_id,)).fetchone())
    set_audit(request, entity="cameras", entity_id=cam.camera_id, after=row)
    return row


@router.patch("/{camera_id}", response_model=schemas.CameraOut)
def patch_camera(
    request: Request,
    camera_id: str,
    patch: schemas.CameraPatch,
    con: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_admin),
):
    """Edit camera metadata, ROI, zones, health or tier."""
    before = con.execute("SELECT * FROM cameras WHERE camera_id = ?", (camera_id,)).fetchone()
    if before is None:
        raise HTTPException(status_code=404, detail="camera not found")
    changes = patch.model_dump(exclude_unset=True)
    if changes:
        sets = ", ".join(f"{k} = ?" for k in changes)
        con.execute(
            f"UPDATE cameras SET {sets}, updated_at = ? WHERE camera_id = ?",
            [*changes.values(), dbmod.utcnow(), camera_id],
        )
        con.commit()
    after = dict(con.execute("SELECT * FROM cameras WHERE camera_id = ?", (camera_id,)).fetchone())
    set_audit(request, entity="cameras", entity_id=camera_id, before=dict(before), after=after)
    return after
