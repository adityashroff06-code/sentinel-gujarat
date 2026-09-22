"""RTSP frame source (task S2.2; decisions F44, F36; feed rules 1-9).

One ffmpeg process per camera is the single pull (root rule 2). It is
*teed*: sampled BGR frames on stdout for inference AND, when ``hls_dir``
is given, a stream-copied local HLS window for the Live Wall - the
operator watches exactly the pull the detector reads, with no second
connection to the camera.

Timing: the ``fps`` filter produces constant-frame-rate output from the
input PTS, so ``frame index / target_fps`` IS the output PTS;
``stream_time = wall_time = pull_start + pts``, ``clock_source =
"rtsp-live"`` (decision F13) - never the arrival time of the bytes.

The stall watchdog is **armed when the child is spawned, not at the
first frame** (decision F44: a pull that never delivers a first frame is
how cam07 and cam25 behaved), and the RTSP socket flag is ``-timeout``,
never ``-rw_timeout`` (F44, measured). A reader thread keeps only the
latest frame, so a slow pipeline never back-pressures the pull.

The credentialed URL exists only in memory; every log line that could
carry it passes through :func:`config.masked` at the call site.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, Optional

from backend.core import config
from backend.core.logging_setup import setup
from ml.ingest.base import HEALTHY_RESET_S, FrameSource, FrameTick, backoff_params

# RTSP socket timeout, microseconds (15 s). The flag is -timeout: measured,
# -rw_timeout has no effect on an RTSP connection (decision F44).
RTSP_SOCKET_TIMEOUT_US = "15000000"

# Indirection so tests can stub the backoff wait (as in ml.ingest.replay).
_sleep = time.sleep


class RtspSourceError(RuntimeError):
    """The pull could not be (re)opened within the allowed retries."""


def resolve_url(camera_id: str, template: str | None) -> str:
    """The camera's RTSP URL, built in memory only (feed-rules behaviour 2).

    A stored template may carry ``<email>``/``<password>`` placeholders
    (filled from the environment, percent-encoded) or be a plain local URL
    used as-is (docs/api.md section 1). With no template, the sandbox
    pattern applies: ``rtsp://<email>:<password>@<ip>:<port>/stream/<id>``.
    Never log or store the result unmasked.
    """
    email = urllib.parse.quote(config.email(), safe="")
    password = urllib.parse.quote(config.password(), safe="")
    if template:
        return template.replace("<email>", email).replace("<password>", password)
    return (
        f"rtsp://{email}:{password}@{config.stream_ip()}:{config.rtsp_port()}"
        f"/stream/{camera_id}"
    )


class RtspFrameSource(FrameSource):
    clock_source = "rtsp-live"

    def __init__(self, camera_id: str, url: str, fps: float | None = None,
                 hls_dir: "Path | str | None" = None,
                 size: tuple[int, int] | None = None,
                 max_retries: int | None = None,
                 stall_timeout_s: float | None = None) -> None:
        self.camera_id = camera_id
        self._url = url
        self.fps = float(fps if fps is not None else config.infer_fps())
        self.hls_dir = Path(hls_dir) if hls_dir else None
        self._size = size
        self.max_retries = max_retries
        self.stall_timeout_s = float(
            stall_timeout_s if stall_timeout_s is not None else config.stall_timeout_s()
        )
        self.log = setup(f"ingest.{camera_id}")
        self._proc: Optional[subprocess.Popen] = None
        self._stop = threading.Event()

    # -- process management -------------------------------------------------

    def _probe_size(self) -> tuple[int, int]:
        """``(width, height)`` probed at pull start - never trusted from the
        registry (a camera may be re-provisioned at another resolution)."""
        out = subprocess.run(
            [
                config.ffprobe(), "-v", "error", "-rtsp_transport", "tcp",
                "-timeout", RTSP_SOCKET_TIMEOUT_US, "-select_streams", "v:0",
                "-show_entries", "stream=width,height", "-of", "json", self._url,
            ],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode != 0:
            raise RuntimeError(config.masked((out.stderr or "").strip()[-200:] or "ffprobe failed"))
        stream = json.loads(out.stdout)["streams"][0]
        return int(stream["width"]), int(stream["height"])

    def _command(self) -> list[str]:
        cmd = [
            config.ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "warning",
            "-rtsp_transport", "tcp", "-timeout", RTSP_SOCKET_TIMEOUT_US,
            "-i", self._url,
            # branch 1: sampled raw frames for inference
            "-map", "0:v:0", "-an", "-vf", f"fps={self.fps}",
            "-pix_fmt", "bgr24", "-f", "rawvideo", "pipe:1",
        ]
        if self.hls_dir:
            self.hls_dir.mkdir(parents=True, exist_ok=True)
            self._clean_hls_dir()  # stale segments desync the relay
            # branch 2: stream-copied live window for the wall (no transcode)
            cmd += [
                "-map", "0:v:0", "-an", "-c:v", "copy", "-f", "hls",
                "-hls_time", "2", "-hls_list_size", "10",
                "-hls_flags", "delete_segments+omit_endlist+independent_segments",
                "-hls_segment_filename", str(self.hls_dir / "seg%06d.ts"),
                str(self.hls_dir / "index.m3u8"),
            ]
        return cmd

    def _clean_hls_dir(self) -> None:
        if not self.hls_dir or not self.hls_dir.exists():
            return
        for f in list(self.hls_dir.glob("*.ts")) + [self.hls_dir / "index.m3u8"]:
            try:
                f.unlink(missing_ok=True)
            except OSError as exc:  # a locked file is not fatal; log, go on
                self.log.debug("%s: tee cleanup: %s", self.camera_id, exc)

    def _drain_stderr(self, proc: subprocess.Popen) -> None:
        # Decoder warnings on join are never fatal (root rule 5): DEBUG.
        for line in iter(proc.stderr.readline, b""):
            self.log.debug("%s: ffmpeg: %s", self.camera_id,
                           config.masked(line.decode(errors="replace").rstrip()))

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
        if self.hls_dir is not None:  # tee directory cleaned on close (S2.2)
            shutil.rmtree(self.hls_dir, ignore_errors=True)

    # -- the generator ------------------------------------------------------

    def frames(self) -> Iterator[FrameTick]:
        import numpy as np

        attempt = 0
        pending_restart = False
        try:
            while not self._stop.is_set():
                try:
                    width, height = self._size or self._probe_size()
                    self._proc = subprocess.Popen(
                        self._command(), stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, bufsize=width * height * 3 * 4,
                    )
                except (subprocess.SubprocessError, OSError, RuntimeError,
                        KeyError, json.JSONDecodeError, ValueError) as exc:
                    base, delay = backoff_params(attempt)
                    self.log.warning(
                        "%s: rtsp open failed url=%s attempt=%d base=%ds"
                        " delay=%.1fs error=%s", self.camera_id,
                        config.masked(self._url), attempt + 1, int(base),
                        delay, config.masked(str(exc)),
                    )
                    attempt += 1
                    if self.max_retries is not None and attempt >= self.max_retries:
                        raise RtspSourceError(
                            f"{self.camera_id}: could not open after {attempt} attempts"
                        ) from exc
                    _sleep(delay)
                    continue
                self._size = (width, height)
                proc = self._proc
                threading.Thread(target=self._drain_stderr, args=(proc,),
                                 daemon=True).start()
                self.log.info(
                    "%s: pull started url=%s size=%dx%d fps=%.1f tee=%s",
                    self.camera_id, config.masked(self._url), width, height,
                    self.fps, self.hls_dir or "off",
                )

                frame_bytes = width * height * 3
                step_ms = 1000.0 / self.fps
                pull_start = datetime.now(timezone.utc)

                # Reader thread drains stdout at the stream's pace so ffmpeg
                # (and its HLS tee) never blocks on a slow consumer. Keeps
                # only the LATEST frame: a slow pipeline samples further, it
                # never builds a backlog and never lags live.
                latest: list = [None, -1]   # [frame, index]
                cond = threading.Condition()
                eof = threading.Event()

                def _reader(out=proc.stdout, h=height, w=width,
                            nbytes=frame_bytes) -> None:
                    i = 0
                    while True:
                        buf = out.read(nbytes)
                        if buf is None or len(buf) < nbytes:
                            break
                        fr = np.frombuffer(buf, np.uint8).reshape(h, w, 3)
                        with cond:
                            latest[0], latest[1] = fr, i
                            cond.notify()
                        i += 1
                    eof.set()
                    with cond:
                        cond.notify()

                threading.Thread(target=_reader, daemon=True).start()

                # Watchdog armed HERE - at spawn, not at the first frame
                # (decision F44).
                last_frame_mono = time.monotonic()
                healthy_since: Optional[float] = None
                last_idx = -1
                yielded = 0
                stalled = False

                while not self._stop.is_set():
                    with cond:
                        if latest[1] == last_idx and not eof.is_set():
                            cond.wait(timeout=0.5)
                        frame, idx = latest[0], latest[1]
                        ended = eof.is_set() and idx == last_idx
                    now_mono = time.monotonic()
                    if idx > last_idx:
                        last_idx = idx
                        last_frame_mono = now_mono
                        if healthy_since is None:
                            healthy_since = now_mono
                        elif now_mono - healthy_since > HEALTHY_RESET_S:
                            attempt = 0
                        pts_ms = idx * step_ms  # CFR output: index * period
                        instant = pull_start + timedelta(milliseconds=pts_ms)
                        yield FrameTick(
                            frame=frame, pts_ms=pts_ms, stream_time=instant,
                            wall_time=instant, clock_source=self.clock_source,
                            restart=pending_restart,
                        )
                        pending_restart = False
                        yielded += 1
                        continue
                    if ended:
                        break  # child exited (-timeout or stream end)
                    if now_mono - last_frame_mono > self.stall_timeout_s:
                        stalled = True
                        self.log.warning(
                            "%s: watchdog: no frame for %.0fs (stall timeout"
                            " %.0fs) - killing the pull", self.camera_id,
                            now_mono - last_frame_mono, self.stall_timeout_s,
                        )
                        break

                self._kill()
                if self._stop.is_set():
                    break
                base, delay = backoff_params(attempt)
                self.log.warning(
                    "%s: pull %s after %d frames attempt=%d base=%ds delay=%.1fs"
                    " - respawning", self.camera_id,
                    "killed by watchdog" if stalled else "ended", yielded,
                    attempt + 1, int(base), delay,
                )
                attempt += 1
                if self.max_retries is not None and attempt >= self.max_retries:
                    raise RtspSourceError(f"{self.camera_id}: pull kept dying")
                pending_restart = True  # reconnect: a discontinuity (rule 8)
                _sleep(delay)
        finally:
            self._kill()  # feed-rules behaviour 9: always release
