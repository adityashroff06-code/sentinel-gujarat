"""Motion gate — MOG2 background subtraction (task S2.3; review D12).

A frame with less foreground than the threshold ratio is skipped before
the detector ever runs. Per-camera threshold from the registry row's
``notes`` JSON (key ``motion_min_ratio``), else the config default.
``reset()`` on every ``restart`` tick (the background model is stale
after a reconnect or a replay wrap).
"""

from __future__ import annotations

import json
from typing import Any, Mapping

import cv2
import numpy as np

from backend.core import config

_WARMUP_FRAMES = 5
_SCALE_WIDTH = 320  # subtraction runs on a downscaled copy; the gate is a cost saver


class MotionGate:
    """``moving(frame)`` is True for frames the pipeline should process."""

    def __init__(self, min_ratio: float | None = None) -> None:
        self.min_ratio = config.motion_min_ratio() if min_ratio is None else min_ratio
        self._sub: cv2.BackgroundSubtractorMOG2 | None = None
        self._frames = 0

    def reset(self) -> None:
        """Drop the background model (call on every restart tick)."""
        self._sub = None
        self._frames = 0

    def moving(self, frame: np.ndarray) -> bool:
        """True when the foreground ratio is at least ``min_ratio``.

        The first few frames after (re)start always pass — the model is
        still learning and a vehicle present at start must not be missed.
        """
        if self._sub is None:
            self._sub = cv2.createBackgroundSubtractorMOG2(history=200, detectShadows=False)
        h, w = frame.shape[:2]
        if w > _SCALE_WIDTH:
            frame = cv2.resize(frame, (_SCALE_WIDTH, max(1, h * _SCALE_WIDTH // w)))
        mask = self._sub.apply(frame)
        self._frames += 1
        if self._frames <= _WARMUP_FRAMES:
            return True
        return float((mask > 0).mean()) >= self.min_ratio


def gate_for_camera(row: Mapping[str, Any]) -> MotionGate:
    """A gate with the camera's own threshold from ``notes`` JSON, if set."""
    ratio: float | None = None
    notes = row["notes"] if "notes" in row.keys() else None
    if notes:
        try:
            value = json.loads(notes).get("motion_min_ratio")
            ratio = float(value) if value is not None else None
        except (ValueError, AttributeError):
            ratio = None  # free-text notes are not an error
    return MotionGate(min_ratio=ratio)
