"""Supervisor — workers, single DB writer, stats, graceful stop (S2.5).

Reads the active tier from the registry (``transport IN
('rtsp','replay')``, ``fps_tier='active'``, capped at
``SENTINEL_ACTIVE_CAMERAS``), never two workers on one camera, restarts
a dead worker with damping, refreshes the watchlist cache and the zones
every 10 s, writes ``data/worker_stats.json`` atomically every 10 s,
stops on SIGINT or a ``data/stop`` file, and kills only its own process
tree via psutil (review D9 — never every ffmpeg on the machine).

The **single writer thread** (``BEGIN IMMEDIATE``) is the only thing
that writes to the database from this process (decision F34).
"""

from __future__ import annotations

import json
import os
import queue
import signal
import sqlite3
import threading
import time
from concurrent.futures import Future
from pathlib import Path
from typing import Callable

import psutil

from backend.core import config
from backend.core import db as dbmod
from backend.core.logging_setup import setup
from backend.core.matcher import WatchlistCache
from ml.anpr.detect import Detector
from ml.anpr.ocr import PlateOcr
from ml.anpr.pipeline import AnprPipeline
from ml.worker import CameraWorker

log = setup("supervisor")

POLL_S = 10.0
_WRITE_RETRIES = 3


class DbWriter(threading.Thread):
    """The one writer. Awaited jobs return a Future; batches are
    best-effort. Each job runs in its own ``BEGIN IMMEDIATE`` transaction
    and a transient lock is retried."""

    _STOP = object()

    def __init__(self, db_path: Path) -> None:
        super().__init__(name="db-writer", daemon=True)
        self.db_path = db_path
        self._queue: queue.Queue = queue.Queue()

    def submit(self, fn: Callable[[sqlite3.Connection], object]) -> Future:
        future: Future = Future()
        self._queue.put((fn, future))
        return future

    def submit_batch(self, fn: Callable[[sqlite3.Connection], object]) -> None:
        """Best-effort: failures are logged in the writer, never raised."""
        self._queue.put((fn, None))

    def stop(self) -> None:
        self._queue.put(self._STOP)

    def run(self) -> None:
        con = dbmod.connect(self.db_path)
        con.isolation_level = None  # explicit BEGIN IMMEDIATE below
        try:
            while True:
                item = self._queue.get()
                if item is self._STOP:
                    break
                fn, future = item
                try:
                    result = self._run_job(con, fn)
                except Exception as exc:
                    if future is not None:
                        future.set_exception(exc)
                    else:
                        log.exception("best-effort batch failed")
                else:
                    if future is not None:
                        future.set_result(result)
        finally:
            con.close()

    def _run_job(self, con: sqlite3.Connection, fn):
        for attempt in range(_WRITE_RETRIES):
            try:
                con.execute("BEGIN IMMEDIATE")
                result = fn(con)
                con.execute("COMMIT")
                return result
            except sqlite3.OperationalError as exc:
                try:
                    con.execute("ROLLBACK")
                except sqlite3.OperationalError:
                    pass
                if "lock" in str(exc).lower() and attempt < _WRITE_RETRIES - 1:
                    log.warning("writer retry %d: %s", attempt + 1, exc)
                    time.sleep(0.2 * (attempt + 1))
                    continue
                raise
            except Exception:
                try:
                    con.execute("ROLLBACK")
                except sqlite3.OperationalError:
                    pass
                raise


class Supervisor:
    def __init__(self) -> None:
        self.stop_event = threading.Event()
        self.workers: dict[str, CameraWorker] = {}
        self.restarts = 0
        self._restart_counts: dict[str, int] = {}
        self._restart_not_before: dict[str, float] = {}
        self.started = time.monotonic()

    # A DB error in the poll loop must not kill the run; connections are
    # cheap and per-use so a locked read never pins the writer.
    def _active_rows(self, con: sqlite3.Connection) -> list[sqlite3.Row]:
        """The active tier under the SENTINEL_ACTIVE_CAMERAS cap: catalogue
        (sandbox) cameras first, then the manual/local ones, each group by
        camera_id — so the cap never trades a live sandbox camera for a
        stock feed, and cap+1 adds local01 (F55/F58). Ordering by id alone
        only did that while every catalogue id happened to sort before
        'local' (a grid with ids like 'road01' would lose to local01)."""
        return con.execute(
            "SELECT * FROM cameras WHERE transport IN ('rtsp', 'replay')"
            " AND fps_tier = 'active'"
            " ORDER BY CASE WHEN source = 'catalogue' THEN 0 ELSE 1 END,"
            " camera_id LIMIT ?",
            (config.active_cameras(),),
        ).fetchall()

    def _spawn(self, row: sqlite3.Row, writer: DbWriter, cache: WatchlistCache,
               detector: Detector, ocr: PlateOcr) -> None:
        camera_id = row["camera_id"]
        if camera_id in self.workers and self.workers[camera_id].is_alive():
            return  # never two workers on one camera
        pipeline = AnprPipeline(detector, ocr, camera_row=row)
        worker = CameraWorker(row, pipeline, writer, cache,
                              stop_event=threading.Event())
        self.workers[camera_id] = worker
        worker.start()
        log.info("worker started: %s (%s)", camera_id, row["transport"])

    def _write_stats(self) -> None:
        uptime = time.monotonic() - self.started
        totals = {"frames": 0, "inferred": 0, "motion_skipped": 0, "detections": 0,
                  "sightings": 0, "alerts": 0, "zone_events": 0, "restart_ticks": 0,
                  "ocr_attempts": 0, "full_reads": 0, "vehicle_tracks": 0}
        cameras = {}
        for camera_id, worker in self.workers.items():
            snap = dict(worker.stats)
            snap["alive"] = worker.is_alive()
            cameras[camera_id] = snap
            for key in totals:
                totals[key] += snap.get(key, 0)
        inferred = max(1, totals["inferred"] + totals["motion_skipped"])
        stats = {
            "written_at": dbmod.utcnow(),
            "uptime_s": round(uptime, 1),
            "restarts": self.restarts,
            "rss_mb": round(psutil.Process().memory_info().rss / 1e6, 1),
            "frames": totals["frames"],
            "fps_sustained": round(totals["frames"] / max(1.0, uptime), 2),
            "inferred": totals["inferred"],
            "motion_skip_rate": round(totals["motion_skipped"] / inferred, 3),
            "detections": totals["detections"],
            "detections_per_min": round(totals["detections"] / max(1.0, uptime / 60), 1),
            "sightings": totals["sightings"],
            "alerts": totals["alerts"],
            "zone_events": totals["zone_events"],
            "ocr_attempts": totals["ocr_attempts"],
            "full_reads": totals["full_reads"],
            "vehicle_tracks": totals["vehicle_tracks"],
            "plate_read_rate": round(
                totals["full_reads"] / max(1, totals["vehicle_tracks"]), 3),
            "cameras": cameras,
        }
        path = config.REPO_ROOT / "data" / "worker_stats.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(stats, indent=1), encoding="utf-8")
        os.replace(tmp, path)  # atomic

    def _check_workers(self, con, writer, cache, detector, ocr) -> None:
        rows = {r["camera_id"]: r for r in self._active_rows(con)}
        now = time.monotonic()
        for camera_id, row in rows.items():
            worker = self.workers.get(camera_id)
            if worker is not None and worker.is_alive():
                worker.update_zones(row["zones_json"])  # hot reload
                continue
            if worker is not None:  # died — restart with damping
                if now < self._restart_not_before.get(camera_id, 0.0):
                    continue
                n = self._restart_counts.get(camera_id, 0) + 1
                self._restart_counts[camera_id] = n
                self._restart_not_before[camera_id] = now + min(2.0 * (2 ** n), 60.0)
                self.restarts += 1
                log.warning("worker %s died; restart %d", camera_id, n)
            self._spawn(row, writer, cache, detector, ocr)

    def run(self) -> int:
        con = dbmod.connect()
        dbmod.migrate(con)
        writer = DbWriter(config.db_path())
        writer.start()
        detector = Detector()
        ocr = PlateOcr()
        cache = WatchlistCache()
        cache.refresh(con)

        signal.signal(signal.SIGINT, lambda *_: self.stop_event.set())
        signal.signal(signal.SIGTERM, lambda *_: self.stop_event.set())
        stop_file = config.REPO_ROOT / "data" / "stop"

        for row in self._active_rows(con):
            self._spawn(row, writer, cache, detector, ocr)
        if not self.workers:
            log.error("no active cameras (transport rtsp/replay, fps_tier=active)")

        last_poll = 0.0
        try:
            while not self.stop_event.is_set():
                time.sleep(0.5)
                if stop_file.exists():
                    log.info("data/stop found — stopping")
                    break
                if time.monotonic() - last_poll >= POLL_S:
                    last_poll = time.monotonic()
                    try:
                        cache.refresh(con)
                        self._check_workers(con, writer, cache, detector, ocr)
                        self._write_stats()
                    except Exception:
                        log.exception("poll failed; run continues")
        finally:
            log.info("stopping %d workers", len(self.workers))
            for worker in self.workers.values():
                worker.request_stop()
            for worker in self.workers.values():
                worker.join(timeout=10)
            writer.stop()
            writer.join(timeout=10)
            self._write_stats()
            # Safety net: kill only OUR children (never every ffmpeg — D9).
            for child in psutil.Process().children(recursive=True):
                try:
                    child.kill()
                except psutil.Error:
                    pass
            con.close()
            log.info("supervisor stopped after %.0f s, %d restarts",
                     time.monotonic() - self.started, self.restarts)
        return 0
