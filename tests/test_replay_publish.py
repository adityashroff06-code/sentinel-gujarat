"""scripts/replay_publish.py — checksum discipline (task S2.2, decision F25):
the recorded SHA-256 is verified on every run and a tampered or unrecorded
binary is refused. Loaded by path, like scripts/doctor.py."""

from __future__ import annotations

import importlib.util
import re
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


# --- mediamtx's HLS server and the --register mode (the wall's stock feeds) --

REAL_YML = REPO_ROOT / "tools" / "mediamtx" / "mediamtx.yml"


def test_mediamtx_env_serves_hls_on_loopback_only_when_asked(rp):
    rtsp_only = rp.mediamtx_env(8554)
    assert rtsp_only["MTX_RTSPADDRESS"] == "127.0.0.1:8554"
    assert rtsp_only["MTX_HLS"] == "no"                 # the S2.2 harness shape
    assert "MTX_HLSADDRESS" not in rtsp_only

    env = rp.mediamtx_env(28554, hls_port=28888)
    assert env["MTX_RTSPADDRESS"] == "127.0.0.1:28554"
    assert env["MTX_HLS"] == "yes"
    assert env["MTX_HLSADDRESS"] == "127.0.0.1:28888"   # rule 11: loopback
    assert env["MTX_HLSVARIANT"] == "mpegts"
    assert env["MTX_HLSSEGMENTDURATION"] == "2s"
    assert env["MTX_HLSSEGMENTCOUNT"] == "7"
    assert env["MTX_HLSALWAYSREMUX"] == "no"            # muxed only when read
    for off in ("MTX_RTMP", "MTX_WEBRTC", "MTX_SRT", "MTX_API", "MTX_METRICS",
                "MTX_PPROF", "MTX_PLAYBACK", "MTX_MOQ"):
        assert env[off] == "no", off
    for key, value in env.items():                      # nothing on 0.0.0.0
        if key.endswith("ADDRESS"):
            assert value.startswith("127.0.0.1:"), key


@pytest.mark.skipif(not REAL_YML.exists(),
                    reason="mediamtx not fetched: python scripts/replay_publish.py --fetch")
def test_every_mtx_override_names_a_real_mediamtx_yml_key(rp):
    """An MTX_ variable with a typo is silently ignored by mediamtx - so
    each one must name a top-level key of the bundled (v1.21.1) config."""
    keys = {m.group(1).lower() for m in re.finditer(
        r"^([A-Za-z0-9]+):", REAL_YML.read_text(encoding="utf-8"), re.M)}
    for var in rp.mediamtx_env(8554, hls_port=8888):
        assert var.startswith("MTX_")
        assert var[4:].lower() in keys, var


def test_register_pairs_publish_what_exists_and_list_what_is_missing(rp, tmp_path):
    feeds = tmp_path / "feeds"
    feeds.mkdir()
    for name in ("local01", "local03"):
        (feeds / f"{name}.mp4").write_bytes(b"x")
    rows = [{"camera_id": f"local0{i}"} for i in (1, 2, 3)]
    pairs, missing = rp.register_pairs(rows, feeds)
    assert [n for n, _ in pairs] == ["local01", "local03"]
    assert pairs[0][1] == feeds / "local01.mp4"
    assert missing == ["local02"]
    with pytest.raises(SystemExit, match="B11"):
        rp.register_pairs([{"camera_id": "bad/id"}], feeds)


def test_run_register_refuses_when_no_feed_exists(rp, tmp_path, capsys):
    register = tmp_path / "local_feeds.csv"
    register.write_text("camera_id,clip\nlocal01,a.mp4\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="no register feed"):
        rp.run_register(register=register, feeds_dir=tmp_path / "none")
    assert "skip local01" in capsys.readouterr().out


def test_register_plan_is_looped_copy_mode_one_path_per_feed(rp):
    pairs = [("local02", Path("b.mp4")), ("local01", Path("a.mp4"))]
    plan = rp._many_plan(pairs, {}, port=8554, copy=True, loop=True)
    assert [name for name, _, _ in plan] == ["local01", "local02"]
    for name, offset, cmd in plan:
        assert offset == 0.0
        assert cmd[cmd.index("-c:v") + 1] == "copy"
        assert "-stream_loop" in cmd and "-re" in cmd
        assert cmd[-1] == f"rtsp://127.0.0.1:8554/stream/{name}"


class _FakePopen:
    def __init__(self, dies_at: float | None, clock: dict):
        self.dies_at, self.clock, self.returncode = dies_at, clock, None

    def poll(self):
        if self.dies_at is not None and self.clock["t"] >= self.dies_at:
            self.returncode = 15
        return self.returncode

    def kill(self):
        self.returncode = -9

    def wait(self, timeout=None):
        return self.returncode


def test_register_respawns_a_dead_publisher_once_its_backoff_is_due(
        rp, tmp_path, monkeypatch, capsys):
    """Regression (found in the 25 Sep end-to-end run): the respawn check
    popped the schedule even when it was not yet due, so a killed
    publisher was re-scheduled every 0.5 s forever and never respawned."""
    clock = {"t": 0.0, "ticks": 0}
    spawned: list[str] = []

    def spawn(cmd):
        name = cmd[-1].rsplit("/", 1)[-1]
        spawned.append(name)
        first_local01 = name == "local01" and spawned.count("local01") == 1
        return _FakePopen(1.0 if first_local01 else None, clock)

    def sleep(seconds):
        clock["t"] += seconds
        clock["ticks"] += 1
        if clock["ticks"] > 40:                     # 20 s of fake time
            raise KeyboardInterrupt

    monkeypatch.setattr(rp, "start_mediamtx",
                        lambda port, hls_port=None: _FakePopen(None, clock))
    monkeypatch.setattr(rp, "_spawn_publisher", spawn)
    monkeypatch.setattr(rp.time, "monotonic", lambda: clock["t"])
    monkeypatch.setattr(rp.time, "sleep", sleep)
    monkeypatch.setattr(rp.random, "uniform", lambda a, b: 1.0)
    pairs = []
    for name in ("local01", "local02"):
        path = tmp_path / f"{name}.mp4"
        path.write_bytes(b"x")
        pairs.append((name, path))

    assert rp.run_many(pairs, {}, 8554, copy=True, loop=True, restart=True,
                       hls_port=0) == 0
    assert spawned.count("local01") == 2            # died once, respawned once
    assert spawned.count("local02") == 1            # the others kept playing
    out = capsys.readouterr().out
    assert "publisher local01 exited rc=15; restart 1 in 2.0 s" in out
    assert out.count("publisher local01 respawned") == 1


def test_restart_delay_is_rule_7_backoff(rp):
    assert rp.restart_delay_s(1, 1.0) == 2.0
    assert rp.restart_delay_s(2, 1.0) == 4.0
    assert rp.restart_delay_s(9, 1.0) == 30.0            # capped
    assert rp.restart_delay_s(1, 0.5) == 1.0             # jitter scales it
    assert rp.restart_delay_s(9, 1.5) == 45.0            # cap x 1.5 max
