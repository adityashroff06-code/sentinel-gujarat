"""Camera worker — one thread per active camera (task S2.5; F34).

``for_camera`` source → ANPR pipeline → ``record_sighting`` →
``find_match`` → ``create_alert`` → events. **All writes go through the
supervisor's single writer thread**: sightings and alerts are awaited
jobs (the sighting commits before the match runs, the alert before
anything broadcasts); object events are async batches, best-effort.
A DB error never ends a pull — log, skip the frame, continue. The
capture closes in ``finally``.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import cv2
import numpy as np

from backend.core import matcher
from backend.core.alerts import create_alert
from backend.core.config import REPO_ROOT
from backend.core.db import utcnow
from backend.core.logging_setup import setup
from backend.core.matcher import WatchlistCache
from ml.analytics.events import EventThrottle, insert_events, insert_zone_event, object_event_row
from ml.analytics.zones import ZoneMonitor, parse_zones
from ml.anpr.detect import superclass
from ml.anpr.pipeline import (
    PLATE_BOX_BGR, VEHICLE_BOX_BGR, AnprPipeline, CommittedRead, EvidenceJpeg,
)
from ml.anpr.sightings import record_sighting
from ml.ingest import for_camera

log = setup("worker")

# clock_source → provenance (decision F26)
PROVENANCE = {"rtsp-live": "live", "hls-vod": "harvest", "harvest": "harvest",
              "replay": "test", "demo": "demo"}
_JOB_TIMEOUT_S = 30.0

_IST = timezone(timedelta(hours=5, minutes=30), "IST")
_EVIDENCE_JPEG_QUALITY = 80
_CAPTION_H = 30


def _ist_label(fired_at: str) -> str:
    """The alert's stream-time instant rendered in IST for the caption."""
    parsed = datetime.fromisoformat(fired_at)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(_IST).strftime("%d %b %Y %H:%M:%S IST")


def _caption_bar(img: np.ndarray, text: str) -> np.ndarray:
    """Append a dark caption strip under *img*. Drawn with Pillow (already
    a pinned dependency — F66's demo crops) because cv2's Hershey fonts
    are ASCII-only and the caption uses '·' separators."""
    from PIL import Image, ImageDraw  # deferred: only a watchlist hit pays for it

    bar = Image.new("RGB", (img.shape[1], _CAPTION_H), (11, 15, 20))
    ImageDraw.Draw(bar).text((10, 7), text, fill=(230, 237, 245), font_size=15)
    return np.vstack([img, np.asarray(bar)[:, :, ::-1]])


def write_evidence(
    con: sqlite3.Connection,
    *,
    alert: Mapping[str, Any],
    camera_id: str,
    sighting_id: int,
    confidence: float,
    evidence: EvidenceJpeg,
) -> str:
    """Store a watchlist hit's full annotated frame (decision F73).

    Decodes the read's held JPEG, draws the vehicle box (red, 3 px) and
    the plate box (amber, 2 px) that belong to that frame, plus a caption
    bar, writes it to ``data/evidence/<cam>/<alert_id>.jpg``, records the
    written bytes' SHA-256 in an ``audit`` row (``action='evidence.frame'``)
    and points ``sightings.frame_path`` at the file. Runs inside the
    writer job that created the alert, which wraps it in a savepoint; if
    either statement fails the file is removed again, so a failure leaves
    neither a stray file nor a half-written row. **This is the only code
    path that writes a full frame.** Returns the relative path; raises on
    decode/encode/write failure.
    """
    img = cv2.imdecode(np.frombuffer(evidence.jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("evidence JPEG did not decode")
    s = evidence.scale
    if evidence.vehicle_xyxy is not None:
        x1, y1, x2, y2 = (int(v * s) for v in evidence.vehicle_xyxy)
        cv2.rectangle(img, (x1, y1), (x2, y2), VEHICLE_BOX_BGR, 3)
    if evidence.plate_bbox is not None:
        px, py, pw, ph = evidence.plate_bbox
        cv2.rectangle(img, (int(px * s), int(py * s)),
                      (int((px + pw) * s), int((py + ph) * s)), PLATE_BOX_BGR, 2)
    caption = " · ".join([
        str(alert["alert_id"]), str(alert["plate"] or "—"), str(alert["match_type"]),
        f"conf {confidence:.2f}", camera_id, _ist_label(alert["fired_at"]),
    ])
    img = _caption_bar(img, caption)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, _EVIDENCE_JPEG_QUALITY])
    if not ok:
        raise ValueError("evidence JPEG did not encode")
    data = buf.tobytes()
    rel = f"data/evidence/{camera_id}/{alert['alert_id']}.jpg"  # forward slashes
    path = REPO_ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    sha256 = hashlib.sha256(data).hexdigest()
    path.write_bytes(data)
    try:
        con.execute(
            "UPDATE sightings SET frame_path = ? WHERE sighting_id = ?", (rel, sighting_id))
        con.execute(
            "INSERT INTO audit (at, actor, role, action, entity, entity_id, after_json)"
            " VALUES (?, 'worker', NULL, 'evidence.frame', 'alert', ?, ?)",
            (utcnow(), alert["alert_id"],
             json.dumps({"path": rel, "sha256": sha256, "bytes": len(data)})),
        )
    except Exception:
        path.unlink(missing_ok=True)
        raise
    log.info("%s: evidence frame %s (%d bytes, sha256 %s…)",
             camera_id, rel, len(data), sha256[:12])
    return rel


def process_read(
    con: sqlite3.Connection,
    cache: WatchlistCache,
    *,
    camera_id: str,
    plate: str,
    plate_raw: str,
    confidence: float,
    seen_at: datetime,
    wall_time: datetime,
    clock_source: str,
    provenance: str,
    pts_ms: float | None = None,
    bbox_json: str | None = None,
    vehicle_class: str | None = None,
    track_id: str | None = None,
    crop=None,
) -> tuple[int, sqlite3.Row | None]:
    """Sighting → commit → watchlist match → alert → commit, in that order
    (persist-before-match, root CLAUDE.md §4). Returns
    ``(sighting_id, alert_row_or_None)``.

    The single-connection path, shared by tests and the demo seeder
    (S3.1a); the live worker runs the same two steps as writer jobs.
    """
    sighting_id, _ = record_sighting(
        con, camera_id=camera_id, plate=plate, plate_raw=plate_raw,
        confidence=confidence, seen_at=seen_at, wall_time=wall_time,
        clock_source=clock_source, provenance=provenance, pts_ms=pts_ms,
        bbox_json=bbox_json, vehicle_class=vehicle_class, track_id=track_id,
        crop=crop)
    con.commit()  # the sighting exists on disk before the match runs
    match = cache.find_match(plate)
    if match is None:
        return sighting_id, None
    wl_row, rule, distance = match
    if not matcher.alertable(rule):
        return sighting_id, None
    sighting = con.execute("SELECT * FROM sightings WHERE sighting_id = ?",
                           (sighting_id,)).fetchone()
    alert = create_alert(
        con, kind="watchlist", camera_id=camera_id, severity=wl_row["severity"],
        seen_at=seen_at, clock_source=clock_source, sighting=sighting,
        wl_row=wl_row, rule=rule, distance=distance)
    con.commit()
    return sighting_id, alert


class CameraWorker(threading.Thread):
    """Pulls one camera; every DB write goes through *writer* jobs."""

    def __init__(self, row: Mapping[str, Any], pipeline: AnprPipeline,
                 writer, cache: WatchlistCache,
                 stop_event: threading.Event) -> None:
        super().__init__(name=f"worker-{row['camera_id']}", daemon=True)
        self.row = dict(row)
        self.camera_id = str(row["camera_id"])
        self.pipeline = pipeline
        self.writer = writer
        self.cache = cache
        self.stop_event = stop_event
        self.source = None
        self.zones = ZoneMonitor(parse_zones(self.row.get("zones_json")))
        self.throttle = EventThrottle()
        self.stats: dict[str, float] = {
            "frames": 0, "inferred": 0, "motion_skipped": 0, "detections": 0,
            "sightings": 0, "alerts": 0, "zone_events": 0, "restart_ticks": 0,
            "ocr_attempts": 0, "full_reads": 0, "vehicle_tracks": 0,
        }
        self._stats_lock = threading.Lock()
        # Track ids are assigned in increasing order and never reused
        # (S2.3; the tracker's reset() keeps the counter), so a high-water
        # mark counts each vehicle track exactly once in O(1) memory —
        # S4.1's plate-read-rate denominator (full reads / vehicle tracks).
        self._max_vehicle_track = -1

    def update_zones(self, zones_json: str | None) -> None:
        """Hot reload from the supervisor poll (10 s)."""
        self.zones.set_zones(parse_zones(zones_json))

    def request_stop(self) -> None:
        self.stop_event.set()
        if self.source is not None:
            try:
                self.source.close()
            except Exception:
                log.exception("closing %s source", self.camera_id)

    def _await(self, fn: Callable[[sqlite3.Connection], Any]) -> Any:
        return self.writer.submit(fn).result(timeout=_JOB_TIMEOUT_S)

    def _handle_committed(self, read: CommittedRead, tick) -> None:
        provenance = PROVENANCE.get(tick.clock_source, "test")
        track_id = f"{self.camera_id}-{read.track_id}"
        bbox_json = json.dumps(list(read.bbox))
        sighting_id, inserted = self._await(lambda con: record_sighting(
            con, camera_id=self.camera_id, plate=read.plate,
            plate_raw=read.plate_raw, confidence=read.confidence,
            seen_at=tick.stream_time, wall_time=tick.wall_time,
            clock_source=tick.clock_source, provenance=provenance,
            pts_ms=read.pts_ms, bbox_json=bbox_json,
            vehicle_class=read.vehicle_class, track_id=track_id,
            crop=read.crop, vehicle_crop=read.vehicle_px))
        with self._stats_lock:
            self.stats["sightings"] += 1 if inserted else 0
        match = self.cache.find_match(read.plate)
        if match is None:
            return
        wl_row, rule, distance = match
        if not matcher.alertable(rule):
            log.info("%s: %s matched watchlist by %s — not alertable (F21)",
                     self.camera_id, read.plate, rule)
            return
        written: list[Path] = []
        try:
            alert = self._await(
                lambda con: self._alert_job(con, read, tick, sighting_id,
                                            wl_row, rule, distance, written))
        except TimeoutError:
            raise  # the job may still commit later: its frame stays
        except Exception:
            # the job — its COMMIT included — failed and rolled back, so a
            # frame it wrote now belongs to no alert (F73: none may exist)
            for path in written:
                path.unlink(missing_ok=True)
            raise
        if alert is not None:
            with self._stats_lock:
                self.stats["alerts"] += 1

    def _alert_job(self, con: sqlite3.Connection, read: CommittedRead, tick,
                   sighting_id: int, wl_row, rule: str, distance: float,
                   written: list[Path]):
        """One writer job: the alert commit, then the evidence frame (F73 —
        persist before you match, then evidence). Runs on the writer thread
        inside one BEGIN IMMEDIATE transaction; an evidence failure logs
        and continues — it never costs the alert. A frame it writes is
        appended to *written*, so the caller can remove it if the job's
        transaction later fails."""
        alert = create_alert(
            con, kind="watchlist", camera_id=self.camera_id,
            severity=wl_row["severity"], seen_at=tick.stream_time,
            clock_source=tick.clock_source,
            sighting=con.execute("SELECT * FROM sightings WHERE sighting_id = ?",
                                 (sighting_id,)).fetchone(),
            wl_row=wl_row, rule=rule, distance=distance)
        if alert is None:
            return None
        if read.evidence is None:
            log.warning("%s: %s fired with no frame held by its track — no evidence"
                        " frame stored", self.camera_id, alert["alert_id"])
            return alert
        # A savepoint, so a failure half-way through (frame_path set, audit
        # row not) rolls back to the committed alert alone.
        con.execute("SAVEPOINT evidence")
        try:
            rel = write_evidence(
                con, alert=alert, camera_id=self.camera_id,
                sighting_id=sighting_id, confidence=read.confidence,
                evidence=read.evidence)
            written.append(REPO_ROOT / rel)
        except Exception:
            con.execute("ROLLBACK TO SAVEPOINT evidence")
            log.exception("%s: evidence frame failed for %s — alert kept",
                          self.camera_id, alert["alert_id"])
        finally:
            con.execute("RELEASE SAVEPOINT evidence")
        return alert

    def _handle_zones(self, result, tick) -> None:
        h, w = tick.frame.shape[:2]
        provenance = PROVENANCE.get(tick.clock_source, "test")
        for track, det in result.matches:
            x1, y1, x2, y2 = det.xyxy
            foot = (((x1 + x2) / 2) / w, y2 / h)
            for hit in self.zones.update(track.id, foot):
                event = self._await(lambda con, hit=hit: insert_zone_event(
                    con, camera_id=self.camera_id, zone_id=hit.zone.zone_id,
                    event_type=hit.event_type, object_class=det.cls,
                    occurred_at=tick.stream_time, wall_time=tick.wall_time,
                    clock_source=tick.clock_source, provenance=provenance))
                with self._stats_lock:
                    self.stats["zone_events"] += 1
                if hit.zone.severity == "high":
                    self._await(lambda con, e=dict(event), hit=hit: create_alert(
                        con, kind="zone", camera_id=self.camera_id,
                        severity=hit.zone.severity, seen_at=tick.stream_time,
                        clock_source=tick.clock_source, event=e))

    def _handle_object_events(self, result, tick) -> None:
        provenance = PROVENANCE.get(tick.clock_source, "test")
        rows = [
            object_event_row(
                camera_id=self.camera_id, object_class=det.cls, confidence=det.conf,
                occurred_at=tick.stream_time, wall_time=tick.wall_time,
                clock_source=tick.clock_source, provenance=provenance,
                bbox_json=json.dumps(list(det.xyxy)))
            for det in result.detections
            if self.throttle.due(det.cls, tick.stream_time.timestamp())
        ]
        if rows:
            self.writer.submit_batch(lambda con: insert_events(con, rows))

    def run(self) -> None:
        try:
            self.source = for_camera(self.row)
            for tick in self.source.frames():
                if self.stop_event.is_set():
                    break
                try:
                    if tick.restart:
                        self.throttle.reset()
                        self.zones.reset()
                        with self._stats_lock:
                            self.stats["restart_ticks"] += 1
                    result = self.pipeline.process(tick)
                    new_vehicle_tracks = [
                        track.id for track, det in result.matches
                        if superclass(det.cls) == "vehicle"
                        and track.id > self._max_vehicle_track]
                    with self._stats_lock:
                        self.stats["frames"] += 1
                        self.stats["inferred" if result.moving else "motion_skipped"] += 1
                        self.stats["detections"] += len(result.detections)
                        self.stats["ocr_attempts"] += result.ocr_attempts
                        self.stats["full_reads"] += sum(
                            1 for read in result.committed if read.kind == "full")
                        if new_vehicle_tracks:
                            self.stats["vehicle_tracks"] += len(new_vehicle_tracks)
                            self._max_vehicle_track = max(new_vehicle_tracks)
                    for read in result.committed:
                        self._handle_committed(read, tick)
                    if result.moving:
                        self._handle_object_events(result, tick)
                        self._handle_zones(result, tick)
                except Exception:
                    # A frame is never worth the pull (guard each frame,
                    # not the loop — sandbox-findings §7).
                    log.exception("%s: frame skipped", self.camera_id)
        except Exception:
            log.exception("%s: source failed; worker exiting", self.camera_id)
        finally:
            if self.source is not None:
                try:
                    self.source.close()
                except Exception:
                    log.exception("%s: close failed", self.camera_id)
            log.info("%s: worker stopped (%s)", self.camera_id, self.stats)
