"""backend/core/cdn_session.py — origin-guard and login regressions.

The fetch guard must be boundary-exact: with the CDN at
``https://cctv.example``, a bare ``startswith`` admitted
``https://cctv.example.evil.tld/...`` (wave-2 review). It must hold on
every redirect hop too, and a 403 wave re-logs in once, not once per
thread (25 Sep review). No network is touched — the guard refuses before
any request is made, and the later tests talk to an ``httpx.MockTransport``
CDN inside this process.
"""

from __future__ import annotations

import threading

import httpx
import pytest

from backend.core import cdn_session


@pytest.fixture()
def session(monkeypatch):
    monkeypatch.setenv("SENTINEL_CDN", "https://cctv.example")
    return cdn_session.CdnSession()


def test_prefix_spoof_of_the_cdn_origin_is_refused(session):
    with pytest.raises(cdn_session.CdnError, match="non-CDN"):
        session.get("https://cctv.example.evil.tld/hls/cam06/index.m3u8")


def test_entirely_foreign_origin_is_refused(session):
    with pytest.raises(cdn_session.CdnError, match="non-CDN"):
        session.get("https://evil.example/enc.key")


def test_a_path_still_resolves_inside_the_origin(session, monkeypatch):
    # Reaching login (not the guard) proves the URL passed the origin check.
    def fail_login(self):
        raise cdn_session.CdnError("login reached")

    monkeypatch.setattr(cdn_session.CdnSession, "login", fail_login)
    with pytest.raises(cdn_session.CdnError, match="login reached"):
        session.get("/hls/cam06/index.m3u8")


# ------------------------------------------------ a MockTransport CDN

@pytest.fixture()
def cdn_env(monkeypatch):
    """Throw-away login values: the MockTransport CDN never leaves the
    process, and nothing here is a real credential."""
    monkeypatch.setenv("SENTINEL_CDN", "https://cctv.example")
    monkeypatch.setenv("SENTINEL_EMAIL", "tester@example.invalid")
    monkeypatch.setenv("SENTINEL_PASSWORD", "not-a-real-password")
    # no jittered pause between attempts: these tests count requests, not time
    monkeypatch.setattr(cdn_session, "backoff_delay", lambda attempt: (0, 0.0))


def test_cdn_redirect_off_origin_is_refused_on_every_hop(cdn_env):
    """Regression (25 Sep review): the client followed redirects and only
    the URL handed to ``get()`` was origin-checked, so a 3xx from the CDN
    carried the organisers' session to another host or port — and the
    relay handed the fetched bytes to the viewer. Every hop is now checked
    before it is sent; a same-origin redirect (the CDN's own 302s) still
    works."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        path = request.url.path
        if path == "/auth/login":
            return httpx.Response(200, headers={"set-cookie": "s=1; Path=/"})
        if path == "/cam01/moved.ts":
            return httpx.Response(302, headers={"location": "/cam01/seg00001.ts"})
        if path == "/cam01/seg00001.ts":
            return httpx.Response(200, content=b"TS")
        if path == "/cam01/port.ts":
            return httpx.Response(302, headers={"location": "https://cctv.example:8443/x.ts"})
        return httpx.Response(302, headers={"location": "http://evil.example/leak.ts"})

    session = cdn_session.CdnSession(transport=httpx.MockTransport(handler))
    assert session.get("/cam01/moved.ts").content == b"TS"  # same origin: followed
    for path in ("/cam01/seg00002.ts", "/cam01/port.ts"):
        with pytest.raises(cdn_session.CdnError, match="off-origin redirect"):
            session.get(path, max_attempts=2)
    assert not any("evil.example" in u or ":8443" in u for u in seen), seen


@pytest.mark.parametrize("relogin_status", [200, 403])
def test_cdn_relogin_after_403_is_single_flight(cdn_env, relogin_status):
    """Regression (25 Sep review): the login lock guarded only the first
    login; when the session cookie expired (or the CDN began refusing)
    mid-play, EVERY in-flight relay fetch got a 403 and POSTed
    /auth/login on its own — N concurrent 403s, N logins, the burst the
    CDN bans for minutes (docs/sandbox-findings.md §1). Now one re-login
    per episode, whether that login succeeds or is itself refused."""
    n = 8
    lock = threading.Lock()
    state = {"valid": "", "logins": 0, "stale": 0}
    barrier = threading.Barrier(n, timeout=10)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            with lock:
                state["logins"] += 1
                k = state["logins"]
            if k > 1 and relogin_status != 200:
                return httpx.Response(relogin_status)
            with lock:
                state["valid"] = f"v{k}"
            return httpx.Response(200, headers={"set-cookie": f"s=v{k}; Path=/"})
        if f"s={state['valid']}" in request.headers.get("cookie", ""):
            return httpx.Response(200, content=b"ok")
        with lock:
            state["stale"] += 1
            first_round = state["stale"] <= n
        if first_round:
            barrier.wait()  # every thread's GET is in flight before any 403 lands
        return httpx.Response(403)

    session = cdn_session.CdnSession(transport=httpx.MockTransport(handler))
    assert session.get("/cam01/seg00001.ts").content == b"ok"  # logged in once
    assert state["logins"] == 1
    state["valid"] = "expired"  # the cookie expires (or a ban starts) mid-play

    outcomes: list[object] = []

    def fetch(i: int) -> None:
        try:
            outcomes.append(session.get(f"/cam{i:02d}/seg00002.ts", max_attempts=2).content)
        except cdn_session.CdnError as exc:
            outcomes.append(exc.status)

    threads = [threading.Thread(target=fetch, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
    assert len(outcomes) == n
    assert state["logins"] == 2, f"{state['logins'] - 1} re-logins for one episode"
    assert outcomes == [b"ok" if relogin_status == 200 else 403] * n
