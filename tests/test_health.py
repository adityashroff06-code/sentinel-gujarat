"""S3.1b acceptance: the health checker (decisions C14, F31).

An active RTSP camera with a fresh tee is online and one with a stale tee
is degraded — judged by tee freshness alone, never probed; a registered
camera whose RTSP is dead goes offline via a paced ffprobe; the CDN is
never touched (asserted by instrumenting CdnSession); probes carry the
TCP transport and ``-timeout`` flags; 0 = off.
"""

from __future__ import annotations

import os
import threading
import time
import types
import urllib.parse

import pytest

import backend.services.health as health
from backend.core import cdn_session, config
from backend.core import db as dbmod

OK_PROBE = '{"streams": [{"codec_name": "h264"}]}'

CAMERAS = [
    # camera_id, transport, fps_tier, rtsp_url_template
    ("act-fresh", "rtsp", "active", None),
    ("act-stale", "rtsp", "active", None),
    ("act-notee", "rtsp", "active", None),
    ("reg-dead", "rtsp", "registered",
     "rtsp://<email>:<password>@127.0.0.1:9500/stream/reg-dead"),
    ("reg-live", "hls", "registered", None),
    ("rep-local", "replay", "registered", None),
]


@pytest.fixture()
def grid(tmp_path, monkeypatch):
    """A migrated per-test DB with the six-camera grid and a temp tee root.
    The "sandbox gateway" is pointed at 127.0.0.1:9500 (where reg-dead's
    template lives), so its placeholders are the gateway's to fill."""
    monkeypatch.setenv("SENTINEL_DB", str(tmp_path / "health.db"))
    monkeypatch.setenv("SENTINEL_HLS_DIR", str(tmp_path / "hls"))
    monkeypatch.setenv("SENTINEL_STREAM_IP", "127.0.0.1")
    monkeypatch.setenv("SENTINEL_RTSP_PORT", "9500")
    con = dbmod.connect()
    dbmod.migrate(con)
    now = dbmod.utcnow()
    for camera_id, transport, tier, template in CAMERAS:
        con.execute(
            "INSERT INTO cameras (camera_id, transport, fps_tier, rtsp_url_template,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (camera_id, transport, tier, template, now, now),
        )
    con.commit()
    con.close()


@pytest.fixture()
def cdn_guard(monkeypatch):
    """Fails the pass if health so much as logs in to the CDN (C14)."""
    calls: list[str] = []
    monkeypatch.setattr(
        cdn_session.CdnSession, "login", lambda self: calls.append("login")
    )
    monkeypatch.setattr(
        cdn_session.CdnSession,
        "get",
        lambda self, url, max_attempts=4: calls.append(url),
    )
    return calls


@pytest.fixture()
def fake_ffprobe(monkeypatch):
    """Intercepts subprocess.run inside health: reg-live answers with a
    stream, everything else is refused. Records every command."""
    commands: list[list[str]] = []

    def run(cmd, capture_output=True, text=True, timeout=None):
        commands.append(list(cmd))
        url = cmd[-1]
        if "reg-live" in url:
            return types.SimpleNamespace(returncode=0, stdout=OK_PROBE, stderr="")
        return types.SimpleNamespace(returncode=1, stdout="", stderr="Connection refused")

    monkeypatch.setattr(health.subprocess, "run", run)
    return commands


def _write_tee(camera_id: str, age_s: float = 0.0) -> None:
    d = config.hls_dir() / camera_id
    d.mkdir(parents=True, exist_ok=True)
    idx = d / "index.m3u8"
    idx.write_text("#EXTM3U\n#EXTINF:2.0,\nseg000001.ts\n", encoding="utf-8")
    if age_s:
        past = time.time() - age_s
        os.utime(idx, (past, past))


def _healths() -> dict[str, tuple[str | None, str | None]]:
    con = dbmod.connect()
    try:
        return {
            r["camera_id"]: (r["health"], r["last_seen"])
            for r in con.execute("SELECT camera_id, health, last_seen FROM cameras")
        }
    finally:
        con.close()


# ------------------------------------------------------------------ the pass

def test_check_all_verdicts_without_touching_the_cdn(grid, fake_ffprobe, cdn_guard) -> None:
    """Fresh tee online, stale tee degraded, dead RTSP offline, live RTSP
    online with last_seen — and zero CDN calls (C14)."""
    _write_tee("act-fresh")
    _write_tee("act-stale", age_s=100.0)

    tally = health.check_all()

    assert tally == {"online": 2, "degraded": 1, "offline": 1, "unchanged": 2}
    healths = _healths()
    assert healths["act-fresh"] == (
        "online", healths["act-fresh"][1]
    ) and healths["act-fresh"][1] is not None
    assert healths["act-stale"][0] == "degraded"
    assert healths["act-stale"][1] is None  # degraded never fakes a last_seen
    assert healths["act-notee"] == (None, None)  # no worker proves nothing
    assert healths["reg-dead"][0] == "offline"
    assert healths["reg-live"][0] == "online" and healths["reg-live"][1] is not None
    assert healths["rep-local"] == (None, None)  # local replay: not checked

    assert cdn_guard == [], "the health checker touched the CDN"
    cdn_host = urllib.parse.urlsplit(config.cdn()).hostname
    assert all(cdn_host not in cmd[-1] for cmd in fake_ffprobe)


def test_active_cameras_are_never_probed(grid, fake_ffprobe, cdn_guard) -> None:
    """Root rule 2: the worker holds an active camera's single pull; the
    checker judges the tee and never opens a second RTSP connection."""
    _write_tee("act-fresh")
    _write_tee("act-stale", age_s=100.0)
    health.check_all()
    probed = {cmd[-1].rsplit("/", 1)[-1] for cmd in fake_ffprobe}
    assert probed == {"reg-dead", "reg-live"}


def test_probe_command_shape(grid, fake_ffprobe, cdn_guard) -> None:
    """RTSP over TCP with -timeout (never -rw_timeout, F44), through
    config.ffprobe(), the template's placeholders filled."""
    health.check_all()
    by_url = {cmd[-1]: cmd for cmd in fake_ffprobe}
    dead = next(u for u in by_url if "reg-dead" in u)
    cmd = by_url[dead]
    assert cmd[0] == config.ffprobe()
    assert "-rtsp_transport" in cmd and cmd[cmd.index("-rtsp_transport") + 1] == "tcp"
    assert "-timeout" in cmd and "-rw_timeout" not in cmd
    assert dead.startswith("rtsp://") and "127.0.0.1:9500" in dead
    assert "<email>" not in dead and "<password>" not in dead
    # The default sandbox pattern for a camera without a template.
    live = next(u for u in by_url if "reg-live" in u)
    assert live.endswith("/stream/reg-live")


FAKE_EMAIL = "judge@example.org"
FAKE_PASSWORD = "not-the-real-password"

#: Templates carrying the credential placeholders on a host that is NOT the
#: configured sandbox gateway (127.0.0.1:9500 in the grid fixture).
FOREIGN_TEMPLATES = {
    "evil-host": "rtsp://<email>:<password>@attacker.example:554/x",
    "evil-port": "rtsp://<email>:<password>@127.0.0.1:9999/x",
    "evil-noport": "rtsp://<email>:<password>@127.0.0.1/x",
    "evil-fragment": "rtsp://<email>:<password>@attacker.example#@127.0.0.1:9500/x",
    "evil-scheme": "http://<email>:<password>@127.0.0.1:9500/x",
    "evil-space": "rtsp://<email>:<password>@attacker.example /@127.0.0.1:9500/x",
}


def _credential_forms() -> set[str]:
    return {FAKE_EMAIL, FAKE_PASSWORD, urllib.parse.quote(FAKE_EMAIL, safe=""),
            urllib.parse.quote(FAKE_PASSWORD, safe="")}


def test_sandbox_credentials_are_never_sent_to_a_non_gateway_host(
        grid, monkeypatch, fake_ffprobe, cdn_guard) -> None:
    """Regression (review, 25 Sep; root rule 1): _resolve_rtsp_url filled
    <email>/<password> for ANY template host, so an evaluator-registered
    camera with rtsp://<email>:<password>@attacker.example:554/x made the
    health probe hand the organisers' credentials to attacker.example on an
    auth challenge. The placeholders are now filled only for a template on
    the configured gateway (stream_ip:rtsp_port); any other host is probed
    as-is, placeholders and all."""
    monkeypatch.setenv("SENTINEL_EMAIL", FAKE_EMAIL)
    monkeypatch.setenv("SENTINEL_PASSWORD", FAKE_PASSWORD)
    con = dbmod.connect()
    now = dbmod.utcnow()
    for camera_id, template in FOREIGN_TEMPLATES.items():
        con.execute(
            "INSERT INTO cameras (camera_id, transport, fps_tier, rtsp_url_template,"
            " created_at, updated_at) VALUES (?, 'rtsp', 'registered', ?, ?, ?)",
            (camera_id, template, now, now),
        )
    con.commit()
    con.close()

    health.check_all()

    probed = {cmd[-1] for cmd in fake_ffprobe}
    for camera_id, template in FOREIGN_TEMPLATES.items():
        assert template in probed, f"{camera_id} was not probed as-is"
    secrets = _credential_forms()
    for url in probed:
        if "/stream/" in url:
            continue  # the gateway's own cameras (reg-dead, reg-live)
        assert not any(s in url for s in secrets), "credentials left the gateway"
    # The gateway itself still gets them: reg-dead's placeholders are filled.
    dead = next(u for u in probed if u.endswith("/stream/reg-dead"))
    assert dead.startswith(
        f"rtsp://{urllib.parse.quote(FAKE_EMAIL, safe='')}:{FAKE_PASSWORD}@127.0.0.1:9500/")


def test_resolve_rtsp_url_fills_placeholders_only_on_the_gateway(grid, monkeypatch) -> None:
    """The unit rule behind the regression above: gateway host and port
    (hostname case-insensitive, 554 when the template names none) → filled;
    anything else → unchanged; a placeholder-free local URL → unchanged."""
    monkeypatch.setenv("SENTINEL_EMAIL", FAKE_EMAIL)
    monkeypatch.setenv("SENTINEL_PASSWORD", FAKE_PASSWORD)
    for template in FOREIGN_TEMPLATES.values():
        assert health._resolve_rtsp_url("x", template) == template
    local = "rtsp://127.0.0.1:8554/stream/local01"
    assert health._resolve_rtsp_url("local01", local) == local
    filled = health._resolve_rtsp_url(
        "cam01", "rtsp://<email>:<password>@127.0.0.1:9500/stream/cam01")
    assert FAKE_PASSWORD in filled and "<password>" not in filled
    monkeypatch.setenv("SENTINEL_STREAM_IP", "Gateway.Example")
    monkeypatch.setenv("SENTINEL_RTSP_PORT", "554")
    filled = health._resolve_rtsp_url(
        "cam01", "RTSP://<email>:<password>@gateway.example/stream/cam01")
    assert FAKE_PASSWORD in filled  # default port 554, case-insensitive host


def test_probe_timeout_and_pacing_budget() -> None:
    """The task's stated budget: 2 concurrent probes, 20 s each."""
    assert health.PROBE_WORKERS == 2
    assert health.PROBE_TIMEOUT_S == 20.0
    assert health.TEE_FRESH_S == 20.0


def test_probe_rtsp_swallows_a_timeout(grid, monkeypatch, cdn_guard) -> None:
    """A hung gateway is a verdict (offline), not an exception — and the
    credentialed argv in TimeoutExpired never escapes (root rule 1)."""

    def run(cmd, capture_output=True, text=True, timeout=None):
        raise health.subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(health.subprocess, "run", run)
    assert health.probe_rtsp("rtsp://user:secret@127.0.0.1:9500/stream/x") is False


# ------------------------------------------- /api/health workers count (fix)

def test_api_health_counts_alive_workers_from_the_snapshot(grid, tmp_path, monkeypatch) -> None:
    """Regression (S3.1b): counts.workers was hardcoded 0 — it must read
    the same supervisor snapshot GET /api/workers serves."""
    import json

    from fastapi.testclient import TestClient

    import backend.app.main as main_mod
    from backend.app import routes_analytics

    snap = tmp_path / "worker_stats.json"
    snap.write_text(
        json.dumps(
            {
                "written_at": "2026-09-25T10:00:00+00:00",
                "cameras": {
                    "cam06": {"alive": True},
                    "cam09": {"alive": True},
                    "cam10": {"alive": False},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(routes_analytics, "_worker_stats_path", lambda: snap)
    client = TestClient(main_mod.create_app(), base_url="http://localhost")
    assert client.get("/api/health").json()["counts"]["workers"] == 2

    monkeypatch.setattr(
        routes_analytics, "_worker_stats_path", lambda: tmp_path / "missing.json"
    )
    assert client.get("/api/health").json()["counts"]["workers"] == 0


# ------------------------------------------------------------ the background

def test_interval_zero_means_off(monkeypatch) -> None:
    monkeypatch.setenv("SENTINEL_HEALTH_INTERVAL_S", "0")
    assert health.start_background() is None


def test_run_loop_waits_first_and_stops_cleanly(monkeypatch) -> None:
    """The loop waits before the first pass (a short-lived test app never
    fires one) and exits when the stop event is set."""
    passes: list[int] = []
    monkeypatch.setattr(health, "check_all", lambda: passes.append(1))

    stop = threading.Event()
    stop.set()
    health.run_loop(0.01, stop)  # returns immediately, no pass
    assert passes == []

    stop = threading.Event()
    t = threading.Thread(target=health.run_loop, args=(0.01, stop), daemon=True)
    t.start()
    time.sleep(0.2)
    stop.set()
    t.join(timeout=2)
    assert not t.is_alive()
    assert passes  # at least one pass ran on the interval


def test_first_health_pass_runs_soon_after_start_not_a_whole_interval_later(
        monkeypatch) -> None:
    """Regression (25 Sep, live platform): the loop slept a full 300 s
    interval before its first pass, so after every launch.py start the map
    and header showed the previous run's health ("1/58 cameras online")
    for five minutes. The first pass now runs FIRST_PASS_DELAY_S after
    start, then every interval."""
    assert health.FIRST_PASS_DELAY_S <= 60
    passes: list[float] = []
    monkeypatch.setattr(health, "check_all", lambda: passes.append(time.monotonic()))
    stop = threading.Event()
    t0 = time.monotonic()
    t = threading.Thread(target=health.run_loop, args=(300.0, stop, 0.05), daemon=True)
    t.start()
    deadline = time.monotonic() + 3
    while not passes and time.monotonic() < deadline:
        time.sleep(0.02)
    stop.set()
    t.join(timeout=2)
    assert passes, "no pass ran within 3 s of start"
    assert passes[0] - t0 < 1.0          # not 300 s
    assert len(passes) == 1              # then it waits the full interval
    # and the delay never exceeds a (short) configured interval
    passes.clear()
    stop = threading.Event()
    t = threading.Thread(target=health.run_loop, args=(0.05, stop), daemon=True)
    t.start()
    time.sleep(0.5)
    stop.set()
    t.join(timeout=2)
    assert passes
