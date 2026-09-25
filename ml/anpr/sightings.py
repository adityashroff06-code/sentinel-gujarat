"""Sighting persistence with the bounded dedupe (task S2.4; api.md §2, B13).

Dedupe: same ``plate_canonical`` on the same camera **in the same
clock_source** whose ``seen_at`` is within 60 s (two-sided) of the new
read AND whose ``wall_time`` is within 10 min of the new read's — update
the confidence if better, never insert. Everything else inserts.

Crops are ~2 KB JPEGs under ``data/crops/<cam>/``, stored with forward
slashes (a backslash path 404s in the UI — sandbox-findings §7).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import cv2
import numpy as np

from backend.core import plates
from backend.core.config import REPO_ROOT
from backend.core.db import iso as _iso
from backend.core.db import utcnow
from backend.core.logging_setup import setup

log = setup("sightings")

DEDUPE_SEEN_S = 60.0
DEDUPE_WALL_S = 600.0
_CROP_MAX_WIDTH = 160
_CROP_JPEG_QUALITY = 70


def _save_crop(camera_id: str, sighting_id: int, crop: np.ndarray) -> str | None:
    if crop is None or crop.size == 0:
        return None
    if crop.shape[1] > _CROP_MAX_WIDTH:
        scale = _CROP_MAX_WIDTH / crop.shape[1]
        crop = cv2.resize(crop, (_CROP_MAX_WIDTH, max(1, int(crop.shape[0] * scale))))
    rel = f"data/crops/{camera_id}/{sighting_id}.jpg"
    path = REPO_ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), crop, [cv2.IMWRITE_JPEG_QUALITY, _CROP_JPEG_QUALITY])
    return rel  # forward slashes, always


def record_sighting(
    con: sqlite3.Connection,
    *,
    camera_id: str,
    plate: str,
    plate_raw: str,
    confidence: float,
    seen_at: datetime,
    wall_time: datetime,
    clock_source: str,
    provenance: str,
    pts_ms: float | None = None,
    bbox_json: str | None = None,
    vehicle_class: str | None = None,
    track_id: str | None = None,
    crop: np.ndarray | None = None,
    frame_path: str | None = None,
) -> tuple[int, bool]:
    """Insert (or dedupe into) a sighting; returns ``(sighting_id, inserted)``.

    *plate* is the normalised read — for a structurally full OCR read the
    pipeline has already coerced it (``plates.coerce``, docs/api.md §6),
    while *plate_raw* keeps the OCR text; the canonical fold happens here
    at write time (coercion never changes it). The caller owns *provenance* (``live`` for real pulls,
    ``test`` for replay, ``demo`` for the seeder — F26) and commits via
    its writer job; this function does not commit.
    """
    canonical = plates.canonical(plate)
    seen_iso, wall_iso = _iso(seen_at), _iso(wall_time)
    lo = _iso(seen_at - timedelta(seconds=DEDUPE_SEEN_S))
    hi = _iso(seen_at + timedelta(seconds=DEDUPE_SEEN_S))
    for row in con.execute(
        "SELECT sighting_id, confidence, wall_time FROM sightings"
        " WHERE plate_canonical = ? AND camera_id = ? AND clock_source = ?"
        " AND seen_at BETWEEN ? AND ? ORDER BY seen_at DESC",
        (canonical, camera_id, clock_source, lo, hi),
    ):
        existing_wall = datetime.fromisoformat(row["wall_time"])
        if abs((wall_time.astimezone(timezone.utc) - existing_wall).total_seconds()) <= DEDUPE_WALL_S:
            if confidence > row["confidence"]:
                con.execute("UPDATE sightings SET confidence = ? WHERE sighting_id = ?",
                            (confidence, row["sighting_id"]))
            return int(row["sighting_id"]), False

    cur = con.execute(
        "INSERT INTO sightings (plate, plate_raw, plate_canonical, confidence,"
        " camera_id, seen_at, wall_time, clock_source, provenance, pts_ms,"
        " bbox_json, vehicle_class, crop_path, frame_path, track_id, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)",
        (plate, plate_raw, canonical, confidence, camera_id, seen_iso, wall_iso,
         clock_source, provenance, pts_ms, bbox_json, vehicle_class, frame_path,
         track_id, utcnow()),
    )
    sighting_id = int(cur.lastrowid)
    if crop is not None:
        crop_path = _save_crop(camera_id, sighting_id, crop)
        if crop_path:
            con.execute("UPDATE sightings SET crop_path = ? WHERE sighting_id = ?",
                        (crop_path, sighting_id))
    return sighting_id, True
