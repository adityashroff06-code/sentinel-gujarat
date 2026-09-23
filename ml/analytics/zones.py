"""Zones — intrusion polygons and crossing lines (S2.5; api.md §5).

Canonical shape only (B1): ``[{zone_id, name, type, severity, points}]``
with normalised 0–1 coordinates, so zones survive resolution changes.

**A zone fires only after confirmation** (v2.3): the foot point must be
inside for 2 consecutive sampled frames — at 1–3 fps that still catches
a moving vehicle, and one bad box can never put a false intrusion on the
dashboard in front of the jury. A line crossing is measured against the
last **confirmed** side (2 consecutive frames on one side) and fires
downward (+y) only. Track ids are unique for the worker's lifetime, so
zone state never attaches to a reused id after a restart.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

CONFIRM_FRAMES = 2


@dataclass
class Zone:
    zone_id: str
    name: str
    type: str        # intrusion | line
    severity: str    # high | medium | low
    points: list[tuple[float, float]]


def validate_zone(z: dict) -> str | None:
    """The PATCH-time check: an error message, or None when valid."""
    if not isinstance(z, dict) or not z.get("zone_id"):
        return "zone_id is required"
    ztype = z.get("type")
    points = z.get("points")
    if ztype not in ("intrusion", "line"):
        return f"type must be intrusion or line, not {ztype!r}"
    if not isinstance(points, list) or not all(
            isinstance(p, (list, tuple)) and len(p) == 2 for p in points or []):
        return "points must be a list of [x, y] pairs"
    if ztype == "intrusion" and len(points) < 3:
        return "an intrusion polygon needs at least 3 points"
    if ztype == "line" and len(points) != 2:
        return "a line needs exactly 2 points"
    if z.get("severity") not in ("high", "medium", "low"):
        return "severity must be high, medium or low"
    return None


def parse_zones(zones_json: str | None) -> list[Zone]:
    """The registry row's ``zones_json`` as validated zones; bad entries
    are dropped (a stored zone passed PATCH validation; defensive here)."""
    if not zones_json:
        return []
    try:
        raw = json.loads(zones_json)
    except ValueError:
        return []
    zones = []
    for z in raw if isinstance(raw, list) else []:
        if validate_zone(z) is None:
            zones.append(Zone(zone_id=z["zone_id"], name=z.get("name", z["zone_id"]),
                              type=z["type"], severity=z["severity"],
                              points=[(float(x), float(y)) for x, y in z["points"]]))
    return zones


def _inside(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    """Ray casting; on-edge counts as inside enough for a foot point."""
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


@dataclass
class _TrackZoneState:
    inside_streak: int = 0
    fired: bool = False
    confirmed_side: int = 0   # line: -1 above / +1 below (0 = none yet)
    candidate_side: int = 0
    candidate_streak: int = 0


@dataclass
class ZoneHit:
    zone: Zone
    event_type: str  # intrusion | line_cross


class ZoneMonitor:
    """Per-camera zone state machine over track foot points (normalised)."""

    def __init__(self, zones: list[Zone]) -> None:
        self.zones = zones
        self._state: dict[tuple[str, int | str], _TrackZoneState] = {}

    def set_zones(self, zones: list[Zone]) -> None:
        """Hot reload from the supervisor poll; per-track state survives
        for zones whose id is unchanged."""
        kept = {z.zone_id for z in zones}
        self.zones = zones
        self._state = {k: v for k, v in self._state.items() if k[0] in kept}

    def reset(self) -> None:
        self._state.clear()

    def _line_side(self, zone: Zone, foot: tuple[float, float]) -> int:
        (x1, y1), (x2, y2) = zone.points
        if x2 == x1:
            return 0  # vertical line: "down = +y" crossing is undefined
        s = (x2 - x1) * (foot[1] - y1) - (y2 - y1) * (foot[0] - x1)
        s *= 1.0 if x2 > x1 else -1.0  # normalise so +1 is the +y (below) side
        return 1 if s > 0 else (-1 if s < 0 else 0)

    def update(self, track_id: int | str, foot: tuple[float, float]) -> list[ZoneHit]:
        """Advance one track by one sampled frame; return the zones that
        fire on this frame."""
        hits: list[ZoneHit] = []
        for zone in self.zones:
            state = self._state.setdefault((zone.zone_id, track_id), _TrackZoneState())
            if zone.type == "intrusion":
                if _inside(foot, zone.points):
                    state.inside_streak += 1
                    if state.inside_streak >= CONFIRM_FRAMES and not state.fired:
                        state.fired = True
                        hits.append(ZoneHit(zone, "intrusion"))
                else:
                    state.inside_streak = 0
            else:  # line
                side = self._line_side(zone, foot)
                if side == 0:
                    continue
                if side == state.candidate_side:
                    state.candidate_streak += 1
                else:
                    state.candidate_side, state.candidate_streak = side, 1
                if state.candidate_streak >= CONFIRM_FRAMES:
                    if state.confirmed_side == -1 and side == 1:
                        hits.append(ZoneHit(zone, "line_cross"))  # downward only
                    state.confirmed_side = side
        return hits
