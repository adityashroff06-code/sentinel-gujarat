"""S7.2 acceptance (decision F73): a vehicle thumbnail on every read, a
full annotated frame ONLY for a watchlist hit — SHA-256 in the audit
trail. No GPU and no Paddle: the detector and OCR are stubs; the worker
path runs through the real ``DbWriter`` and ``write_evidence``."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import threading
from datetime import datetime, timezone

import numpy as np
import pytest
from fastapi.testclient import TestClient

import backend.app.main as main_mod
from backend.core.config import REPO_ROOT
from backend.core.db import utcnow
from backend.core.matcher import WatchlistCache
from backend.services.plate_search import search_sightings
from ml.anpr.detect import Detection
from ml.anpr.ocr import PlateRead
from ml.anpr.pipeline import AnprPipeline, CommittedRead, _encode_evidence
from ml.anpr.sightings import record_sighting
from ml.ingest.base import FrameTick
from ml.supervisor import DbWriter
from ml.worker import CameraWorker, write_evidence

VIEWER = {"X-API-Key": "test-viewer-key-not-a-secret"}

T0 = datetime(2026, 9, 27, 21, 0, 0, tzinfo=timezone.utc)


def _frame(w: int = 640, h: int = 360) -> np.ndarray:
    frame = np.full((h, w, 3), 32, dtype=np.uint8)
    frame[120:260, 200:420] = (60, 60, 160)  # a "vehicle"
    return frame


def _committed(evidence=True) -> CommittedRead:
    frame = _frame()
    return CommittedRead(
        track_id=1, plate="GJ01AB1234", plate_raw="GJ01AB1234", confidence=0.91,
        bbox=(260, 200, 120, 30), vehicle_class="car", kind="full", pts_ms=0.0,
        crop=frame[200:230, 260:380].copy(),
        vehicle_px=frame[120:260, 200:420].copy(),
        evidence=(_encode_evidence(frame, (260, 200, 120, 30), (200, 120, 420, 260))
                  if evidence else None),
        vehicle_xyxy=(200, 120, 420, 260),
    )


def _tick() -> FrameTick:
    return FrameTick(frame=_frame(), pts_ms=0.0, stream_time=T0, wall_time=T0,
                     clock_source="replay", restart=False)


@pytest.fixture()
def worker_env(con, tmp_path):
    """A real CameraWorker over a real DbWriter on the per-test database,
    with a unique camera; its crop/evidence folders are removed after."""
    camera_id = "evcam"
    con.execute("INSERT INTO cameras (camera_id, created_at, updated_at)"
                " VALUES (?, ?, ?)", (camera_id, utcnow(), utcnow()))
    con.commit()
    writer = DbWriter(tmp_path / "t.db")
    writer.start()
    cache = WatchlistCache()
    cache.refresh(con)
    worker = CameraWorker(
        row={"camera_id": camera_id, "transport": "replay"},
        pipeline=None, writer=writer, cache=cache,
        stop_event=threading.Event())
    try:
        yield worker, con, camera_id, cache
    finally:
        writer.stop()
        writer.join(timeout=10)
        shutil.rmtree(REPO_ROOT / "data" / "crops" / camera_id, ignore_errors=True)
        shutil.rmtree(REPO_ROOT / "data" / "evidence" / camera_id, ignore_errors=True)


def test_full_frame_written_only_for_watchlist_hits(worker_env) -> None:
    """F73's governing rule: a read that never matches leaves a vehicle
    thumbnail (``_v.jpg``) and NO file under data/evidence/, with
    ``frame_path`` NULL and no evidence audit row."""
    worker, con, camera_id, _ = worker_env
    worker._handle_committed(_committed(), _tick())

    row = con.execute("SELECT * FROM sightings").fetchone()
    assert row is not None and row["frame_path"] is None
    vehicle = REPO_ROOT / "data" / "crops" / camera_id / f"{row['sighting_id']}_v.jpg"
    assert vehicle.is_file(), "every read keeps a vehicle thumbnail"
    evidence_dir = REPO_ROOT / "data" / "evidence" / camera_id
    assert not evidence_dir.exists() or not any(evidence_dir.iterdir())
    assert con.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 0
    assert con.execute(
        "SELECT COUNT(*) FROM audit WHERE action = 'evidence.frame'").fetchone()[0] == 0


def test_hit_writes_one_evidence_file_whose_sha_matches_the_audit_row(worker_env) -> None:
    worker, con, camera_id, cache = worker_env
    con.execute(
        "INSERT INTO watchlist (plate, plate_canonical, category, severity, active, added_at)"
        " VALUES ('GJ01AB1234', '', 'stolen_vehicle', 'high', 1, ?)", (utcnow(),))
    con.commit()
    cache.refresh(con)

    worker._handle_committed(_committed(), _tick())

    alert = con.execute("SELECT * FROM alerts").fetchone()
    assert alert is not None and alert["kind"] == "watchlist"
    row = con.execute("SELECT * FROM sightings").fetchone()
    rel = row["frame_path"]
    assert rel == f"data/evidence/{camera_id}/{alert['alert_id']}.jpg"
    evidence_dir = REPO_ROOT / "data" / "evidence" / camera_id
    files = list(evidence_dir.iterdir())
    assert len(files) == 1, "exactly one evidence file per hit"
    audit = con.execute(
        "SELECT * FROM audit WHERE action = 'evidence.frame'"
        " AND entity = 'alert' AND entity_id = ?", (alert["alert_id"],)).fetchone()
    assert audit is not None
    after = json.loads(audit["after_json"])
    written = (REPO_ROOT / rel).read_bytes()
    assert after["sha256"] == hashlib.sha256(written).hexdigest()
    assert after["path"] == rel and after["bytes"] == len(written)


def test_evidence_write_failure_never_costs_the_alert(worker_env, monkeypatch) -> None:
    worker, con, camera_id, cache = worker_env
    con.execute(
        "INSERT INTO watchlist (plate, plate_canonical, category, severity, active, added_at)"
        " VALUES ('GJ01AB1234', '', 'stolen_vehicle', 'high', 1, ?)", (utcnow(),))
    con.commit()
    cache.refresh(con)
    import ml.worker as worker_mod

    def boom(*a, **kw):
        raise ValueError("synthetic evidence failure")

    monkeypatch.setattr(worker_mod, "write_evidence", boom)
    worker._handle_committed(_committed(), _tick())
    assert con.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 1
    assert con.execute("SELECT frame_path FROM sightings").fetchone()[0] is None


def test_partial_evidence_failure_leaves_no_file_and_no_frame_path(worker_env,
                                                                    monkeypatch) -> None:
    """Regression (S7.2 review): write_evidence wrote the file, set
    frame_path, then the audit insert failed — the blanket except kept the
    transaction going and committed an evidence_url with no sha (and the
    file). Now a savepoint rolls frame_path back and the file is removed;
    the alert stays."""
    worker, con, camera_id, cache = worker_env
    con.execute(
        "INSERT INTO watchlist (plate, plate_canonical, category, severity, active, added_at)"
        " VALUES ('GJ01AB1234', '', 'stolen_vehicle', 'high', 1, ?)", (utcnow(),))
    con.commit()
    cache.refresh(con)
    import ml.worker as worker_mod

    def audit_clock_fails():
        raise RuntimeError("synthetic failure between frame_path and the audit row")

    monkeypatch.setattr(worker_mod, "utcnow", audit_clock_fails)
    worker._handle_committed(_committed(), _tick())
    assert con.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 1
    assert con.execute("SELECT frame_path FROM sightings").fetchone()[0] is None
    assert con.execute(
        "SELECT COUNT(*) FROM audit WHERE action = 'evidence.frame'").fetchone()[0] == 0
    evidence_dir = REPO_ROOT / "data" / "evidence" / camera_id
    assert not evidence_dir.exists() or not any(evidence_dir.iterdir())


def test_dedupe_supplies_a_missing_vehicle_thumbnail(con) -> None:
    """Regression (S7.2 review): a read that deduped into a row written
    without a thumbnail returned before saving its own, so the row kept
    vehicle_url null for good."""
    con.execute("INSERT INTO cameras (camera_id, created_at, updated_at)"
                " VALUES ('evdedupe', ?, ?)", (utcnow(), utcnow()))
    con.commit()
    kw = dict(camera_id="evdedupe", plate="GJ01AB1234", plate_raw="GJ01AB1234",
              confidence=0.8, wall_time=T0, clock_source="replay", provenance="test")
    try:
        sid, inserted = record_sighting(con, seen_at=T0, **kw)
        assert inserted
        thumb = REPO_ROOT / "data" / "crops" / "evdedupe" / f"{sid}_v.jpg"
        assert not thumb.exists()
        sid2, inserted2 = record_sighting(con, seen_at=T0, vehicle_crop=_frame(200, 150), **kw)
        assert (sid2, inserted2) == (sid, False)
        assert thumb.is_file()
    finally:
        shutil.rmtree(REPO_ROOT / "data" / "crops" / "evdedupe", ignore_errors=True)


def test_removing_a_watchlist_entry_that_fired_an_alert_deactivates_it(tmp_path,
                                                                        monkeypatch) -> None:
    """Regression (28 Sep, found closing the S7.2 acceptance): DELETE
    /api/watchlist/{id} answered 500 for an entry that had fired an alert —
    alerts.watchlist_id references it and foreign keys are on. It is now
    deactivated (the alert keeps its row, the matcher ignores it), and
    listing the plate again reactivates it instead of a 409 (F78)."""
    from backend.core import db as dbmod

    monkeypatch.setenv("SENTINEL_DB", str(tmp_path / "wl.db"))
    monkeypatch.delenv("SENTINEL_PUBLIC_HOST", raising=False)
    con = dbmod.connect()
    dbmod.migrate(con)
    now = utcnow()
    con.execute("INSERT INTO cameras (camera_id, created_at, updated_at)"
                " VALUES ('wlcam', ?, ?)", (now, now))
    con.execute("INSERT INTO watchlist (plate, plate_canonical, category, severity,"
                " active, added_at) VALUES ('GJ01AB1234', '6J01A81234',"
                " 'stolen_vehicle', 'high', 1, ?)", (now,))
    con.execute("INSERT INTO watchlist (plate, plate_canonical, category, severity,"
                " active, added_at) VALUES ('MH02CD5678', 'MH02CD5678',"
                " 'suspect', 'low', 1, ?)", (now,))
    con.execute("INSERT INTO alerts (alert_id, kind, watchlist_id, camera_id, severity,"
                " clock_source, fired_at) VALUES ('ALERT-T-0001', 'watchlist', 1, 'wlcam',"
                " 'high', 'rtsp-live', ?)", (now,))
    con.commit()
    con.close()
    admin = {"X-API-Key": "test-admin-key-not-a-secret"}
    c = TestClient(main_mod.create_app(), base_url="http://localhost")

    r = c.request("DELETE", "/api/watchlist/1", headers=admin)
    assert r.status_code == 200, r.text
    assert r.json() == {"deleted": 1, "deactivated": True}
    listed = {w["plate"]: w for w in c.get("/api/watchlist", headers=admin).json()}
    assert listed["GJ01AB1234"]["active"] == 0
    cache = WatchlistCache()
    con = dbmod.connect()
    try:
        cache.refresh(con)
        assert cache.find_match("GJ01AB1234") is None, "a deactivated entry never matches"
        assert con.execute("SELECT watchlist_id FROM alerts").fetchone()[0] == 1
    finally:
        con.close()

    # an entry with no alerts is still deleted outright
    r = c.request("DELETE", "/api/watchlist/2", headers=admin)
    assert r.json() == {"deleted": 2, "deactivated": False}
    assert "MH02CD5678" not in {w["plate"] for w in c.get("/api/watchlist", headers=admin).json()}

    # listing the plate again reactivates the kept row
    r = c.post("/api/watchlist", headers=admin,
               json={"plate": "GJ01AB1234", "category": "suspect", "severity": "medium"})
    assert r.status_code == 201, r.text
    assert r.json()["watchlist_id"] == 1 and r.json()["active"] == 1
    assert r.json()["severity"] == "medium"
    # and an active duplicate is still a 409
    r = c.post("/api/watchlist", headers=admin,
               json={"plate": "GJ01AB1234", "category": "suspect", "severity": "medium"})
    assert r.status_code == 409


def test_evidence_route_needs_auth_and_refuses_traversal(tmp_path, monkeypatch) -> None:
    from backend.core import db as dbmod

    monkeypatch.setenv("SENTINEL_DB", str(tmp_path / "ev.db"))
    monkeypatch.delenv("SENTINEL_PUBLIC_HOST", raising=False)
    con = dbmod.connect()
    dbmod.migrate(con)
    con.close()
    c = TestClient(main_mod.create_app(), base_url="http://localhost")

    assert c.get("/evidence/x.jpg").status_code == 401           # no credential
    assert c.get("/evidence/x.jpg", headers=VIEWER).status_code == 404  # absent file
    # traversal (encoded, so the client does not normalise it away)
    assert c.get("/evidence/%2E%2E/sentinel.db", headers=VIEWER).status_code == 404
    assert c.get("/evidence/%2E%2E/%2E%2E/.env", headers=VIEWER).status_code == 404

    served = REPO_ROOT / "data" / "evidence" / "evroute" / "EV-TEST.jpg"
    served.parent.mkdir(parents=True, exist_ok=True)
    served.write_bytes(b"\xff\xd8\xff\xdbjpegish")
    try:
        r = c.get("/evidence/evroute/EV-TEST.jpg", headers=VIEWER)
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/jpeg"
        assert r.headers["cache-control"] == "private, no-store"
    finally:
        shutil.rmtree(served.parent, ignore_errors=True)


def test_media_routes_refuse_unc_and_device_paths_before_resolving(tmp_path,
                                                                   monkeypatch) -> None:
    """Regression (S7.2 security review): /evidence (and the older /crops)
    joined the request path onto the folder and called resolve() before the
    containment check. On Windows a UNC path discards the base, and resolve()
    opens it: an outbound SMB connection leaking the service's NTLM hash to
    any signed-in viewer's chosen host. The shape is now checked first, so
    resolve() never sees such a path."""
    import pathlib

    from backend.core import db as dbmod

    monkeypatch.setenv("SENTINEL_DB", str(tmp_path / "unc.db"))
    monkeypatch.delenv("SENTINEL_PUBLIC_HOST", raising=False)
    con = dbmod.connect()
    dbmod.migrate(con)
    con.close()
    c = TestClient(main_mod.create_app(), base_url="http://localhost")

    real_resolve = pathlib.Path.resolve
    resolved: list[str] = []

    def spy(self, *a, **kw):
        resolved.append(str(self))
        if str(self).startswith(("\\\\", "//")) or "attacker" in str(self):
            raise AssertionError(f"resolve() reached a hostile path: {self}")
        return real_resolve(self, *a, **kw)

    monkeypatch.setattr(pathlib.Path, "resolve", spy)
    hostile = [
        "%5C%5Cattacker%5Cshare%5Cx.jpg",      # \\attacker\share\x.jpg
        "%2F%2Fattacker%2Fshare%2Fx.jpg",      # //attacker/share/x.jpg
        "%2F%2F%3F%2FC%3A%2Fx.jpg",             # //?/C:/x.jpg (device path)
        "C%3A%2FWindows%2Fwin.ini",            # drive path
        "cam06%2Fx.jpg%3A%3A%24DATA",          # alternate data stream
        "cam06/..%2F..%2Fsentinel.jpg",        # traversal in the name part
        "a/b/c.jpg",                            # deeper than folder/name
    ]
    for route in ("/evidence/", "/crops/"):
        for path in hostile:
            r = c.get(route + path, headers=VIEWER)
            assert r.status_code == 404, (route, path, r.status_code)
    assert not any("attacker" in p for p in resolved)


def test_failed_alert_commit_removes_the_evidence_file(worker_env, monkeypatch) -> None:
    """Regression (S7.2 review): the frame is written inside the writer
    job; if the job's COMMIT then failed (disk full, I/O error, a lock on
    the last retry) the alert and audit row rolled back but the full frame
    stayed on disk with no watchlist hit on record."""
    from concurrent.futures import Future

    from backend.core import db as dbmod

    worker, con, camera_id, cache = worker_env
    con.execute(
        "INSERT INTO watchlist (plate, plate_canonical, category, severity, active, added_at)"
        " VALUES ('GJ01AB1234', '', 'stolen_vehicle', 'high', 1, ?)", (utcnow(),))
    con.commit()
    cache.refresh(con)
    real_submit = worker.writer.submit
    calls = {"n": 0}

    def submit(fn):
        calls["n"] += 1
        if calls["n"] == 1:
            return real_submit(fn)  # the sighting commits normally
        # the alert job runs, then its COMMIT fails and it rolls back
        future: Future = Future()
        job_con = dbmod.connect(worker.writer.db_path)
        job_con.isolation_level = None
        try:
            job_con.execute("BEGIN IMMEDIATE")
            fn(job_con)
            job_con.execute("ROLLBACK")
        finally:
            job_con.close()
        future.set_exception(sqlite3.OperationalError("disk I/O error"))
        return future

    monkeypatch.setattr(worker.writer, "submit", submit)
    with pytest.raises(sqlite3.OperationalError):
        worker._handle_committed(_committed(), _tick())
    assert con.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 0
    evidence_dir = REPO_ROOT / "data" / "evidence" / camera_id
    assert not evidence_dir.exists() or not any(evidence_dir.iterdir())


def test_alert_sha_is_read_only_for_alerts_with_a_frame(con) -> None:
    """Regression (S7.2 review): the audit lookup for evidence_sha256 ran a
    whole-table scan for EVERY alert row (7.3 s for 200 alerts against 30k
    audit rows). It now runs only when the alert's sighting has a frame —
    an evidence audit row with no frame_path behind it is not shown."""
    from backend.app.routes_analytics import _ALERT_SELECT, _alert_dict

    now = utcnow()
    con.execute("INSERT INTO cameras (camera_id, created_at, updated_at)"
                " VALUES ('shacam', ?, ?)", (now, now))
    sid, _ = record_sighting(
        con, camera_id="shacam", plate="GJ01AB1234", plate_raw="GJ01AB1234",
        confidence=0.9, seen_at=T0, wall_time=T0, clock_source="rtsp-live",
        provenance="live")
    for alert_id in ("ALERT-SHA-0001", "ALERT-SHA-0002"):
        con.execute(
            "INSERT INTO alerts (alert_id, kind, sighting_id, camera_id, severity,"
            " clock_source, fired_at) VALUES (?, 'watchlist', ?, 'shacam', 'high',"
            " 'rtsp-live', ?)", (alert_id, sid, now))
        con.execute(
            "INSERT INTO audit (at, actor, action, entity, entity_id, after_json)"
            " VALUES (?, 'worker', 'evidence.frame', 'alert', ?, ?)",
            (now, alert_id, json.dumps({"path": "x", "sha256": "ab" * 32, "bytes": 1})))
    con.commit()
    rows = [_alert_dict(r) for r in con.execute(_ALERT_SELECT)]
    assert all(r["evidence_url"] is None and r["evidence_sha256"] is None for r in rows)
    con.execute("UPDATE sightings SET frame_path = 'data/evidence/shacam/ALERT-SHA-0001.jpg'")
    con.commit()
    rows = {r["alert_id"]: _alert_dict(r) for r in con.execute(_ALERT_SELECT)}
    assert rows["ALERT-SHA-0001"]["evidence_sha256"] == "ab" * 32
    assert rows["ALERT-SHA-0001"]["evidence_url"] == "/evidence/shacam/ALERT-SHA-0001.jpg"


def test_vehicle_url_null_when_the_file_is_missing(con) -> None:
    con.execute("INSERT INTO cameras (camera_id, created_at, updated_at)"
                " VALUES ('evurl', ?, ?)", (utcnow(), utcnow()))
    con.commit()
    sid_bare, _ = record_sighting(
        con, camera_id="evurl", plate="GJ01AB1234", plate_raw="GJ01AB1234",
        confidence=0.9, seen_at=T0, wall_time=T0, clock_source="replay",
        provenance="test")
    sid_with, _ = record_sighting(
        con, camera_id="evurl", plate="MH02CD5678", plate_raw="MH02CD5678",
        confidence=0.9, seen_at=T0, wall_time=T0, clock_source="replay",
        provenance="test", vehicle_crop=_frame(200, 150))
    con.commit()
    try:
        body = search_sightings(
            con, plate=None, match="contains", camera_id="evurl", from_iso=None,
            to_iso=None, min_confidence=0.0, provenance=None, vehicle_class=None,
            limit=10, offset=0)
        by_id = {r["sighting_id"]: r for r in body["sightings"]}
        assert by_id[sid_bare]["vehicle_url"] is None
        assert by_id[sid_with]["vehicle_url"] == f"/crops/evurl/{sid_with}_v.jpg"
    finally:
        shutil.rmtree(REPO_ROOT / "data" / "crops" / "evurl", ignore_errors=True)


# --- memory bound: a track holds at most one frame JPEG ---------------------

class StubDetector:
    def __init__(self) -> None:
        self.boxes: list[Detection] = []

    def detect(self, frame, roi=None):
        return self.boxes


class StubOcr:
    def __init__(self) -> None:
        self.queue: list[list[PlateRead]] = []

    def read(self, crop, *, offset=(0, 0), frame_h=None):
        return self.queue.pop(0) if self.queue else []


class AlwaysMoving:
    def moving(self, frame) -> bool:
        return True

    def reset(self) -> None:
        pass


def _read(text: str, conf: float) -> PlateRead:
    return PlateRead(text=text, raw=text, conf=conf, bbox=(260, 200, 120, 30),
                     kind="full")


def _pipe_tick(pts_ms: float) -> FrameTick:
    return FrameTick(frame=_frame(), pts_ms=pts_ms, stream_time=T0, wall_time=T0,
                     clock_source="replay", restart=False)


def test_a_track_keeps_at_most_one_frame_jpeg() -> None:
    """The evidence JPEG lives only on the track's best read; a new best
    takes it over and the previous best drops it (F73's memory bound)."""
    det, ocr = StubDetector(), StubOcr()
    pipe = AnprPipeline(det, ocr, gate=AlwaysMoving())
    det.boxes = [Detection(cls="car", superclass="vehicle", conf=0.9,
                           xyxy=(200, 120, 420, 260))]
    # different spellings so no full consensus commits and OCR keeps going
    ocr.queue = [[_read("GJ01AB1234", 0.5)], [_read("GJ01AB1235", 0.9)],
                 [_read("GJ01AB1236", 0.7)]]
    for pts in (0.0, 1600.0, 3200.0):
        pipe.process(_pipe_tick(pts))
        track = next(iter(pipe.tracker.tracks.values()))
        holders = [r for r in track.ocr_reads if r.evidence is not None]
        assert len(holders) <= 1, "a track holds at most one frame JPEG"
    track = next(iter(pipe.tracker.tracks.values()))
    holders = [r for r in track.ocr_reads if r.evidence is not None]
    assert len(holders) == 1
    assert holders[0].conf == 0.9, "the highest-confidence read holds the frame"
    assert all(r.vehicle_px is not None for r in track.ocr_reads), \
        "every appended read carries its vehicle thumbnail"


def test_hit_whose_best_read_misspelt_the_plate_still_carries_evidence() -> None:
    """Regression (S7.2 review): the frame sits on the track's top-
    confidence read, but the commit backs onto the best read WITH the
    consensus text — when those differ the committed read carried no
    evidence and the hit stored no frame, silently."""
    det, ocr = StubDetector(), StubOcr()
    pipe = AnprPipeline(det, ocr, gate=AlwaysMoving())
    det.boxes = [Detection(cls="car", superclass="vehicle", conf=0.9,
                           xyxy=(200, 120, 420, 260))]
    # 0.9 misspelt (holds the frame); two agreeing 0.5/0.6 reads outvote it
    ocr.queue = [[_read("GJ01AB9999", 0.9)], [_read("GJ01AB1234", 0.5)],
                 [_read("GJ01AB1234", 0.6)]]
    committed = []
    for pts in (0.0, 1600.0, 3200.0):
        committed += pipe.process(_pipe_tick(pts)).committed
    assert [c.plate for c in committed] == ["GJ01AB1234"]
    evidence = committed[0].evidence
    assert evidence is not None and evidence.jpeg
    # the boxes travel with the frame they were measured on
    assert evidence.plate_bbox == (260, 200, 120, 30)
    assert evidence.vehicle_xyxy == (200, 120, 420, 260)


def test_committed_read_carries_the_evidence_fields() -> None:
    det, ocr = StubDetector(), StubOcr()
    pipe = AnprPipeline(det, ocr, gate=AlwaysMoving())
    det.boxes = [Detection(cls="car", superclass="vehicle", conf=0.9,
                           xyxy=(200, 120, 420, 260))]
    ocr.queue = [[_read("GJ01AB1234", 0.8)], [_read("GJ01AB1234", 0.9)]]
    pipe.process(_pipe_tick(0.0))
    result = pipe.process(_pipe_tick(1600.0))
    assert len(result.committed) == 1
    committed = result.committed[0]
    assert committed.vehicle_px is not None
    assert committed.evidence is not None and committed.evidence.jpeg
    assert committed.vehicle_xyxy == (200, 120, 420, 260)
