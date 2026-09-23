"""Greedy IoU + centre-distance tracker (task S2.3; decision F14).

Matches on **vehicle superclass** so a car↔truck flip keeps one track
(review A3). Velocity comes from PTS deltas, never wall clock. Track ids
are unique for the tracker's lifetime — ``reset()`` clears the tracks but
never the counter, so zone state can never attach to a reused id after a
restart (ml/CLAUDE.md).

Honestly an IoU tracker (never described as ByteTrack — F14). At 1–3 fps
a fast vehicle can move past IoU overlap between samples, so unmatched
pairs fall back to a centre-distance bound scaled by the box size.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ml.anpr.detect import Detection

_MAX_BOXES_KEPT = 30


@dataclass
class Track:
    id: int
    boxes: list[tuple[float, float, float, float]]
    last_seen_pts: float
    superclass: str
    cls: str
    ocr_reads: list[Any] = field(default_factory=list)  # PlateRead rows (S2.4)
    velocity: tuple[float, float] = (0.0, 0.0)          # px/s from PTS deltas
    hits: int = 1
    last_ocr_pts: float = float("-inf")                  # OCR budget (S2.4)
    committed_full: bool = False                         # full consensus stored (S2.4)

    @property
    def centre(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.boxes[-1]
        return (x1 + x2) / 2, (y1 + y2) / 2


def _iou(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter == 0.0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (area_a + area_b - inter)


class Tracker:
    """``update(detections, pts_ms)`` returns ``[(track, detection), …]``
    for this frame's matched and newly created tracks."""

    def __init__(self, iou_min: float = 0.2, max_age_s: float = 3.0) -> None:
        self.iou_min = iou_min
        self.max_age_s = max_age_s
        self.tracks: dict[int, Track] = {}
        self._next_id = 1  # never reset — ids are unique for the lifetime

    def reset(self) -> None:
        """Drop every track on a restart tick; ids keep counting."""
        self.tracks.clear()

    def _new_track(self, det: Detection, pts_ms: float) -> Track:
        track = Track(id=self._next_id, boxes=[det.xyxy], last_seen_pts=pts_ms,
                      superclass=det.superclass, cls=det.cls)
        self._next_id += 1
        self.tracks[track.id] = track
        return track

    def update(self, detections: list[Detection], pts_ms: float) -> list[tuple[Track, Detection]]:
        # Age out stale tracks first (PTS domain, never wall clock).
        for tid in [t.id for t in self.tracks.values()
                    if pts_ms - t.last_seen_pts > self.max_age_s * 1000.0]:
            del self.tracks[tid]

        # Greedy: best IoU pairs first, then centre-distance leftovers.
        candidates: list[tuple[float, int, int]] = []  # (-score, track_id, det_idx)
        for track in self.tracks.values():
            for i, det in enumerate(detections):
                if det.superclass != track.superclass:
                    continue
                iou = _iou(track.boxes[-1], det.xyxy)
                if iou >= self.iou_min:
                    candidates.append((-(1.0 + iou), track.id, i))  # IoU beats any distance match
                else:
                    cx, cy = track.centre
                    dx = (det.xyxy[0] + det.xyxy[2]) / 2 - cx
                    dy = (det.xyxy[1] + det.xyxy[3]) / 2 - cy
                    x1, y1, x2, y2 = track.boxes[-1]
                    # ponytail: centre gate = 2x the box's larger side; a real
                    # motion model (Kalman) only after a measured ID-switch cut (F14)
                    limit = 2.0 * max(x2 - x1, y2 - y1)
                    dist = (dx * dx + dy * dy) ** 0.5
                    if dist <= limit:
                        # key in (-1, 0]: always after every IoU pair (< -1.2)
                        candidates.append((dist / limit - 1.0, track.id, i))
        candidates.sort()

        matched_tracks: set[int] = set()
        matched_dets: set[int] = set()
        result: list[tuple[Track, Detection]] = []
        for _, tid, i in candidates:
            if tid in matched_tracks or i in matched_dets or tid not in self.tracks:
                continue
            matched_tracks.add(tid)
            matched_dets.add(i)
            track, det = self.tracks[tid], detections[i]
            dt_s = (pts_ms - track.last_seen_pts) / 1000.0
            if dt_s > 0:
                cx0, cy0 = track.centre
                cx1 = (det.xyxy[0] + det.xyxy[2]) / 2
                cy1 = (det.xyxy[1] + det.xyxy[3]) / 2
                track.velocity = ((cx1 - cx0) / dt_s, (cy1 - cy0) / dt_s)
            track.boxes.append(det.xyxy)
            del track.boxes[:-_MAX_BOXES_KEPT]
            track.last_seen_pts = pts_ms
            track.cls = det.cls  # latest class label; superclass is stable
            track.hits += 1
            result.append((track, det))

        for i, det in enumerate(detections):
            if i not in matched_dets:
                result.append((self._new_track(det, pts_ms), det))
        return result
