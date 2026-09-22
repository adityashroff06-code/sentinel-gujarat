"""S2.1 acceptance: the frame-source harness (reused by S2.2 with the RTSP
source parametrised in). Runs against the synthetic 60 s clip; ffmpeg's
``-re`` paces delivery, so these tests take real seconds by design."""

from __future__ import annotations

import logging
import re

import numpy as np
import pytest

from ml.ingest.base import PtsSampler, SceneCutDetector
from ml.ingest.replay import ReplayFrameSource, ReplaySourceError
from tests.fixtures.make_synthetic import ensure


@pytest.fixture(scope="module")
def clip():
    return str(ensure())


def _take(source, count=None, until_pts_ms=None):
    ticks = []
    for tick in source.frames():
        ticks.append(tick)
        if count is not None and len(ticks) >= count:
            break
        if until_pts_ms is not None and tick.pts_ms >= until_pts_ms:
            break
    return ticks


@pytest.mark.timeout(90)
def test_100_frames_strictly_monotonic(clip):
    with ReplayFrameSource(clip, fps=3) as source:
        ticks = _take(source, count=100)
    assert len(ticks) == 100
    times = [t.stream_time for t in ticks]
    assert all(b > a for a, b in zip(times, times[1:]))
    assert all(t.clock_source == "replay" for t in ticks)
    assert ticks[0].frame.shape == (360, 640, 3)


@pytest.mark.timeout(60)
def test_sampling_3fps_over_20s(clip):
    with ReplayFrameSource(clip, fps=3) as source:
        ticks = _take(source, until_pts_ms=20_000)
    in_window = [t for t in ticks if t.pts_ms < 20_000]
    assert 51 <= len(in_window) <= 69          # 60 ± 15 %
    span_s = (in_window[-1].pts_ms - in_window[0].pts_ms) / 1000
    assert 18 <= span_s <= 21                  # PTS span of ~20 s


@pytest.mark.timeout(200)
def test_loop_emits_restart_ticks_and_stays_monotonic(clip):
    with ReplayFrameSource(clip, fps=5) as source:
        ticks = _take(source, until_pts_ms=130_000)
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
