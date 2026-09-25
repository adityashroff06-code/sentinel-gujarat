"""scripts/replay_publish.py — checksum discipline (task S2.2, decision F25):
the recorded SHA-256 is verified on every run and a tampered or unrecorded
binary is refused. Loaded by path, like scripts/doctor.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "replay_publish", REPO_ROOT / "scripts" / "replay_publish.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def rp(tmp_path, monkeypatch):
    module = _load()
    tools = tmp_path / "tools" / "mediamtx"
    tools.mkdir(parents=True)
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "TOOLS_DIR", tools)
    monkeypatch.setattr(module, "CHECKSUMS", tmp_path / "CHECKSUMS.txt")
    return module


def test_verify_passes_a_recorded_zip_and_refuses_a_tampered_one(rp):
    zip_path = rp.TOOLS_DIR / "mediamtx_v1.0.0_windows_amd64.zip"
    zip_path.write_bytes(b"payload")
    rp.CHECKSUMS.write_text(
        "# comment line\n"
        f"{rp.sha256_file(zip_path)}  https://example/v1.0.0  "
        f"tools/mediamtx/{zip_path.name}\n",
        encoding="utf-8",
    )
    assert rp.verify_zip() == zip_path         # intact: passes

    zip_path.write_bytes(b"tampered!")
    with pytest.raises(SystemExit, match="mismatch"):
        rp.verify_zip()                        # altered: refused


def test_verify_demands_a_fetch_and_a_recorded_entry(rp):
    with pytest.raises(SystemExit, match="not fetched"):
        rp.verify_zip()                        # no zip at all

    zip_path = rp.TOOLS_DIR / "mediamtx_v1.0.0_windows_amd64.zip"
    zip_path.write_bytes(b"payload")
    with pytest.raises(SystemExit, match="no CHECKSUMS.txt entry"):
        rp.verify_zip()                        # zip present, never recorded


def test_publish_command_reencodes_by_default_and_copies_on_request(rp):
    default = rp._publish_cmd("clip.mp4", "local01", 8554)
    assert "libx264" in default and "-g" in default          # 2 s GOP forced
    assert default[-1] == "rtsp://127.0.0.1:8554/stream/local01"

    copied = rp._publish_cmd("clip.mp4", "local01", 8554, copy=True)
    i = copied.index("-c:v")
    assert copied[i + 1] == "copy" and "libx264" not in copied
    assert copied[-1] == "rtsp://127.0.0.1:8554/stream/local01"


# --- the --many mode (task S3.4; F56/F58) — command-builder tests only, ----
# --- nothing here binds a port or spawns a process -------------------------

def test_publish_command_loops_by_default_and_once_through_on_request(rp):
    looped = rp._publish_cmd("clip.mp4", "local01", 8554)
    assert "-stream_loop" in looped                # S2.2 harness behaviour kept

    once = rp._publish_cmd("clip.mp4", "local01", 8554, loop=False)
    assert "-stream_loop" not in once              # F56: publish once through
    assert once[-1] == "rtsp://127.0.0.1:8554/stream/local01"


def test_parse_many_pairs_and_refusals(rp):
    pairs = rp._parse_many(["local01=a.mp4", "local02=feeds/b.mp4"])
    assert [name for name, _ in pairs] == ["local01", "local02"]
    assert str(pairs[1][1]).endswith("b.mp4")

    with pytest.raises(SystemExit, match="NAME=PATH"):
        rp._parse_many(["local01"])                # missing '='
    with pytest.raises(SystemExit, match="duplicate"):
        rp._parse_many(["a=x.mp4", "a=y.mp4"])
    with pytest.raises(SystemExit, match="B11"):
        rp._parse_many(["bad/name=x.mp4"])         # registry would refuse it


def test_parse_offsets_maps_real_gaps_and_refuses_junk(rp):
    offsets = rp._parse_offsets("local02=12.5,local03=40",
                                ["local01", "local02", "local03"])
    assert offsets == {"local02": 12.5, "local03": 40.0}
    assert rp._parse_offsets("", ["a"]) == {}

    with pytest.raises(SystemExit, match="not a --many feed"):
        rp._parse_offsets("nope=3", ["a"])
    with pytest.raises(SystemExit, match="negative"):
        rp._parse_offsets("a=-1", ["a"])
    with pytest.raises(SystemExit, match="NAME=SECONDS"):
        rp._parse_offsets("a", ["a"])
    with pytest.raises(SystemExit, match="not a number"):
        rp._parse_offsets("a=soon", ["a"])


def test_many_plan_defaults_copy_mode_once_through_offset_sorted(rp):
    pairs = [("local02", Path("b.mp4")), ("local01", Path("a.mp4"))]
    plan = rp._many_plan(pairs, {"local02": 30.0}, port=8554)

    assert [(name, off) for name, off, _ in plan] == [
        ("local01", 0.0), ("local02", 30.0)]       # started in offset order
    for _, _, cmd in plan:
        i = cmd.index("-c:v")
        assert cmd[i + 1] == "copy"                # F58: copy mode default
        assert "-stream_loop" not in cmd           # F56: once through default
    assert plan[1][2][-1] == "rtsp://127.0.0.1:8554/stream/local02"


def test_many_plan_reencode_and_loop_are_explicit_opt_ins(rp):
    plan = rp._many_plan([("wall", Path("w.mp4"))], copy=False, loop=True)
    cmd = plan[0][2]
    assert "libx264" in cmd and "-stream_loop" in cmd

    with pytest.raises(SystemExit, match="unknown feed"):
        rp._many_plan([("a", Path("a.mp4"))], {"b": 5.0})
