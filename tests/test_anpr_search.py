"""ANPR search lane (25 Sep): GET /api/sightings match modes,
GET /api/plates/suggest, and backend.tools.renormalise_plates.

The seeded demo scenario is the fixture: hero GJ01AB1234 on cam06, cam10,
cam09, the ambiguity near-miss GJ01A81234 on cam09, 20 background plates.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.core import db as dbmod
from backend.core import plates
from backend.core.matcher import WatchlistCache
from backend.tools import demo_seed, renormalise_plates
from ml.worker import process_read

VIEWER = {"X-API-Key": "test-viewer-key-not-a-secret"}
T0 = datetime(2026, 9, 23, 10, 0, 0, tzinfo=timezone.utc)
CAMERAS = [("cam06", "GSRTC"), ("cam09", "Police"), ("cam10", "Municipal")]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SENTINEL_DB", str(tmp_path / "anpr.db"))
    monkeypatch.setattr(demo_seed, "CROPS_ROOT", tmp_path / "crops")
    con = dbmod.connect()
    dbmod.migrate(con)
    now = dbmod.utcnow()
    for camera_id, dept in CAMERAS:
        con.execute("INSERT INTO cameras (camera_id, department, location_name,"
                    " created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (camera_id, dept, f"{camera_id} junction", now, now))
    demo_seed.inject(con, at=T0)
    con.close()
    from backend.app.main import app

    with TestClient(app, base_url="http://localhost") as c:
        yield c


def _read(plate: str, camera_id: str, seen: datetime, *, provenance: str = "live",
          clock: str = "rtsp-live", raw: str | None = None) -> None:
    con = dbmod.connect()
    try:
        cache = WatchlistCache()
        cache.refresh(con)
        process_read(con, cache, camera_id=camera_id, plate=plate, plate_raw=raw or plate,
                     confidence=0.9, seen_at=seen, wall_time=seen, clock_source=clock,
                     provenance=provenance, track_id=f"T-{plate}-{camera_id}")
    finally:
        con.close()


def _search(c: TestClient, **params) -> dict:
    r = c.get("/api/sightings", params=params, headers=VIEWER)
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------ match modes

def test_anpr_mode_finds_the_hero_from_an_ambiguity_typo(client) -> None:
    body = _search(client, plate="GJ01A81234", match="anpr")
    assert body["match"] == "anpr"
    assert body["query"] == {"plate": "GJ01A81234", "normalised": "GJ01A81234",
                             "canonical": "6J01A81234", "kind": "full",
                             "coerced": "GJ01AB1234"}
    rows = body["sightings"]
    assert body["total"] == body["count"] == 4
    # exact first (the stored near-miss), then the hero's three reads
    assert [(r["plate"], r["match_type"], r["match_distance"]) for r in rows] == [
        ("GJ01A81234", "exact", 0.0)] + [("GJ01AB1234", "ambiguity", 0.0)] * 3
    hero_times = [r["seen_at"] for r in rows[1:]]
    assert hero_times == sorted(hero_times, reverse=True)       # then newest first
    assert all(r["crop_url"] and r["crop_url"].startswith("/crops/demo/") for r in rows)


def test_anpr_mode_ranks_exact_then_ambiguity_then_fuzzy(client) -> None:
    _read("GJ01AB1235", "cam09", T0 + timedelta(minutes=30), provenance="demo", clock="demo")
    body = _search(client, plate="GJ01AB1234", match="anpr")
    assert body["total"] == 5
    types = [(r["match_type"], r["match_distance"]) for r in body["sightings"]]
    assert types == [("exact", 0.0)] * 3 + [("ambiguity", 0.0), ("fuzzy", 1.0)]
    assert body["sightings"][-1]["plate"] == "GJ01AB1235"


def test_contains_stays_the_default_and_unchanged(client) -> None:
    body = _search(client, plate="GJ01AB1234")
    assert body["match"] == "contains" and body["total"] == 3   # near-miss not contained
    assert {r["match_type"] for r in body["sightings"]} == {"exact"}
    body = _search(client, plate="GJ01")
    assert body["total"] == 5            # hero x3, near-miss, GJ01KT4821
    times = [r["seen_at"] for r in body["sightings"]]
    assert times == sorted(times, reverse=True)                  # newest first, as before
    assert {r["match_type"] for r in body["sightings"]} == {"contains"}
    assert all(r["match_distance"] is None for r in body["sightings"])
    # no plate: no match annotation at all
    body = _search(client)
    assert body["total"] == 24 and body["query"] is None
    assert {r["match_type"] for r in body["sightings"]} == {None}


def test_exact_mode_is_exact(client) -> None:
    body = _search(client, plate="gj01 a8 1234", match="exact")
    assert body["total"] == 1 and body["sightings"][0]["plate"] == "GJ01A81234"
    assert body["sightings"][0]["match_type"] == "exact"


def test_anpr_partial_query_matches_an_ocr_tolerant_fragment(client) -> None:
    # I<->1: "GJ0I" is a fragment of every GJ01... plate under the fold;
    # a partial query never fuzzy-matches (docs/api.md §6)
    body = _search(client, plate="GJ0I", match="anpr")
    assert body["query"]["kind"] is None and body["query"]["canonical"] == "6J01"
    assert body["total"] == 5
    assert {r["match_type"] for r in body["sightings"]} == {"contains"}
    assert _search(client, plate="GJ0I", match="contains")["total"] == 0


def test_anpr_total_honours_camera_and_pagination(client) -> None:
    body = _search(client, plate="GJ01AB1234", match="anpr", camera_id="cam09")
    assert body["total"] == 2 and [r["camera_id"] for r in body["sightings"]] == ["cam09"] * 2
    assert [r["match_type"] for r in body["sightings"]] == ["exact", "ambiguity"]
    page = _search(client, plate="GJ01AB1234", match="anpr", limit=2, offset=2)
    assert page["total"] == 4 and page["count"] == 2
    assert [r["match_type"] for r in page["sightings"]] == ["exact", "ambiguity"]
    assert _search(client, plate="GJ01AB1234", match="anpr", provenance="live")["total"] == 0


def test_anpr_mode_finds_the_observed_confusions_as_one_registration(client) -> None:
    # the 25 Sep live-DB pairs, stored as they were before coercion
    t = T0 + timedelta(hours=1)
    _read("6J23H1548", "cam06", t)
    _read("GJ23H1548", "cam10", t + timedelta(minutes=5))
    body = _search(client, plate="GJ23H1548", match="anpr")
    assert [(r["plate"], r["match_type"]) for r in body["sightings"]] == [
        ("GJ23H1548", "exact"), ("6J23H1548", "ambiguity")]


def test_bad_match_value_is_a_422(client) -> None:
    r = client.get("/api/sightings?plate=GJ01&match=soundex", headers=VIEWER)
    assert r.status_code == 422


# ------------------------------------------------------------------ suggest

def test_suggest_lists_demo_watchlist_and_live_plates(client) -> None:
    body = client.get("/api/plates/suggest?limit=3", headers=VIEWER).json()
    assert set(body) == {"demo", "watchlist", "top_live"}
    demo = body["demo"]
    assert len(demo) == 3
    assert demo[0] == {"plate": "GJ01AB1234", "reads": 3, "cameras": 3,
                       "last_seen": "2026-09-23T10:15:00+00:00", "provenance": "demo",
                       "on_watchlist": True}
    assert demo[1]["plate"] == "GJ01A81234" and demo[1]["on_watchlist"] is True
    assert demo[2]["on_watchlist"] is False and demo[2]["provenance"] == "demo"
    wl = body["watchlist"]
    assert wl[0]["plate"] == "GJ01AB1234" and wl[0]["reads"] == 4   # canonical: + near-miss
    assert wl[0]["provenance"] == "demo" and wl[0]["on_watchlist"] is True
    assert body["top_live"] == []

    t = T0 + timedelta(hours=2)
    _read("6J23H1548", "cam06", t)                          # OCR twin, pre-coercion
    _read("GJ23H1548", "cam10", t + timedelta(minutes=4))
    _read("GJ23H1548", "cam10", t + timedelta(minutes=9))
    _read("GJ05JB432", "cam06", t + timedelta(minutes=12))  # partial: never suggested
    top = client.get("/api/plates/suggest", headers=VIEWER).json()["top_live"]
    assert top == [{"plate": "GJ23H1548", "reads": 3, "cameras": 2,
                    "last_seen": (t + timedelta(minutes=9)).isoformat(),
                    "provenance": "live", "on_watchlist": False}]


def test_plate_queries_are_audited_with_the_plate(client) -> None:
    _search(client, plate="GJ01A81234", match="anpr")
    client.get("/api/plates/suggest", headers=VIEWER)
    con = dbmod.connect()
    try:
        rows = [dict(r) for r in con.execute("SELECT * FROM audit ORDER BY audit_id")]
    finally:
        con.close()
    search = [r for r in rows if r["action"] == "GET /api/sightings -> 200"]
    assert search and search[-1]["entity"] == "plate_search"
    assert search[-1]["entity_id"] == "GJ01A81234"
    assert json.loads(search[-1]["after_json"])["match"] == "anpr"
    assert any(r["action"] == "GET /api/plates/suggest -> 200" for r in rows)


def test_suggest_and_search_reject_anonymous(client) -> None:
    assert client.get("/api/plates/suggest").status_code == 401
    assert client.get("/api/sightings?plate=GJ01&match=anpr").status_code == 401


# ------------------------------------------------------ renormalise_plates

def _insert(con, plate: str, provenance: str, camera_id: str = "cam06",
            canonical: str | None = None, at: int = 0) -> int:
    seen = (T0 + timedelta(minutes=at)).isoformat()
    clock = {"live": "rtsp-live", "harvest": "harvest", "demo": "demo", "test": "replay"}
    cur = con.execute(
        "INSERT INTO sightings (plate, plate_raw, plate_canonical, confidence, camera_id,"
        " seen_at, wall_time, clock_source, provenance, created_at)"
        " VALUES (?, ?, ?, 0.9, ?, ?, ?, ?, ?, ?)",
        (plate, f"raw:{plate}", canonical if canonical is not None else plates.canonical(plate),
         camera_id, seen, seen, clock[provenance], provenance, dbmod.utcnow()))
    return int(cur.lastrowid)


@pytest.fixture()
def legacy_db(tmp_path):
    """The 25 Sep live-DB shape: OCR twins stored side by side."""
    path = tmp_path / "legacy.db"
    con = dbmod.connect(path)
    dbmod.migrate(con)
    now = dbmod.utcnow()
    con.execute("INSERT INTO cameras (camera_id, department, created_at, updated_at)"
                " VALUES ('cam06', 'GSRTC', ?, ?)", (now, now))
    ids = {
        "6J23H1548": _insert(con, "6J23H1548", "live", at=1),
        "GJ23H1548": _insert(con, "GJ23H1548", "live", at=2),
        "GJ1157924": _insert(con, "GJ1157924", "live", at=3),
        "GJ11S7924": _insert(con, "GJ11S7924", "live", at=4),
        "GJO3XH0407": _insert(con, "GJO3XH0407", "harvest", at=5),
        "partial": _insert(con, "GJ05JB432", "live", at=6),
        "demo": _insert(con, "GJ01A81234", "demo", at=7),
        "test": _insert(con, "6J23H1548", "test", at=8),
    }
    wl = con.execute("INSERT INTO watchlist (plate, plate_canonical, category, severity,"
                     " added_at) VALUES ('GJ23H1548', ?, 'suspect', 'low', ?)",
                     (plates.canonical("GJ23H1548"), now)).lastrowid
    con.execute("INSERT INTO alerts (alert_id, kind, sighting_id, watchlist_id, plate,"
                " plate_canonical, camera_id, severity, match_type, clock_source, fired_at)"
                " VALUES ('ALERT-1', 'watchlist', ?, ?, '6J23H1548', ?, 'cam06', 'low',"
                " 'ambiguity', 'rtsp-live', ?)",
                (ids["6J23H1548"], wl, plates.canonical("6J23H1548"), now))
    con.commit()
    yield path, con, ids
    con.close()


def test_renormalise_plans_only_live_and_harvest_confusions(legacy_db) -> None:
    _, con, _ = legacy_db
    changes = renormalise_plates.plan(con)
    assert [(c.old, c.new, c.rows) for c in changes] == [
        ("6J23H1548", "GJ23H1548", 1),        # observed
        ("GJ1157924", "GJ11S7924", 1),        # observed
        ("GJO3XH0407", "GJ03XH0407", 1),      # observed (harvest provenance)
    ]


def test_renormalise_dry_run_writes_nothing(legacy_db, capsys) -> None:
    path, con, _ = legacy_db
    before = [tuple(r) for r in con.execute("SELECT * FROM sightings ORDER BY sighting_id")]
    assert renormalise_plates.main(["--db", str(path)]) == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "6J23H1548" in out and "-> GJ23H1548" in out
    assert "distinct live/harvest plates: 6 before -> 4 after (2 merged" in out
    assert "untouched (never rewritten): demo=1, test=1" in out
    after = [tuple(r) for r in con.execute("SELECT * FROM sightings ORDER BY sighting_id")]
    assert after == before
    assert not (path.parent / "backup").exists()


def test_renormalise_apply_restores_the_observed_confusions(legacy_db, capsys) -> None:
    path, con, ids = legacy_db
    before = {r["sighting_id"]: dict(r) for r in con.execute("SELECT * FROM sightings")}
    assert renormalise_plates.main(["--db", str(path), "--apply"]) == 0
    out = capsys.readouterr().out
    assert "applied: 3 row(s), 1 alert(s)" in out
    assert list((path.parent / "backup").glob("legacy-pre-renormalise-*.db"))  # snapshot first

    after = {r["sighting_id"]: dict(r) for r in con.execute("SELECT * FROM sightings")}
    assert after[ids["6J23H1548"]]["plate"] == "GJ23H1548"
    assert after[ids["GJ1157924"]]["plate"] == "GJ11S7924"
    assert after[ids["GJO3XH0407"]]["plate"] == "GJ03XH0407"
    for sid, row in after.items():
        # plate_raw and plate_canonical never move; nothing else changes
        assert row["plate_raw"] == before[sid]["plate_raw"]
        assert row["plate_canonical"] == before[sid]["plate_canonical"]
        assert {k: v for k, v in row.items() if k != "plate"} == \
               {k: v for k, v in before[sid].items() if k != "plate"}
    # never demo/test, never a partial read
    assert after[ids["demo"]]["plate"] == "GJ01A81234"
    assert after[ids["test"]]["plate"] == "6J23H1548"
    assert after[ids["partial"]]["plate"] == "GJ05JB432"
    # the alert's plate copy follows its sighting
    assert con.execute("SELECT plate FROM alerts").fetchone()[0] == "GJ23H1548"
    # idempotent: a second run plans nothing
    assert renormalise_plates.plan(con) == []


def test_renormalise_refuses_when_the_stored_canonical_disagrees(legacy_db, capsys) -> None:
    path, con, _ = legacy_db
    _insert(con, "MHO1DE2432", "live", canonical="BROKEN", at=9)
    con.commit()
    snapshot = [tuple(r) for r in con.execute("SELECT * FROM sightings ORDER BY sighting_id")]
    with pytest.raises(renormalise_plates.CanonicalMismatch):
        renormalise_plates.plan(con)
    assert renormalise_plates.main(["--db", str(path), "--apply"]) == 1
    assert "REFUSING" in capsys.readouterr().err
    assert [tuple(r) for r in con.execute("SELECT * FROM sightings ORDER BY sighting_id")] \
        == snapshot
