"""Replay frame source (task S2.1; decisions F20, F26, F36).

Reads a local file through ffmpeg (``-re -stream_loop -1``) at a target
fps. ``stream_time = wall_time = pull_start + pts`` — **continuous across
loops** (with ``-stream_loop`` the pipe never resets; pts here is
``index / fps`` by construction). Wrap detection uses the file's duration
from ffprobe: crossing ``k × duration`` emits one tick with
``restart=True`` (trackers and the motion gate reset; the clock does not).
Jittered backoff on process death; ``try/finally`` kill.

Deviation from the task's "reader thread" wording, with reason: a
keep-latest reader thread drops frames when the consumer is slow, which is
what RTSP needs (S2.2) but exactly wrong for replay — the soak and the
harness count every sampled frame. Replay therefore reads the pipe
directly; ffmpeg's ``-re`` paces delivery.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Iterator, Optional

from backend.core import config
from backend.core.logging_setup import setup
from ml.ingest.base import HEALTHY_RESET_S, FrameSource, FrameTick, backoff_params

# Indirection so tests can stub the backoff wait without touching the global
# time module (subprocess's wait-poll would spin on a no-op sleep).
_sleep = time.sleep


class ReplaySourceError(RuntimeError):
    """The replay file could not be opened after the allowed retries."""


def _probe_file(path: str) -> tuple[int, int, float]:
    """``(width, height, duration_s)`` of the file's first video stream."""
    out = subprocess.run(
        [
            config.ffprobe(), "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-show_entries",
            "format=duration", "-of", "json", path,
        ],
        capture_output=True, text=True, timeout=30, check=True,
    )
    data = json.loads(out.stdout)
    stream = data["streams"][0]
    return int(stream["width"]), int(stream["height"]), float(data["format"]["duration"])


class ReplayFrameSource(FrameSource):
    clock_source = "replay"

    def __init__(self, path: str, fps: float | None = None,
                 max_retries: int | None = None, name: str = "replay") -> None:
        self.path = str(path)
        self.fps = float(fps if fps is not None else config.infer_fps())
        self.max_retries = max_retries
        self.log = setup(f"ingest.{name}")
        self._proc: Optional[subprocess.Popen] = None
        self._stop = threading.Event()

    # -- process management -------------------------------------------------

    def _spawn(self) -> tuple[subprocess.Popen, int, int, float]:
        width, height, duration = _probe_file(self.path)
        cmd = [
            config.ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "warning",
            "-re", "-stream_loop", "-1", "-i", self.path,
            "-map", "0:v:0", "-an", "-vf", f"fps={self.fps}",
            "-pix_fmt", "bgr24", "-f", "rawvideo", "pipe:1",
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        threading.Thread(target=self._drain_stderr, args=(proc,), daemon=True).start()
        return proc, width, height, duration

    def _drain_stderr(self, proc: subprocess.Popen) -> None:
        # Decoder warnings are never fatal (root rule 5): DEBUG and move on.
        for line in iter(proc.stderr.readline, b""):
            self.log.debug("ffmpeg: %s", config.masked(line.decode(errors="replace").rstrip()))

    def _kill(self) -> None:
        proc, self._proc = self._proc, None
        if proc is not None:
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:  # pragma: no cover - best-effort cleanup
                pass

    def close(self) -> None:
        self._stop.set()
        self._kill()

    # -- the generator ------------------------------------------------------

    def frames(self) -> Iterator[FrameTick]:
        import numpy as np

        attempt = 0
        index = 0
        pull_start: Optional[datetime] = None
        last_wrap = 0
        pending_restart = False
        try:
            while not self._stop.is_set():
                try:
                    self._proc, width, height, duration = self._spawn()
                except (subprocess.SubprocessError, OSError, KeyError,
                        json.JSONDecodeError, ValueError) as exc:
                    base, delay = backoff_params(attempt)
                    self.log.warning(
                        "replay open failed attempt=%d base=%ds delay=%.1fs error=%s",
                        attempt + 1, int(base), delay, config.masked(str(exc)),
                    )
                    attempt += 1
                    if self.max_retries is not None and attempt >= self.max_retries:
                        raise ReplaySourceError(
                            f"could not open {self.path} after {attempt} attempts"
                        ) from exc
                    _sleep(delay)
                    continue

                if pull_start is None:
                    pull_start = datetime.now(timezone.utc)
                frame_bytes = width * height * 3
                healthy_since: Optional[float] = None

                while not self._stop.is_set():
                    chunk = self._proc.stdout.read(frame_bytes)
                    if chunk is None or len(chunk) < frame_bytes:
                        break  # child died or pipe closed -> respawn
                    if healthy_since is None:
                        healthy_since = time.monotonic()
                    elif time.monotonic() - healthy_since > HEALTHY_RESET_S:
                        attempt = 0

                    pts_ms = index * 1000.0 / self.fps
                    index += 1
                    wrap = int((pts_ms / 1000.0) // duration)
                    if wrap > last_wrap:
                        last_wrap = wrap
                        pending_restart = True

                    frame = np.frombuffer(chunk, dtype=np.uint8).reshape(height, width, 3)
                    instant = pull_start + timedelta(milliseconds=pts_ms)
                    yield FrameTick(
                        frame=frame, pts_ms=pts_ms, stream_time=instant,
                        wall_time=instant, clock_source=self.clock_source,
                        restart=pending_restart,
                    )
                    pending_restart = False

                if self._stop.is_set():
                    break
                self._kill()
                base, delay = backoff_params(attempt)
                self.log.warning(
                    "replay child died attempt=%d base=%ds delay=%.1fs — respawning",
                    attempt + 1, int(base), delay,
                )
                attempt += 1
                if self.max_retries is not None and attempt >= self.max_retries:
                    raise ReplaySourceError(f"{self.path}: child kept dying")
                pending_restart = True  # the file restarts: a discontinuity
                _sleep(delay)
        finally:
            self._kill()
