"""S2.1/S2.2 acceptance: the frame-source harness, parametrised over the
replay and RTSP sources (S2.2). The RTSP cases read a local mediamtx
(fetched by ``scripts/replay_publish.py --fetch``; skipped cleanly when it
is not) publishing the synthetic 60 s clip. ffmpeg's ``-re`` paces
delivery, so these tests take real seconds by design."""

from __future__ import annotations

import importlib.util
import logging
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

from backend.core import config
from ml.ingest import for_camera
from ml.ingest.base import PtsSampler, SceneCutDetector
from ml.ingest.replay import ReplayFrameSource, ReplaySourceError
from ml.ingest.rtsp import RtspFrameSource, RtspSourceError, resolve_url
from tests.fixtures.make_synthetic import ensure

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_RTSP_URL = "rtsp://127.0.0.1:8554/stream/test"


@pytest.fixture(scope="module")
def clip():
    return str(ensure())


def _load_replay_publish():
    spec = importlib.util.spec_from_file_location(
        "replay_publish", REPO_ROOT / "scripts" / "replay_publish.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _wait_stream_readable(url: str, timeout_s: float = 25.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        out = subprocess.run(
            [
                config.ffprobe(), "-v", "error", "-rtsp_transport", "tcp",
                "-timeout", "5000000", "-select_streams", "v:0",
                "-show_entries", "stream=codec_name", "-of", "json", url,
            ],
            capture_output=True, timeout=15,
        )
        if out.returncode == 0:
            return
        time.sleep(0.5)
    pytest.fail(f"published stream never became readable at {url}")


@pytest.fixture(scope="module")
def rtsp_url_local(clip):
    """mediamtx on 127.0.0.1:8554 with the synthetic clip loop-published
    at /stream/test — the S2.2 acceptance topology."""
    rp = _load_replay_publish()
    if not rp.mediamtx_exe().exists():
        pytest.skip("mediamtx not fetched: python scripts/replay_publish.py --fetch")
    server = rp.start_mediamtx(hls_port=0)  # RTSP only, as before HLS existed
    publisher = None
    try:
        publisher = rp.publish(clip, "test")
        _wait_stream_readable(LOCAL_RTSP_URL)
        yield LOCAL_RTSP_URL
    finally:
        for proc in (publisher, server):
            if proc is not None:
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except Exception:
                    pass


@pytest.fixture(params=["replay", "rtsp"])
def make_source(request, clip):
    """Factory returning a fps-parametrised source of the requested kind."""
    if request.param == "replay":
        return lambda fps: ReplayFrameSource(clip, fps=fps)
    url = request.getfixturevalue("rtsp_url_local")
    return lambda fps: RtspFrameSource("test", url, fps=fps)


def _take(source, count=None, until_pts_ms=None, timeout_s=110.0):
    """Collect ticks until a count/pts target. A wall-clock guard closes the
    source if it stops delivering, so a dead local stream fails the assertion
    cleanly instead of hanging past pytest-timeout (whose thread method can't
    interrupt a blocked pull on Windows). Keep timeout_s below the caller's
    @pytest.mark.timeout but above its real ``-re``-paced run time."""
    ticks = []
    stopper = threading.Timer(timeout_s, source.close)
    stopper.daemon = True
    stopper.start()
    try:
        for tick in source.frames():
            ticks.append(tick)
            if count is not None and len(ticks) >= count:
                break
            if until_pts_ms is not None and tick.pts_ms >= until_pts_ms:
                break
    finally:
        stopper.cancel()
    return ticks


# --- the shared harness (S2.1, parametrised by S2.2) -----------------------

@pytest.mark.timeout(120)
def test_100_frames_strictly_monotonic(make_source):
    source = make_source(5)
    with source:
        ticks = _take(source, count=100)
    assert len(ticks) == 100
    times = [t.stream_time for t in ticks]
    assert all(b > a for a, b in zip(times, times[1:]))
    assert all(t.clock_source == source.clock_source for t in ticks)
    assert ticks[0].frame.shape == (360, 640, 3)


@pytest.mark.timeout(120)
def test_sampling_3fps_over_20s(make_source):
    source = make_source(3)
    with source:
        ticks = _take(source, until_pts_ms=20_000)
    in_window = [t for t in ticks if t.pts_ms < 20_000]
    assert 51 <= len(in_window) <= 69          # 60 ± 15 %
    span_s = (in_window[-1].pts_ms - in_window[0].pts_ms) / 1000
    assert 18 <= span_s <= 21                  # PTS span of ~20 s


# --- replay-only cases (the wrap tick is replay-only: a re-encoded RTSP
# --- loop has continuous PTS) ----------------------------------------------

@pytest.mark.timeout(200)
def test_loop_emits_restart_ticks_and_stays_monotonic(clip):
    with ReplayFrameSource(clip, fps=5) as source:
        # ~130 s of PTS at 1x -re pacing needs a guard above its real runtime
        ticks = _take(source, until_pts_ms=130_000, timeout_s=180.0)
    restarts = sum(1 for t in ticks if t.restart)
    assert restarts >= 2                       # wraps at 60 s and 120 s
    times = [t.stream_time for t in ticks]
    assert all(b > a for a, b in zip(times, times[1:]))


def test_backoff_bases_double_with_jittered_delays(clip, monkeypatch, caplog):
    slept: list[float] = []
    monkeypatch.setattr("ml.ingest.replay._sleep", slept.append)
    caplog.set_level(logging.WARNING, logger="ingest.replay")
    source = ReplayFrameSource("/nonexistent/clip.mp4", fps=3, max_retries=3)
    with pytest.raises(ReplaySourceError):
        next(iter(source.frames()))
    lines = [r.getMessage() for r in caplog.records if "replay open failed" in r.getMessage()]
    bases = [int(re.search(r"base=(\d+)s", l).group(1)) for l in lines]
    delays = [float(re.search(r"delay=([\d.]+)s", l).group(1)) for l in lines]
    assert bases == [2, 4, 8]
    for base, delay in zip(bases, delays):
        assert 0.5 * base <= delay <= 1.5 * base
    assert len(slept) == 2                     # no sleep after the final attempt


@pytest.mark.timeout(90)
def test_frames_resume_after_child_killed_mid_read(clip):
    source = ReplayFrameSource(clip, fps=3)
    try:
        it = source.frames()
        before = [next(it) for _ in range(5)]
        source._proc.kill()                    # simulate the child dying
        after = [next(it) for _ in range(4)]
    finally:
        source.close()
    assert after[0].restart is True            # discontinuity signalled
    assert after[-1].stream_time > before[-1].stream_time


# --- RTSP-only cases (task S2.2) --------------------------------------------

def test_rtsp_backoff_doubles_and_credentials_never_reach_a_log(monkeypatch, caplog):
    """Root rule 1 / feed-rules behaviour 2: the masked URL appears in the
    logs, the raw credential never does — and the open-failure backoff
    matches the replay source's contract (base 2·2ⁿ capped, jittered)."""
    slept: list[float] = []
    monkeypatch.setattr(RtspFrameSource, "_wait_backoff",
                        lambda self, d: slept.append(d))
    caplog.set_level(logging.WARNING, logger="ingest.badcam")
    url = "rtsp://someone%40example.com:sekretpass@127.0.0.1:9/stream/none"
    source = RtspFrameSource("badcam", url, fps=3, max_retries=3)
    with pytest.raises(RtspSourceError):
        next(iter(source.frames()))
    lines = [r.getMessage() for r in caplog.records if "open failed" in r.getMessage()]
    bases = [int(re.search(r"base=(\d+)s", l).group(1)) for l in lines]
    delays = [float(re.search(r"delay=([\d.]+)s", l).group(1)) for l in lines]
    assert bases == [2, 4, 8]
    for base, delay in zip(bases, delays):
        assert 0.5 * base <= delay <= 1.5 * base
    assert len(slept) == 2
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert "sekretpass" not in joined                      # raw: never
    assert "rtsp://<email>:***@127.0.0.1:9" in joined      # masked: always


@pytest.mark.timeout(60)
def test_watchdog_kills_a_pull_that_never_delivers_a_frame(monkeypatch, caplog):
    """Decision F44: the watchdog is armed at spawn — a child that never
    writes a first frame is killed after the stall timeout, not waited on
    forever (how cam07 and cam25 behaved)."""
    monkeypatch.setattr(RtspFrameSource, "_wait_backoff", lambda self, d: None)
    caplog.set_level(logging.WARNING, logger="ingest.stallcam")
    source = RtspFrameSource(
        "stallcam", "rtsp://127.0.0.1:8554/stream/none", fps=3,
        size=(64, 48), max_retries=2, stall_timeout_s=1.0,
    )
    monkeypatch.setattr(
        source, "_command",
        lambda: [sys.executable, "-c", "import time; time.sleep(60)"],
    )
    with pytest.raises(RtspSourceError):
        next(iter(source.frames()))
    source.close()
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "watchdog: no frame" in text
    assert "killed by watchdog after 0 frames" in text


@pytest.mark.timeout(120)
def test_rtsp_signals_restart_on_reconnect_and_stays_monotonic(rtsp_url_local):
    """RTSP flags ``restart`` on a reconnect (the reliable discontinuity
    signal - in-stream loop-cut detection is intentionally not done here;
    see rtsp.py) and stream_time never steps backwards across it, even
    though the join-time GOP burst can run early ticks ahead of the wall
    clock."""
    source = RtspFrameSource("test", rtsp_url_local, fps=5)
    try:
        it = source.frames()
        before = [next(it) for _ in range(6)]
        source._kill()                         # force the pull to end -> reconnect
        after = [next(it) for _ in range(4)]
    finally:
        source.close()
    assert any(t.restart for t in after)       # reconnect signalled
    assert not any(t.restart for t in before[1:])  # no spurious mid-pull restarts
    times = [t.stream_time for t in before + after]
    assert all(b > a for a, b in zip(times, times[1:]))  # monotonic across reconnect


@pytest.mark.timeout(120)
def test_rtsp_tee_writes_a_bounded_playlist_and_close_cleans_it(rtsp_url_local, tmp_path):
    hls_dir = tmp_path / "hls" / "test"
    source = RtspFrameSource("test", rtsp_url_local, fps=3, hls_dir=hls_dir)
    try:
        _take(source, until_pts_ms=9_000)      # ~9 s: several 2 s segments
        playlist = hls_dir / "index.m3u8"
        assert playlist.exists()
        listed = sum(
            1 for line in playlist.read_text(encoding="utf-8").splitlines()
            if line.strip().endswith(".ts")
        )
        assert 1 <= listed <= 10               # -hls_list_size 10
        assert len(list(hls_dir.glob("*.ts"))) <= 25
    finally:
        source.close()
    # close() rmtrees best-effort; on Windows a just-killed ffmpeg's handle
    # can linger a moment, so re-attempt briefly rather than flake.
    import shutil as _shutil
    for _ in range(20):
        if not hls_dir.exists():
            break
        _shutil.rmtree(hls_dir, ignore_errors=True)
        time.sleep(0.1)
    assert not hls_dir.exists()                # tee dir cleaned on close


# --- URL resolution and dispatch (task S2.2) --------------------------------

def test_resolve_url_encodes_credentials_and_honours_templates(monkeypatch):
    monkeypatch.setenv("SENTINEL_EMAIL", "a@b.c")
    monkeypatch.setenv("SENTINEL_PASSWORD", "p w+x")
    expected_default = (
        f"rtsp://a%40b.c:p%20w%2Bx@{config.stream_ip()}:{config.rtsp_port()}"
        "/stream/cam01"
    )
    assert resolve_url("cam01", None) == expected_default
    gateway = f"rtsp://<email>:<password>@{config.stream_ip()}:{config.rtsp_port()}/stream/cam01"
    assert resolve_url("cam01", gateway) == expected_default
    plain = "rtsp://127.0.0.1:8554/stream/local01"     # local URL: as-is
    assert resolve_url("local01", plain) == plain


def test_worker_never_sends_sandbox_credentials_to_a_non_gateway_host(monkeypatch):
    """Regression (25 Sep review gate): resolve_url filled <email>/<password>
    into ANY template host, so a registered camera pointing at a host of
    its choosing would receive the organisers' credentials from the worker
    (root rule 1). Only the configured sandbox gateway gets them now; any
    other host - another IP, another port, a userinfo trick - is returned
    as-is, placeholders and all."""
    monkeypatch.setenv("SENTINEL_EMAIL", "a@b.c")
    monkeypatch.setenv("SENTINEL_PASSWORD", "secret")
    gw, port = config.stream_ip(), config.rtsp_port()
    for tpl in (
        "rtsp://<email>:<password>@10.0.0.5:8554/stream/cam01",
        f"rtsp://<email>:<password>@{gw}:9999/stream/cam01",
        f"rtsp://<email>:<password>@evil.example/{gw}:{port}/stream/cam01",
        f"rtsp://<email>:<password>@{gw}.evil.example:{port}/x",
        f"rtsp://<email>:<password>@{gw}:{port} @evil.example/x",
        "http://<email>:<password>@evil.example/x",
    ):
        out = resolve_url("cam77", tpl)
        assert "secret" not in out and "a%40b.c" not in out, tpl
        assert out == tpl


def test_for_camera_dispatches_on_transport(clip):
    rtsp_source = for_camera({"camera_id": "camX", "transport": "rtsp",
                              "rtsp_url_template": None})
    assert isinstance(rtsp_source, RtspFrameSource)
    assert rtsp_source.hls_dir == config.REPO_ROOT / "data" / "hls" / "camX"

    replay_source = for_camera({"camera_id": "rep01", "transport": "replay",
                                "rtsp_url_template": clip})
    assert isinstance(replay_source, ReplayFrameSource)
    assert replay_source.path == clip

    with pytest.raises(NotImplementedError):
        for_camera({"camera_id": "camY", "transport": "hls"})
    with pytest.raises(ValueError):
        for_camera({"camera_id": "camZ", "transport": "none"})


# --- primitives (S2.1, unchanged) -------------------------------------------

def test_scene_cut_detector_fires_on_hard_cut_only():
    detector = SceneCutDetector()
    black = np.zeros((360, 640, 3), dtype=np.uint8)
    white = np.full((360, 640, 3), 255, dtype=np.uint8)
    assert detector.is_cut(black) is False     # first frame: nothing to compare
    assert detector.is_cut(white) is True      # black -> white: a hard cut
    detector.reset()
    assert detector.is_cut(white) is False
    assert detector.is_cut(white) is False     # identical frames: no cut


def test_pts_sampler_drops_on_pts():
    sampler = PtsSampler(target_fps=3)         # interval ~333.3 ms
    assert sampler.due(0.0) is True
    assert sampler.due(100.0) is False
    assert sampler.due(334.0) is True
    assert sampler.due(400.0) is False
    assert sampler.due(2000.0) is True         # catches up after a gap
    assert sampler.due(2100.0) is False
