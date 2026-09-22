"""Camera registry routes (docs/api.md §1, §7).

Route-order trap: ``/gap-analysis`` and ``/import`` are registered
**before** ``/{camera_id}`` so FastAPI never swallows them as ids.
"""

from __future__ import annotations

import csv
import io
import sqlite3
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from pydantic import ValidationError

from backend.app import schemas
from backend.app.audit import set_audit
from backend.app.auth import require_admin, require_auth
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


@router.post("", response_model=schemas.CameraOut, status_code=201)
def create_camera(
    request: Request,
    cam: schemas.CameraIn,
    con: sqlite3.Connection = Depends(get_db),
    _: str = Depends(require_admin),
):
    """Manual camera onboarding (Model 1 deliverable); 409 on a duplicate id."""
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
