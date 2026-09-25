"""launch.py — mode dispatch, the stubs and the replay defaults (task S3.4).

Command-builder tests only: nothing here binds a port, spawns a process
or touches the real data/ directory. Loaded by path, like doctor.py.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "launch", REPO_ROOT / "launch.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def lp():
    return _load()


def test_unknown_mode_prints_usage_and_exits_2(lp, capsys):
    assert lp.main(["frobnicate"]) == 2
    out = capsys.readouterr().out
    assert "unknown mode" in out and "usage:" in out


def test_bare_invocation_prints_usage_and_exits_2(lp, capsys):
    assert lp.main([]) == 2
    assert "usage:" in capsys.readouterr().out


def test_extra_arguments_on_a_plain_mode_are_a_usage_error(lp, capsys):
    assert lp.main(["measure", "--now"]) == 2
    assert "takes no arguments" in capsys.readouterr().out


def test_measure_and_harvest_stubs_exit_0(lp, capsys):
    assert lp.main(["measure"]) == 0
    assert "built in S4.1" in capsys.readouterr().out

    assert lp.main(["harvest"]) == 0
    assert "cut in v2.5 (F54)" in capsys.readouterr().out


def test_default_replay_specs_skip_missing_feeds_and_loop(lp, tmp_path,
                                                          monkeypatch):
    feeds = tmp_path / "feeds"
    feeds.mkdir()
    for i in (1, 2, 4):                       # local03 deliberately absent
        (feeds / f"local{i:02d}.mp4").write_bytes(b"x")
    monkeypatch.setattr(lp, "FOOTAGE_FEEDS", feeds)

    specs = lp._default_replay_specs()
    names = [s.split("=", 1)[0] for s in specs if "=" in s]
    assert names == ["local01", "local02", "local04"]     # missing = skipped
    assert specs[-1] == "--loop"              # F58 wall feeds loop by default


def test_default_replay_specs_die_when_no_feed_exists(lp, tmp_path,
                                                      monkeypatch):
    monkeypatch.setattr(lp, "FOOTAGE_FEEDS", tmp_path / "empty")
    with pytest.raises(SystemExit):
        lp._default_replay_specs()


def test_replay_cmd_shells_replay_publish_many(lp):
    cmd = lp._replay_cmd(Path("venv-python"), ["local01=a.mp4", "--loop"])
    assert cmd[0] == "venv-python"
    assert cmd[1].endswith("replay_publish.py")
    assert cmd[2] == "--many"
    assert cmd[3:] == ["local01=a.mp4", "--loop"]


def test_req_hash_tracks_both_requirements_files(lp, tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("a==1\n", encoding="utf-8")
    (tmp_path / "requirements-dev.txt").write_text("b==2\n", encoding="utf-8")
    monkeypatch.setattr(lp, "ROOT", tmp_path)

    first = lp._req_hash()
    (tmp_path / "requirements-dev.txt").write_text("b==3\n", encoding="utf-8")
    assert lp._req_hash() != first            # editing dev pins re-runs pip


def test_read_pidfile_tolerates_names_and_bare_pids(lp, tmp_path):
    pidfile = tmp_path / "launcher_pids.txt"
    pidfile.write_text("api 123\nworker 456\n789\n\n", encoding="utf-8")
    assert lp._read_pidfile(pidfile) == {"api": 123, "worker": 456,
                                         "proc2": 789}
    assert lp._read_pidfile(tmp_path / "absent.txt") == {}
