"""The local stock feeds (decision F58): the committed register, its upsert
into the registry, the one-time transcode argv and the worker's pick order.

Nothing here binds a port or spawns a process; the scripts are loaded by
path, like scripts/doctor.py.
"""

from __future__ import annotations

import csv
import importlib.util
import re
from pathlib import Path

import pytest

from backend.core import config
from backend.tools import seed_registry

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTER = REPO_ROOT / "data" / "local_feeds.csv"
DISCLOSURE = "(stock footage, seeded coordinates)"
# Gujarat's bounding box, generously rounded (Kutch to Valsad, Dang to Banaskantha)
GUJ_LAT, GUJ_LON = (20.0, 24.8), (68.0, 74.6)
DEPARTMENTS = {"Health", "Police", "GSRTC", "Panchayat", "Municipal"}


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(
        name, REPO_ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rows() -> list[dict[str, str]]:
    with REGISTER.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# --- the register itself ----------------------------------------------------

def test_register_has_28_unique_disclosed_rows_inside_gujarat():
    rows = _rows()
    assert len(rows) == 28
    ids = [r["camera_id"] for r in rows]
    assert len(set(ids)) == 28
    assert ids == [f"local{i:02d}" for i in range(1, 29)]
    for r in rows:
        assert re.fullmatch(r"[A-Za-z0-9_-]{1,64}", r["camera_id"])  # B11
        assert not r["camera_id"].startswith("cam")  # never a sandbox id
        lat, lon = float(r["lat"]), float(r["lon"])
        assert GUJ_LAT[0] <= lat <= GUJ_LAT[1], r["camera_id"]
        assert GUJ_LON[0] <= lon <= GUJ_LON[1], r["camera_id"]
        assert DISCLOSURE in r["location_name"], r["camera_id"]  # rule 12
        assert r["department"] in DEPARTMENTS
        assert r["fps_tier"] in {"active", "registered"}
        assert 0 <= float(r["bearing_deg"]) < 360
        assert float(r["fov_deg"]) > 0 and float(r["range_m"]) > 0
    # Every stock feed is view-only on the platform database (25 Sep
    # decision): a looped clip analysed there would store the same plates
    # again each loop as provenance='live' reads (root rule 12, F58).
    # Analysing a stock clip is a test-DB activity (--tier active there).
    assert not [r["camera_id"] for r in rows if r["fps_tier"] == "active"]


def test_every_reader_of_the_register_sees_the_same_rows():
    rows = _rows()
    assert seed_registry.load_local_feeds() == rows
    assert _load_script("prepare_feeds").load_register() == rows
    assert _load_script("replay_publish").load_register() == rows


# --- seed_registry.upsert_local_feeds ----------------------------------------

def _snapshot(con, where: str) -> list[tuple]:
    return [tuple(r) for r in con.execute(
        f"SELECT * FROM cameras WHERE {where} ORDER BY camera_id")]


def test_upsert_local_feeds_writes_every_register_row(con):
    assert seed_registry.upsert_local_feeds(con) == 28
    con.commit()
    rows = {r["camera_id"]: r for r in _rows()}
    got = {r["camera_id"]: r for r in con.execute(
        "SELECT * FROM cameras WHERE camera_id LIKE 'local%'")}
    assert set(got) == set(rows)
    for cid, reg in rows.items():
        row = got[cid]
        assert row["transport"] == "rtsp" and row["source"] == "manual"
        assert row["rtsp_url_template"] == f"rtsp://127.0.0.1:8554/stream/{cid}"
        assert row["department"] == reg["department"]
        assert row["location_name"] == reg["location_name"]
        assert DISCLOSURE in row["location_name"]
        assert (row["lat"], row["lon"]) == (float(reg["lat"]), float(reg["lon"]))
        assert row["bearing_deg"] == float(reg["bearing_deg"])
        assert row["fov_deg"] == float(reg["fov_deg"])
        assert row["range_m"] == float(reg["range_m"])
        assert row["fps_tier"] == reg["fps_tier"]
        assert row["ownership"] == "government"  # the local rows' value
    assert seed_registry.local_feed_count(con) == (28, 28)


def test_upsert_local_feeds_is_idempotent_and_keeps_ownership(con):
    seed_registry.upsert_local_feeds(con)
    con.execute("UPDATE cameras SET ownership = 'private', health = 'online'"
                " WHERE camera_id = 'local05'")
    con.commit()
    first = _snapshot(con, "camera_id LIKE 'local%'")

    seed_registry.upsert_local_feeds(con)
    con.commit()
    second = _snapshot(con, "camera_id LIKE 'local%'")
    assert len(second) == 28
    # only updated_at may move; everything else is the same row
    strip = lambda rows: [r[:-1] for r in rows]  # noqa: E731 - updated_at last
    assert strip(first) == strip(second)
    local05 = con.execute("SELECT ownership, health FROM cameras"
                          " WHERE camera_id = 'local05'").fetchone()
    assert tuple(local05) == ("private", "online")  # not the seeder's to reset


def test_upsert_local_feeds_restores_a_drifted_local_row(con):
    seed_registry.upsert_local_feeds(con)
    con.execute("UPDATE cameras SET fps_tier = 'active', lat = 0, lon = 0,"
                " rtsp_url_template = 'rtsp://elsewhere/x' WHERE camera_id = 'local01'")
    seed_registry.upsert_local_feeds(con)
    row = con.execute("SELECT * FROM cameras WHERE camera_id = 'local01'").fetchone()
    assert row["fps_tier"] == "registered" and row["lat"] == pytest.approx(23.2156)
    assert row["rtsp_url_template"] == "rtsp://127.0.0.1:8554/stream/local01"


def test_upsert_local_feeds_never_touches_sandbox_rows(con):
    seed_registry.upsert_catalogue(con)
    seed_registry.apply_seed(con)
    con.commit()
    before = _snapshot(con, "camera_id LIKE 'cam%'")
    assert len(before) == 30

    seed_registry.upsert_local_feeds(con)
    # even a register row that named a catalogue id may not overwrite it
    rogue = dict(_rows()[0], camera_id="cam06", fps_tier="registered",
                 location_name="rogue (stock footage, seeded coordinates)")
    assert seed_registry.upsert_local_feeds(con, [rogue]) == 0
    con.commit()
    assert _snapshot(con, "camera_id LIKE 'cam%'") == before
    total, active, departments, ok = seed_registry.summarise(con)
    assert (total, active, ok) == (58, 5, True)  # the 5 sandbox cameras only


def test_upsert_local_feeds_refuses_an_id_outside_b11(con):
    bad = dict(_rows()[0], camera_id="local/01")
    with pytest.raises(ValueError, match="B11"):
        seed_registry.upsert_local_feeds(con, [bad])


def test_seed_registry_main_reports_the_local_feed_count(monkeypatch, capsys,
                                                         tmp_path):
    monkeypatch.setenv("SENTINEL_DB", str(tmp_path / "seed.db"))
    monkeypatch.setattr("sys.argv", ["seed_registry"])
    assert seed_registry.main() == 0
    out = capsys.readouterr().out
    assert "28/28 local stock feeds" in out and "ACCEPTANCE: PASS" in out
    assert "58 rows, 5 active" in out
    assert seed_registry.main() == 0  # idempotent: same line again
    assert "58 rows, 5 active" in capsys.readouterr().out


# --- prepare_feeds.transcode_cmd --------------------------------------------

def test_transcode_cmd_forces_a_2s_gop_720_or_1080_no_audio_faststart():
    pf = _load_script("prepare_feeds")
    assert pf.feed_height("active") == 1080
    assert pf.feed_height("registered") == 720
    cmd = pf.transcode_cmd("ffmpeg", Path("raw.mp4"), Path("out.mp4"),
                           height=pf.feed_height("registered"), nvenc=False)
    assert cmd[0] == "ffmpeg" and cmd[-1] == "out.mp4"
    assert cmd[cmd.index("-g") + 1] == "60"            # 2 s at 30 fps
    assert cmd[cmd.index("-keyint_min") + 1] == "60"   # ... exactly 2 s
    assert cmd[cmd.index("-sc_threshold") + 1] == "0"  # no scene-cut extras
    vf = cmd[cmd.index("-vf") + 1]
    assert vf.startswith("fps=30,") and "720" in vf and "1080" not in vf
    assert "-an" in cmd
    assert cmd[cmd.index("-movflags") + 1] == "+faststart"
    assert cmd[cmd.index("-c:v") + 1] == "libx264"

    hd = pf.transcode_cmd("ffmpeg", Path("raw.mp4"), Path("out.mp4"),
                          height=pf.feed_height("active"), nvenc=True)
    assert "1080" in hd[hd.index("-vf") + 1]
    assert hd[hd.index("-c:v") + 1] == "h264_nvenc"
    assert hd[hd.index("-g") + 1] == "60"
    assert hd[hd.index("-force_key_frames") + 1] == "expr:gte(t,n_forced*2)"
    assert "-an" in hd and "+faststart" in hd


# --- the worker's pick under SENTINEL_ACTIVE_CAMERAS --------------------------

def _active_ids(con) -> list[str]:
    from ml.supervisor import Supervisor
    return [r["camera_id"] for r in Supervisor()._active_rows(con)]


def _seed_like_the_laptop(con) -> None:
    """Catalogue + seed + register, with the probe's verdict that the five
    seeded-active sandbox cameras answer RTSP."""
    seed_registry.upsert_catalogue(con)
    seed_registry.apply_seed(con)
    seed_registry.upsert_local_feeds(con)
    con.execute("UPDATE cameras SET transport = 'rtsp'"
                " WHERE source = 'catalogue' AND fps_tier = 'active'")
    con.commit()


def test_active_pick_keeps_the_five_sandbox_cameras_first(con, monkeypatch):
    _seed_like_the_laptop(con)
    monkeypatch.setenv("SENTINEL_ACTIVE_CAMERAS", "5")
    assert _active_ids(con) == ["cam06", "cam09", "cam26", "cam27", "cam28"]
    # the stock feeds are view-only: raising the cap never hands a worker
    # to a looped clip on the platform database
    for cap in ("6", "9", "40"):
        monkeypatch.setenv("SENTINEL_ACTIVE_CAMERAS", cap)
        assert _active_ids(con) == ["cam06", "cam09", "cam26", "cam27", "cam28"]


def test_active_pick_prefers_catalogue_cameras_whatever_their_ids(con,
                                                                 monkeypatch):
    """Regression: the pick was ORDER BY camera_id, so catalogue ids that
    sort after 'local' (a new grid's 'road01'...) lost their slots to the
    stock feeds under the cap."""
    now = "2026-09-25T00:00:00+00:00"
    for i in range(1, 6):
        con.execute(
            "INSERT INTO cameras (camera_id, transport, fps_tier, source,"
            " created_at, updated_at) VALUES (?, 'rtsp', 'active', 'catalogue', ?, ?)",
            (f"road{i:02d}", now, now))
    seed_registry.upsert_local_feeds(con)
    # the stock feeds are view-only; an operator-onboarded ACTIVE manual
    # camera (the S3.6 own-footage path) is what competes for the slots
    con.execute("UPDATE cameras SET fps_tier = 'active' WHERE camera_id = 'local01'")
    con.commit()
    monkeypatch.setenv("SENTINEL_ACTIVE_CAMERAS", "6")
    assert _active_ids(con) == ["road01", "road02", "road03", "road04",
                                "road05", "local01"]
    assert config.active_cameras() == 6
