"""Coverage gap analysis (Model 1 deliverable — docs/api.md §7).

Nearest-neighbour Haversine over cameras with coordinates, offline/degraded
listing, and a per-department summary. Pure read — one short transaction.
"""

from __future__ import annotations

import math
import sqlite3
from typing import Any

from backend.core import db as dbmod

EARTH_RADIUS_KM = 6371.0
ISOLATION_RADIUS_KM = 5.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def generate(con: sqlite3.Connection) -> dict[str, Any]:
    """The gap-analysis report shape of docs/api.md §7 / B3."""
    cameras = [dict(r) for r in con.execute("SELECT * FROM cameras")]
    located = [c for c in cameras if c["lat"] is not None and c["lon"] is not None]

    isolated: list[dict[str, Any]] = []
    for cam in located:
        nearest = min(
            (
                haversine_km(cam["lat"], cam["lon"], other["lat"], other["lon"])
                for other in located
                if other["camera_id"] != cam["camera_id"]
            ),
            default=None,
        )
        if nearest is not None and nearest > ISOLATION_RADIUS_KM:
            isolated.append(
                {
                    "camera_id": cam["camera_id"],
                    "nearest_neighbour_km": round(nearest, 2),
                    "radius_km": ISOLATION_RADIUS_KM,
                }
            )

    offline = [
        {
            "camera_id": c["camera_id"],
            "health": c["health"],
            "last_seen": c["last_seen"],
            "department": c["department"],
        }
        for c in cameras
        if c["health"] in ("offline", "degraded") or c["health"] is None
    ]

    departments: dict[str, dict[str, int]] = {}
    for c in cameras:
        dept = c["department"] or "Unknown"
        entry = departments.setdefault(dept, {"total": 0, "online": 0})
        entry["total"] += 1
        if c["health"] == "online":
            entry["online"] += 1

    return {
        "generated_at": dbmod.utcnow(),
        "cameras_total": len(cameras),
        "online": sum(1 for c in cameras if c["health"] == "online"),
        "active_tier": sum(1 for c in cameras if c["fps_tier"] == "active"),
        "cameras_offline_or_degraded": offline,
        "isolated_coverage": isolated,
        "department_summary": departments,
    }
