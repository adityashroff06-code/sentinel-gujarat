"""S4.1 measurement sampler (ml/tools/measure_run.py, F18) and the worker
counters that feed it (ocr_attempts, full_reads, vehicle_tracks).

Everything here runs without a live platform: the sampler is pointed at
this test process's own PID and synthetic stats files; the worker loop
runs against stub source/pipeline objects and a real per-test database.
The live 10-minute run itself is the laptop half of S4.1 (GATE B).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone

import numpy as np
import pytest

from backend.core.matcher import WatchlistCache
from ml.anpr.pipeline import CommittedRead, FrameResult
from ml.anpr.detect import Detection
from ml.anpr.track import Track
from ml.ingest.base import FrameTick
from ml.tools import measure_run
from ml.worker import CameraWorker


# ------------------------------------------------------------ window maths

def _snap(cameras: dict, uptime_s: float = 900.0, restarts: int = 0) -> dict:
    return {"uptime_s": uptime_s, "restarts": restarts, "cameras": cameras}


_BASE_CAM = {"frames": 100, "inferred": 60, "motion_skipped": 40,
             "detections": 500, "sightings": 5, "alerts": 1,
             "zone_events": 0, "restart_ticks": 0, "ocr_attempts": 30,
             "full_reads": 6, "vehicle_tracks": 50, "alive": True}


def test_window_rows_computes_rates_from_deltas_not_whole_run():
    base = _snap({"cam06": dict(_BASE_CAM)})
    final = _snap({"cam06": {**_BASE_CAM, "frames": 220, "inferred": 120,
                             "motion_skipped": 140, "detections": 1100,
                             "sightings": 12, "ocr_attempts": 75,
                             "full_reads": 18, "vehicle_tracks": 110}})
    rows = measure_run.window_rows(base, final, window_s=600.0)
    cam = rows["cam06"]
    assert cam["reliable"] is True
    assert cam["fps"] == 0.2                       # 120 frames / 600 s
    assert cam["boxes_per_min"] == 60.0            # 600 boxes / 10 min
    assert cam["vehicles_per_min"] == 6.0          # 60 new tracks / 10 min
    assert cam["motion_skip_rate"] == 0.625        # 100 / (60 + 100)
    assert cam["plate_read_rate"] == 0.2           # 12 full reads / 60 tracks
    assert cam["sightings"] == 7


def test_window_rows_flags_a_counter_regression_as_unreliable():
    # A worker respawn mid-window resets its counters (fresh CameraWorker):
    # deltas go negative. They are clamped and the row is flagged, never
    # quoted as measured.
    base = _snap({"cam06": dict(_BASE_CAM)})
    final = _snap({"cam06": {**_BASE_CAM, "frames": 10, "inferred": 5,
                             "motion_skipped": 5, "detections": 40,
                             "sightings": 0, "ocr_attempts": 2,
                             "full_reads": 0, "vehicle_tracks": 3}})
    rows = measure_run.window_rows(base, final, window_s=600.0)
    cam = rows["cam06"]
    assert cam["reliable"] is False
    assert cam["frames"] == 0 and cam["fps"] == 0.0    # clamped, not negative


def test_plate_read_rate_is_unmeasured_when_worker_predates_read_counters():
    # 25 Sep laptop: the running worker started before the merge that added
    # full_reads/vehicle_tracks, so its stats carry neither key. The window
    # maths used to default them to 0 and print "0.0 (0/0)" — a number no
    # code measured (root rule 8). It must say "unmeasured" instead.
    old = {k: v for k, v in _BASE_CAM.items()
           if k not in ("full_reads", "vehicle_tracks", "ocr_attempts")}
    rows = measure_run.window_rows(
        _snap({"cam06": dict(old)}),
        _snap({"cam06": {**old, "frames": 220, "detections": 1100}}), 600.0)
    cam = rows["cam06"]
    assert cam["read_counters"] is False
    assert cam["plate_read_rate"] is None and cam["vehicles_per_min"] is None
    assert cam["fps"] == 0.2                       # the other rows still measure
    result = _result_dict()
    result["cameras"] = rows
    result["totals"]["plate_read_rate"] = None
    md = measure_run.render_markdown(result)
    assert "unmeasured (worker predates the read counters)" in md
    assert "cam06 unmeasured" in md                # vehicles/camera/min row
    assert "0.0 (0/0)" not in md


def _result_dict(*, warmup_ok: bool = True, gpu_available: bool = False) -> dict:
    rows = measure_run.window_rows(
        _snap({"cam06": dict(_BASE_CAM)}),
        _snap({"cam06": {**_BASE_CAM, "frames": 220, "inferred": 120,
                         "motion_skipped": 140, "detections": 1100,
                         "sightings": 12, "ocr_attempts": 75, "full_reads": 18,
                         "vehicle_tracks": 110}}),
        600.0)
    totals = {k: sum(r[k] for r in rows.values())
              for k in ("frames", "detections", "sightings", "alerts",
                        "zone_events", "full_reads", "vehicle_tracks",
                        "ocr_attempts")}
    totals["plate_read_rate"] = 0.2
    return {"measured_at": "20260925-120000Z", "planned_minutes": 10.0,
            "window_s": 600.0, "sample_s": 5.0, "warmup_ok": warmup_ok,
            "warmup_uptime_s": 900.0, "warmup_min": 10.0, "crashed": False,
            "n_active": 1, "cameras": rows, "totals": totals,
            "restarts_in_window": 0,
            "peak_rss_mb": {"api": 210.0, "worker": 1187.0, "combined": 1397.0},
            "ram_trend": {"q1_mb": 1300.0, "q3_mb": 1390.0, "q4_mb": 1395.0,
                          "drift_pct": 7.3, "steady_pct": 0.4},
            "gpu": {"available": gpu_available,
                    "baseline_mib": 456 if gpu_available else None,
                    "peak_mib": 1234 if gpu_available else None},
            "samples": []}


def test_markdown_table_carries_every_key_measurement_row():
    md = measure_run.render_markdown(_result_dict(gpu_available=True))
    for label in ("Sustained inference fps per camera",
                  "Real detection rate (vehicles/camera/min)",
                  "Peak VRAM used", "Peak RAM used",
                  "Motion-skip rate per camera", "Plate-read rate"):
        assert label in md
    assert "[measured]" in md
    assert "1234 MiB" in md and "baseline before window: 456 MiB" in md
    assert "1397 MB" in md
    assert "WARM-UP NOT SATISFIED" not in md


def test_markdown_never_invents_a_gpu_number_and_marks_cold_runs():
    # Root rule 8: an unmeasured number is labelled, never invented.
    md = measure_run.render_markdown(
        _result_dict(warmup_ok=False, gpu_available=False))
    assert "unmeasured (nvidia-smi unavailable)" in md
    assert "WARM-UP NOT SATISFIED" in md


# ------------------------------------------------------------ main() paths

def _write_pidfile(path, api_pid: int, worker_pid: int) -> None:
    path.write_text(f"api {api_pid}\nworker {worker_pid}\n", encoding="utf-8")


def _write_stats(path, uptime_s: float) -> None:
    path.write_text(json.dumps(
        {**_snap({"cam06": dict(_BASE_CAM)}, uptime_s=uptime_s),
         "sightings": 5}), encoding="utf-8")


def test_main_refuses_without_a_running_platform(tmp_path):
    with pytest.raises(SystemExit, match="launch.py start"):
        measure_run.main(["--pidfile", str(tmp_path / "absent.txt")])


def test_main_refuses_a_cold_run_unless_allowed(tmp_path):
    pidfile, stats = tmp_path / "pids.txt", tmp_path / "stats.json"
    _write_pidfile(pidfile, os.getpid(), os.getpid())
    _write_stats(stats, uptime_s=120.0)          # 2 min < the 10 min warm-up
    with pytest.raises(SystemExit, match="warm-up not met"):
        measure_run.main(["--pidfile", str(pidfile), "--stats", str(stats),
                          "--out-dir", str(tmp_path / "m")])


def test_main_measures_writes_json_and_md_and_exits_0(tmp_path, monkeypatch,
                                                      capsys):
    pidfile, stats = tmp_path / "pids.txt", tmp_path / "stats.json"
    out = tmp_path / "measurements"
    _write_pidfile(pidfile, os.getpid(), os.getpid())
    _write_stats(stats, uptime_s=700.0)          # past the 10 min warm-up
    gpu_values = iter([100, 200, 150, 150, 150, 150])
    monkeypatch.setattr(measure_run, "_gpu_used_mib",
                        lambda: next(gpu_values, 150))
    rc = measure_run.main(["--minutes", "0.005", "--sample-s", "0.05",
                           "--pidfile", str(pidfile), "--stats", str(stats),
                           "--out-dir", str(out)])
    assert rc == 0
    files = sorted(out.iterdir())
    assert [p.suffix for p in files] == [".json", ".md"]
    result = json.loads(files[0].read_text(encoding="utf-8"))
    assert result["warmup_ok"] is True and result["crashed"] is False
    assert result["n_active"] == 1 and len(result["samples"]) >= 1
    assert result["peak_rss_mb"]["combined"] > 0      # this process's own RSS
    assert result["gpu"]["available"] is True
    assert result["gpu"]["peak_mib"] >= 200           # the max of the series
    assert "Peak RAM used" in capsys.readouterr().out # the table is printed


def test_main_exits_2_when_the_worker_dies_mid_window(tmp_path, monkeypatch):
    pidfile, stats = tmp_path / "pids.txt", tmp_path / "stats.json"
    out = tmp_path / "measurements"
    child = subprocess.Popen([sys.executable, "-c",
                              "import time; time.sleep(60)"])
    try:
        _write_pidfile(pidfile, os.getpid(), child.pid)
        _write_stats(stats, uptime_s=700.0)

        def _kill_then_wait(seconds: float) -> None:
            child.kill()
            child.wait()
        monkeypatch.setattr(measure_run, "_sleep", _kill_then_wait)
        rc = measure_run.main(["--minutes", "1", "--sample-s", "0.05",
                               "--pidfile", str(pidfile),
                               "--stats", str(stats), "--out-dir", str(out)])
        assert rc == 2
        result = json.loads(next(out.glob("*.json")).read_text("utf-8"))
        assert result["crashed"] is True   # partial evidence still on disk
    finally:
        if child.poll() is None:
            child.kill()


def test_main_refuses_stale_stats(tmp_path):
    pidfile, stats = tmp_path / "pids.txt", tmp_path / "stats.json"
    _write_pidfile(pidfile, os.getpid(), os.getpid())
    _write_stats(stats, uptime_s=700.0)
    old = stats.stat().st_mtime - 300
    os.utime(stats, (old, old))                  # supervisor looks wedged
    with pytest.raises(SystemExit, match="wedged"):
        measure_run.main(["--pidfile", str(pidfile), "--stats", str(stats)])


# ------------------------------------------- the worker counters (S4.1)

class _DoneFuture:
    def __init__(self, value):
        self._value = value

    def result(self, timeout=None):
        return self._value


class _SyncWriter:
    """Runs writer jobs synchronously on one connection (tests only)."""

    def __init__(self, con):
        self.con = con

    def submit(self, fn):
        return _DoneFuture(fn(self.con))

    def submit_batch(self, fn):
        fn(self.con)


class _StubSource:
    def __init__(self, ticks):
        self._ticks = ticks
        self.closed = False

    def frames(self):
        yield from self._ticks

    def close(self):
        self.closed = True


class _StubPipeline:
    def __init__(self, results):
        self._results = iter(results)

    def process(self, tick):
        return next(self._results)


def _tick(pts_ms: float) -> FrameTick:
    now = datetime.now(timezone.utc)
    return FrameTick(frame=np.zeros((8, 8, 3), np.uint8), pts_ms=pts_ms,
                     stream_time=now, wall_time=now, clock_source="replay")


def _track(tid: int, cls: str) -> Track:
    sup = "vehicle" if cls in ("car", "truck", "bus", "motorcycle") else cls
    return Track(id=tid, boxes=[(0.0, 0.0, 10.0, 10.0)], last_seen_pts=0.0,
                 superclass=sup, cls=cls)


def _det(cls: str) -> Detection:
    sup = "vehicle" if cls in ("car", "truck", "bus", "motorcycle") else cls
    return Detection(cls=cls, superclass=sup, conf=0.9,
                     xyxy=(0.0, 0.0, 10.0, 10.0))


def test_worker_counts_ocr_full_reads_and_unique_vehicle_tracks(con,
                                                                monkeypatch):
    from backend.core.db import utcnow
    con.execute("INSERT INTO cameras (camera_id, created_at, updated_at)"
                " VALUES ('testcam', ?, ?)", (utcnow(), utcnow()))
    con.commit()
    car, person, truck = _det("car"), _det("person"), _det("truck")
    results = [
        # frame 1: a car track and a person track appear; 2 OCR attempts.
        FrameResult(moving=True, detections=[car, person],
                    matches=[(_track(1, "car"), car),
                             (_track(2, "person"), person)],
                    ocr_attempts=2),
        # frame 2: the SAME car track again (id 1 — never recounted), one
        # NEW truck track, one full + one partial consensus committed.
        FrameResult(moving=True, detections=[car],
                    matches=[(_track(1, "car"), car),
                             (_track(3, "truck"), truck)],
                    committed=[
                        CommittedRead(track_id=1, plate="GJ01AB1234",
                                      plate_raw="GJ01AB1234", confidence=0.9,
                                      bbox=(0, 0, 10, 10), vehicle_class="car",
                                      kind="full", pts_ms=1000.0),
                        CommittedRead(track_id=3, plate="GJ05JB432",
                                      plate_raw="GJ05JB432", confidence=0.6,
                                      bbox=(0, 0, 10, 10),
                                      vehicle_class="truck",
                                      kind="partial", pts_ms=1000.0)],
                    ocr_attempts=1),
    ]
    source = _StubSource([_tick(0.0), _tick(1000.0)])
    monkeypatch.setattr("ml.worker.for_camera", lambda row: source)
    cache = WatchlistCache()
    cache.refresh(con)
    worker = CameraWorker({"camera_id": "testcam", "zones_json": None},
                          _StubPipeline(results), _SyncWriter(con), cache,
                          stop_event=threading.Event())
    worker.run()          # synchronously: the source exhausts, the loop ends

    assert worker.stats["ocr_attempts"] == 3
    assert worker.stats["full_reads"] == 1          # the partial never counts
    assert worker.stats["vehicle_tracks"] == 2      # ids 1 and 3; person id 2
    assert worker.stats["sightings"] == 2           # both committed reads land
    assert source.closed                            # capture released (rules)
