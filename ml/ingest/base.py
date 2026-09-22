"""Frame-source foundations (docs/feed-rules.md; ml/CLAUDE.md; F36).

Shared by every source: the ``FrameTick`` shape, the PTS-dropping sampler
(never sleeps), the jittered backoff (logged as ``attempt``/``base``/
``delay`` on one line so tests assert on ``base``, never on jitter), and
the scene-cut detector for the sandbox's loop discontinuity (feed rule 8).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterator, Optional

import numpy as np

BACKOFF_CAP_S = 30.0
HEALTHY_RESET_S = 30.0


@dataclass
class FrameTick:
    """One sampled frame. ``stream_time`` is the in-memory name of what is
    stored as the ``seen_at`` column (docs/api.md §2); ``restart`` tells
    trackers and the motion gate to reset — it never touches the clock."""

    frame: np.ndarray
    pts_ms: float
    stream_time: datetime
    wall_time: datetime
    clock_source: str
    restart: bool = False


class FrameSource:
    """Abstract source: ``frames()`` yields FrameTicks; ``close()`` always
    releases the capture (feed rule 9)."""

    clock_source: str = "replay"

    def frames(self) -> Iterator[FrameTick]:  # pragma: no cover - interface
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def __enter__(self) -> "FrameSource":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class PtsSampler:
    """Sample to a target fps by **dropping on PTS**, never by sleeping
    (feed rule 4). ``due(pts_ms)`` is True for frames to keep."""

    def __init__(self, target_fps: float) -> None:
        self.interval_ms = 1000.0 / target_fps
        self._next_due_ms: Optional[float] = None

    def reset(self) -> None:
        self._next_due_ms = None

    def due(self, pts_ms: float) -> bool:
        if self._next_due_ms is None or pts_ms >= self._next_due_ms:
            base = pts_ms if self._next_due_ms is None else self._next_due_ms
            while base <= pts_ms:
                base += self.interval_ms
            self._next_due_ms = base
            return True
        return False


def backoff_params(attempt: int) -> tuple[float, float]:
    """``(base, delay)``: base = min(2·2ⁿ, 30) s, delay = base·random(0.5, 1.5)
    (root rule 7 / decision F36). Callers log attempt, base and delay."""
    base = min(2.0 * (2 ** attempt), BACKOFF_CAP_S)
    return base, base * random.uniform(0.5, 1.5)


class SceneCutDetector:
    """Mean absolute difference of consecutive down-scaled grey frames;
    above the threshold means a hard cut (the loop point) — feed rule 8."""

    def __init__(self, threshold: float = 48.0, stride: int = 8) -> None:
        self.threshold = threshold
        self.stride = stride
        self._previous: np.ndarray | None = None

    def reset(self) -> None:
        self._previous = None

    def is_cut(self, frame: np.ndarray) -> bool:
        small = frame[:: self.stride, :: self.stride]
        grey = small.mean(axis=2) if small.ndim == 3 else small.astype(float)
        previous, self._previous = self._previous, grey
        if previous is None or previous.shape != grey.shape:
            return False
        return float(np.abs(grey - previous).mean()) > self.threshold
