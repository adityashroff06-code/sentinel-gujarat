"""launch.py — mode dispatch, the stubs and the replay defaults (task S3.4).

Command-builder tests only: nothing here binds a port or touches the real
data/ directory, and the only processes spawned are two sleeping pythons
for the replay-pid guard. Loaded by path, like doctor.py.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
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
    assert lp.main(["status", "--now"]) == 2
    assert "takes no arguments" in capsys.readouterr().out


def test_harvest_stub_exits_0(lp, capsys):
    assert lp.main(["harvest"]) == 0
    assert "cut in v2.5 (F54)" in capsys.readouterr().out


def test_measure_cmd_shells_ml_tools_measure_run(lp):
    cmd = lp._measure_cmd(Path("venv-python"), ["--minutes", "10"])
    assert cmd == ["venv-python", "-m", "ml.tools.measure_run",
                   "--minutes", "10"]


def test_measure_requires_a_venv_then_a_running_platform(lp, tmp_path,
                                                         monkeypatch):
    monkeypatch.setattr(lp, "venv_python", lambda: None)
    with pytest.raises(SystemExit):
        lp.measure(["--minutes", "10"])          # no .venv yet

    monkeypatch.setattr(lp, "venv_python", lambda: Path("venv-python"))
    monkeypatch.setattr(lp, "PIDFILE", tmp_path / "absent.txt")
    with pytest.raises(SystemExit):
        lp.measure(["--minutes", "10"])          # platform not started


def test_measure_forwards_its_arguments_to_the_sampler(lp, tmp_path,
                                                       monkeypatch):
    pidfile = tmp_path / "launcher_pids.txt"
    pidfile.write_text("api 1\nworker 2\n", encoding="utf-8")
    monkeypatch.setattr(lp, "venv_python", lambda: Path("venv-python"))
    monkeypatch.setattr(lp, "PIDFILE", pidfile)
    seen: list[list[str]] = []
    monkeypatch.setattr(lp, "run", lambda cmd, cwd=None: seen.append(cmd) or 0)

    assert lp.main(["measure", "--minutes", "10", "--sample-s", "5"]) == 0
    assert seen == [["venv-python", "-m", "ml.tools.measure_run",
                     "--minutes", "10", "--sample-s", "5"]]


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


# --- the local stock feeds from one command (F58) ------------------------------
# Every process, port and pid below is faked: nothing is spawned or bound.

class _FakeProc:
    def __init__(self, pid: int = 4242, rc=None):
        self.pid, self.returncode = pid, rc

    def poll(self):
        return self.returncode


@pytest.fixture()
def sandbox(lp, tmp_path, monkeypatch):
    """launch.py pointed at a throw-away data/ with a 3-row register and
    local01 + local03 transcoded; mediamtx 'fetched'; no real sleeps."""
    data = tmp_path / "data"
    data.mkdir()
    register = data / "local_feeds.csv"
    register.write_text("camera_id,clip\nlocal01,a.mp4\nlocal02,b.mp4\n"
                        "local03,c.mp4\n", encoding="utf-8")
    feeds = tmp_path / "feeds"
    feeds.mkdir()
    for name in ("local01", "local03"):
        (feeds / f"{name}.mp4").write_bytes(b"x")
    mtx = tmp_path / "mediamtx.exe"
    mtx.write_bytes(b"")
    for attr, value in (("DATA", data), ("LOGS", data / "logs"),
                        ("REGISTER", register), ("MEDIAMTX_EXE", mtx),
                        ("PIDFILE", data / "launcher_pids.txt"),
                        ("REPLAY_PIDFILE", data / "replay_pids.txt"),
                        ("STOP_FILE", data / "stop")):
        monkeypatch.setattr(lp, attr, value)
    monkeypatch.setattr(lp, "_feeds_dir", lambda vp: feeds)
    monkeypatch.setattr(lp.time, "sleep", lambda s: None)
    # never DESCRIBE a real mediamtx (the platform's :8554) from a test
    monkeypatch.setattr(lp, "_rtsp_publishing", lambda name: False)
    return lp


def test_register_cmd_shells_replay_publish_register(lp):
    cmd = lp._register_cmd(Path("venv-python"))
    assert cmd[0] == "venv-python"
    assert cmd[1].endswith("replay_publish.py")
    assert cmd[2:] == ["--register"]


def test_replay_start_without_args_is_the_register(sandbox, capsys):
    cmd, names = sandbox._replay_plan(Path("venv-python"), [])
    assert cmd == sandbox._register_cmd(Path("venv-python"))
    assert names == ["local01", "local03"]            # missing local02 skipped
    out = capsys.readouterr().out
    assert "local02" in out and "missing" in out
    assert "LOOPED STOCK CLIPS" in out                # F56/F58 disclosure


def test_replay_start_dies_when_no_register_feed_exists(sandbox, monkeypatch,
                                                        tmp_path):
    monkeypatch.setattr(sandbox, "_feeds_dir", lambda vp: tmp_path / "empty")
    with pytest.raises(SystemExit):
        sandbox._replay_plan(Path("venv-python"), [])


def test_replay_start_stream_list_excludes_offset_values(sandbox):
    """Regression: replay-start printed 'r2=30' (an --offsets value) as a
    second rtsp://.../stream/r2 line - every NAME=... token counted."""
    cmd, names = sandbox._replay_plan(
        Path("venv-python"), ["r1=a.mp4", "r2=b.mp4", "--offsets", "r2=30"])
    assert cmd[2] == "--many" and names == ["r1", "r2"]


def test_start_feeds_spawns_the_register_publisher_and_records_it(
        sandbox, monkeypatch, capsys):
    spawned: list[list[str]] = []
    monkeypatch.setattr(sandbox, "_spawn_detached",
                        lambda args, log: spawned.append(args) or _FakeProc())
    busy = iter([False, True])        # RTSP port free before, bound after
    monkeypatch.setattr(sandbox, "_port_busy", lambda port: next(busy))
    described: list[str] = []
    monkeypatch.setattr(sandbox, "_rtsp_publishing",
                        lambda name: described.append(name) or True)

    sandbox.start_feeds(Path("venv-python"))
    assert spawned == [sandbox._register_cmd(Path("venv-python"))]
    assert sandbox.REPLAY_PIDFILE.read_text(encoding="utf-8") == "feeds 4242\n"
    assert described == ["local01", "local03"]    # counted, not assumed
    out = capsys.readouterr().out
    assert "2/3 feeds publishing" in out and "local02" in out


@pytest.mark.parametrize("breakage", ["no_register", "no_feed", "no_mediamtx"])
def test_start_feeds_skips_quietly_when_nothing_can_publish(
        sandbox, monkeypatch, tmp_path, breakage):
    if breakage == "no_register":
        sandbox.REGISTER.unlink()
    elif breakage == "no_feed":
        monkeypatch.setattr(sandbox, "_feeds_dir", lambda vp: tmp_path / "none")
    else:
        sandbox.MEDIAMTX_EXE.unlink()
    monkeypatch.setattr(sandbox, "_spawn_detached",
                        lambda *a: pytest.fail("nothing to publish"))
    sandbox.start_feeds(Path("venv-python"))      # never fails start
    assert not sandbox.REPLAY_PIDFILE.exists()


def test_start_feeds_keeps_a_running_publisher_and_drops_a_stale_record(
        sandbox, monkeypatch):
    sandbox.REPLAY_PIDFILE.write_text("replay 777\n", encoding="utf-8")
    monkeypatch.setattr(sandbox, "_alive_pids", lambda vp, pids: [777])
    monkeypatch.setattr(sandbox, "_spawn_detached",
                        lambda *a: pytest.fail("already publishing"))
    sandbox.start_feeds(Path("venv-python"))
    assert sandbox.REPLAY_PIDFILE.read_text(encoding="utf-8") == "replay 777\n"

    monkeypatch.setattr(sandbox, "_alive_pids", lambda vp, pids: [])
    monkeypatch.setattr(sandbox, "_spawn_detached", lambda a, log: _FakeProc(99))
    # the stale record is dropped first, so the port is free until the spawn
    monkeypatch.setattr(sandbox, "_port_busy",
                        lambda port: sandbox.REPLAY_PIDFILE.exists())
    monkeypatch.setattr(sandbox, "_rtsp_publishing", lambda name: True)
    sandbox.start_feeds(Path("venv-python"))
    assert sandbox.REPLAY_PIDFILE.read_text(encoding="utf-8") == "feeds 99\n"


def _sleeper(cwd: Path, *argv: str) -> subprocess.Popen:
    """A python that only sleeps; *argv* lands in its command line (after
    ``-c``, so it is never executed)."""
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)",
                             *argv], cwd=str(cwd))


def test_start_feeds_ignores_a_recorded_replay_pid_reused_by_another_process(
        sandbox, monkeypatch, tmp_path, capsys):
    """Regression (review, 25 Sep): _alive_pids asked only psutil.pid_exists,
    so a data/replay_pids.txt left by a replay-start that died (reboot,
    crash) whose pid Windows had handed to some other process made start
    print "a replay publisher is already running ... - kept" and start no
    local feeds at all. A recorded pid now counts only when its command
    line names this repo's scripts/replay_publish.py."""
    vp = Path(sys.executable)          # the test venv's python has psutil
    script = str(sandbox.ROOT / "scripts" / "replay_publish.py")
    other = _sleeper(tmp_path)
    ours = _sleeper(tmp_path, script, "--register")
    try:
        assert sandbox._alive_pids(vp, [other.pid]) == []
        assert sandbox._alive_pids(vp, [ours.pid]) == [ours.pid]

        sandbox.REPLAY_PIDFILE.write_text(f"replay {other.pid}\n", encoding="utf-8")
        monkeypatch.setattr(sandbox, "_spawn_detached", lambda a, log: _FakeProc(99))
        monkeypatch.setattr(sandbox, "_port_busy",
                            lambda port: sandbox.REPLAY_PIDFILE.exists())
        monkeypatch.setattr(sandbox, "_rtsp_publishing", lambda name: True)
        sandbox.start_feeds(vp)
        assert sandbox.REPLAY_PIDFILE.read_text(encoding="utf-8") == "feeds 99\n"
        assert "already running" not in capsys.readouterr().out
    finally:
        for proc in (other, ours):
            proc.kill()
            proc.wait(timeout=10)


def test_start_feeds_forgets_a_publisher_that_dies_at_once(sandbox, monkeypatch):
    monkeypatch.setattr(sandbox, "FEED_RETRY_DELAY_S", 0.0)
    spawned: list[int] = []
    monkeypatch.setattr(sandbox, "_spawn_detached",
                        lambda a, log: spawned.append(1) or _FakeProc(5, rc=1))
    monkeypatch.setattr(sandbox, "_port_busy", lambda port: False)
    sandbox.start_feeds(Path("venv-python"))     # reported, start continues
    assert not sandbox.REPLAY_PIDFILE.exists()
    assert len(spawned) == 2                     # one retry, then give up


def test_feed_publisher_that_dies_at_birth_is_retried_once(sandbox, monkeypatch,
                                                           capsys):
    """Regression (25 Sep, laptop): after a stop+start the publisher died
    at birth (rc 3221225786) and start carried on with no local feeds on
    the wall; the identical start succeeded the next time. One retry."""
    monkeypatch.setattr(sandbox, "FEED_RETRY_DELAY_S", 0.0)
    procs = iter([_FakeProc(5, rc=3221225786), _FakeProc(77)])
    monkeypatch.setattr(sandbox, "_spawn_detached", lambda a, log: next(procs))
    busy = iter([False, True])   # port free before; bound on the second try
    monkeypatch.setattr(sandbox, "_port_busy", lambda port: next(busy, True))
    monkeypatch.setattr(sandbox, "_rtsp_publishing", lambda name: True)
    sandbox.start_feeds(Path("venv-python"))
    assert sandbox.REPLAY_PIDFILE.read_text(encoding="utf-8") == "feeds 77\n"
    out = capsys.readouterr().out
    assert "retrying once" in out and "feeds publishing" in out


def test_start_brings_the_feeds_up_after_the_seeds_before_the_worker(
        sandbox, monkeypatch):
    order: list[str] = []
    vp = Path("venv-python")
    monkeypatch.setattr(sandbox.subprocess, "call", lambda *a, **k: 0)  # doctor
    monkeypatch.setattr(sandbox, "ensure_venv_and_deps", lambda: vp)
    for step in ("ensure_directml", "ensure_ffmpeg", "ensure_models",
                 "ensure_probe"):
        monkeypatch.setattr(sandbox, step, lambda vp: None)
    monkeypatch.setattr(sandbox, "ensure_seeds", lambda vp: order.append("seeds"))
    monkeypatch.setattr(sandbox, "ensure_frontend", lambda: order.append("frontend"))
    monkeypatch.setattr(sandbox, "start_feeds", lambda vp: order.append("feeds"))
    pids = iter([101, 102])

    def spawn(args, log):
        order.append("api" if "backend.app" in args else "worker")
        return _FakeProc(next(pids))
    monkeypatch.setattr(sandbox, "_spawn_detached", spawn)
    api_up = iter([False, True])                 # free before, bound after
    monkeypatch.setattr(sandbox, "_port_busy", lambda port: next(api_up))
    monkeypatch.setattr(sandbox.webbrowser, "open", lambda url: None)

    assert sandbox.start() == 0
    assert order == ["seeds", "frontend", "feeds", "api", "worker"]
    assert sandbox.PIDFILE.read_text(encoding="utf-8") == "api 101\nworker 102\n"


def test_stop_stops_the_feeds_after_the_platform(sandbox, monkeypatch):
    sandbox.PIDFILE.write_text("api 1\nworker 2\n", encoding="utf-8")
    sandbox.REPLAY_PIDFILE.write_text("feeds 3\n", encoding="utf-8")
    killed: list[list[int]] = []
    monkeypatch.setattr(sandbox, "venv_python", lambda: None)
    monkeypatch.setattr(sandbox, "_kill_trees", lambda pids: killed.append(pids))

    assert sandbox.stop() == 0
    assert killed == [[1, 2], [3]]               # worker first, feeds last
    assert not sandbox.PIDFILE.exists() and not sandbox.REPLAY_PIDFILE.exists()


def test_stop_with_only_the_feeds_recorded_stops_them(sandbox, monkeypatch):
    sandbox.REPLAY_PIDFILE.write_text("replay 3\n", encoding="utf-8")
    killed: list[list[int]] = []
    monkeypatch.setattr(sandbox, "_kill_trees", lambda pids: killed.append(pids))
    assert sandbox.stop() == 0
    assert killed == [[3]] and not sandbox.REPLAY_PIDFILE.exists()


def test_status_reports_feeds_n_of_register_publishing(sandbox, monkeypatch,
                                                      capsys):
    monkeypatch.setattr(sandbox, "_port_busy", lambda port: True)
    monkeypatch.setattr(sandbox, "_rtsp_publishing",
                        lambda name: name != "local02")
    sandbox._feeds_line()
    assert capsys.readouterr().out.startswith(
        "feeds    : 2/3 publishing (rtsp://127.0.0.1:")

    monkeypatch.setattr(sandbox, "_port_busy", lambda port: False)
    sandbox._feeds_line()
    assert "0/3 publishing" in capsys.readouterr().out


class _FakeSock:
    def __init__(self, reply: bytes):
        self.reply, self.sent = reply, b""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def sendall(self, data: bytes):
        self.sent += data

    def recv(self, n: int) -> bytes:
        return self.reply[:n]


def test_rtsp_publishing_is_a_describe_answered_200(lp, monkeypatch):
    socks: list[_FakeSock] = []

    def connect(reply):
        def fake(addr, timeout):
            assert addr[0] == "127.0.0.1"              # local mediamtx only
            socks.append(_FakeSock(reply))
            return socks[-1]
        return fake

    monkeypatch.setattr(lp.socket, "create_connection",
                        connect(b"RTSP/1.0 200 OK\r\nCSeq: 1\r\n"))
    assert lp._rtsp_publishing("local01", port=8554)
    assert socks[-1].sent.startswith(
        b"DESCRIBE rtsp://127.0.0.1:8554/stream/local01 RTSP/1.0\r\n")

    monkeypatch.setattr(lp.socket, "create_connection",
                        connect(b"RTSP/1.0 404 Not Found\r\n"))
    assert not lp._rtsp_publishing("local02", port=8554)

    def refused(addr, timeout):
        raise ConnectionRefusedError
    monkeypatch.setattr(lp.socket, "create_connection", refused)
    assert not lp._rtsp_publishing("local03", port=8554)


# ------------------------------------------------ status: uptime + tunnel (S6.1b)

def test_fmt_uptime_is_compact_and_never_negative(lp):
    assert lp._fmt_uptime(42) == "42 s"
    assert lp._fmt_uptime(7 * 60 + 5) == "7 min 05 s"
    assert lp._fmt_uptime(3 * 3600 + 7 * 60) == "3 h 07 min"
    assert lp._fmt_uptime(2 * 86400 + 4 * 3600 + 59) == "2 d 04 h"
    assert lp._fmt_uptime(-5) == "0 s"


def test_uptime_reports_our_processes_and_refuses_reused_pids(lp, tmp_path,
                                                              monkeypatch, capsys):
    """A recorded pid counts as up only while its command line names this
    repo (the api/worker run the repo's .venv python): after a reboot a
    reused pid must read NOT RUNNING, not 'up 3 h'."""
    vp = Path(sys.executable)          # the test venv's python has psutil
    ours = _sleeper(tmp_path, str(lp.ROOT / ".venv" / "python"), "-m", "backend.app")
    other = _sleeper(tmp_path)
    gone = _sleeper(tmp_path)
    gone.kill()
    gone.wait()
    pidfile = tmp_path / "launcher_pids.txt"
    pidfile.write_text(f"api {ours.pid}\nworker {other.pid}\nml {gone.pid}\n",
                       encoding="utf-8")
    monkeypatch.setattr(lp, "PIDFILE", pidfile)
    try:
        got = lp._uptimes(vp, lp._read_pidfile(pidfile))
        assert got["api"].isdigit()
        assert got["worker"] == "foreign"
        assert got["ml"] == "gone"
        assert got["tailscaled"] in ("none", "denied") or got["tailscaled"].isdigit()

        lp._uptime_line(vp)
        out = capsys.readouterr().out
        assert "api up " in out and f"(pid {ours.pid})" in out
        assert "worker NOT RUNNING (pid now belongs to another process)" in out
        assert "ml NOT RUNNING (process gone)" in out
    finally:
        ours.kill()
        other.kill()


def test_uptime_without_a_venv_or_a_pidfile_says_what_to_do(lp, tmp_path,
                                                            monkeypatch, capsys):
    monkeypatch.setattr(lp, "PIDFILE", tmp_path / "absent.txt")
    assert lp._uptime_line(None) is None
    assert "needs .venv" in capsys.readouterr().out
    lp._uptime_line(Path(sys.executable))
    assert "no API or worker recorded" in capsys.readouterr().out


_FUNNEL_JSON = """{
  "TCP": {"443": {"HTTPS": true}},
  "Web": {"sentinel.tail1234.ts.net:443": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:8000"}}},
          "sentinel.tail1234.ts.net:8443": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:5173"}}}},
  "AllowFunnel": {"sentinel.tail1234.ts.net:443": true, "sentinel.tail1234.ts.net:8443": false}
}"""

_FUNNEL_TEXT = """\
# Funnel on:
#     - https://sentinel.tail1234.ts.net

https://sentinel.tail1234.ts.net (Funnel on)
|-- / proxy http://127.0.0.1:8000

https://sentinel.tail1234.ts.net:8443 (tailnet only)
|-- / proxy http://127.0.0.1:5173
"""


def test_parse_funnel_reads_json_and_plain_text(lp):
    expected = [("https://sentinel.tail1234.ts.net", ["http://127.0.0.1:8000"])]
    assert lp._parse_funnel(_FUNNEL_JSON) == expected   # 8443 not funnelled
    assert lp._parse_funnel(_FUNNEL_TEXT) == expected   # tailnet-only skipped
    assert lp._parse_funnel("No serve config\n") == []
    assert lp._parse_funnel("{}") == []


class _Done:
    def __init__(self, stdout: str, returncode: int = 0):
        self.stdout, self.returncode = stdout, returncode


def test_tunnel_line_names_the_url_and_its_health(lp, monkeypatch, capsys):
    monkeypatch.setattr(lp, "_tailscale_exe", lambda: "tailscale")
    monkeypatch.setattr(lp, "API_PORT", 8000)
    monkeypatch.setattr(lp.subprocess, "run", lambda *a, **k: _Done(_FUNNEL_JSON))
    probed: list[str] = []
    monkeypatch.setattr(lp, "_https_health",
                        lambda url: probed.append(url) or "/api/health 200")
    lp._tunnel_line("7200")
    out = capsys.readouterr().out
    assert probed == ["https://sentinel.tail1234.ts.net"]
    assert ("tunnel   : funnel ON https://sentinel.tail1234.ts.net -> :8000;"
            " /api/health 200; tailscaled up 2 h 00 min") in out


def test_tunnel_line_says_plainly_when_the_url_is_down(lp, monkeypatch, capsys):
    monkeypatch.setattr(lp, "_tailscale_exe", lambda: None)
    lp._tunnel_line(None)
    assert "tailscale not installed" in capsys.readouterr().out

    monkeypatch.setattr(lp, "_tailscale_exe", lambda: "tailscale")
    monkeypatch.setattr(lp, "API_PORT", 8000)
    # --json unsupported (old client, rc 1) -> the plain-text call: no funnel
    calls: list[list[str]] = []

    def run(argv, **kw):
        calls.append(argv)
        return _Done("", 1) if "--json" in argv else _Done("No serve config\n")
    monkeypatch.setattr(lp.subprocess, "run", run)
    monkeypatch.setattr(lp, "_https_health", lambda url: pytest.fail("no URL to probe"))
    lp._tunnel_line("none")
    assert [c[-1] for c in calls] == ["--json", "status"]
    assert "NO FUNNEL publishing :8000 - the public URL is down" in capsys.readouterr().out

    # a funnel that publishes something else (the Vite port) is not ours
    monkeypatch.setattr(lp.subprocess, "run", lambda *a, **k: _Done(
        _FUNNEL_TEXT.replace(":8000", ":5173")))
    lp._tunnel_line(None)
    assert "NO FUNNEL publishing :8000" in capsys.readouterr().out
