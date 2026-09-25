"""The HLS relay (docs/api.md §7 hls row, §9, B11; decisions C7, C14).

S3.1b acceptance, extended on 25 Sep for the relay lane ("every camera
plays on the Live Wall"): the relay serves the worker's local tee when
fresh; a LOCAL feed without a fresh tee is proxied from mediamtx's own HLS
server (URIs rewritten, allow-listed, host pinned to 127.0.0.1); a sandbox
camera keeps a stale tee only while it is younger than 120 s and otherwise
falls to the CDN VOD relay (the old "an RTSP camera never falls to the
CDN" rule is replaced — see the tests below for why); the CDN path
rewrites a sliding window with the key and segment URIs pointed back at
the relay, refuses off-playlist names, names outside the live window it
served (rule 6) and off-origin URLs (redirect hops included), needs a
16-byte key, shares ONE upstream fetch between concurrent viewers of a
segment, and backs off (503) after a refusal — at once, never after a turn
in the playlist pacer; ``/source`` says which path a camera
takes; header, ``sentinel_key`` cookie and ``sentinel_session`` cookie all
authenticate; the relay is rate-limited at the documented 16-tile budget.
"""

from __future__ import annotations

import os
import threading
import time

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import backend.app.main as main_mod
import backend.app.routes_hls as routes_hls
from backend.core import config, passwords
from backend.core import db as dbmod
from backend.core.cdn_session import CdnError

ADMIN = {"X-API-Key": "test-admin-key-not-a-secret"}
VIEWER = {"X-API-Key": "test-viewer-key-not-a-secret"}

KEY_16 = b"0123456789abcdef"
MTX_PORT = 18888

#: 24 x 6 s VOD segments, AES key, plus one absolute off-origin URI that
#: must never become servable through /seg/{name}.
PLAYLIST = (
    "#EXTM3U\n#EXT-X-VERSION:6\n#EXT-X-TARGETDURATION:7\n"
    "#EXT-X-PLAYLIST-TYPE:VOD\n"
    '#EXT-X-KEY:METHOD=AES-128,URI="/enc.key",IV=0x00000000000000000000000000000000\n'
    + "".join(f"#EXTINF:6.0,\nseg{i:05d}.ts\n" for i in range(24))
    + "#EXTINF:6.0,\nhttps://evil.example/leak.ts\n#EXT-X-ENDLIST\n"
)
#: The fixture pins the shared-timeline position here: segment 10 is the
#: live edge, so the served window is seg00001..seg00010.
POSITION_S = 60.0

#: The sandbox's real shape: a 12 h VOD of 7,200 x 6 s segments.
VOD_12H = (
    "#EXTM3U\n#EXT-X-VERSION:6\n#EXT-X-TARGETDURATION:7\n"
    "#EXT-X-PLAYLIST-TYPE:VOD\n"
    '#EXT-X-KEY:METHOD=AES-128,URI="/enc.key",IV=0x00000000000000000000000000000000\n'
    + "".join(f"#EXTINF:6.0,\nseg{i:05d}.ts\n" for i in range(7200))
    + "#EXT-X-ENDLIST\n"
)

#: What mediamtx v1.21.1 actually answered (observed 25 Sep with
#: MTX_HLSVARIANT=mpegts): a multivariant index, a session-scoped child
#: playlist, session-scoped segment names.
MTX_INDEX = (
    "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-INDEPENDENT-SEGMENTS\n\n"
    '#EXT-X-STREAM-INF:BANDWIDTH=9811305,CODECS="avc1.640028",RESOLUTION=1920x1080\n'
    "main_stream.m3u8?session=8b658fca-5593-4d2d-bac0-c0ca45022460\n"
)
MTX_SESSION = "8b658fca-5593-4d2d-bac0-c0ca45022460"
MTX_CHILD = (
    "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:4\n#EXT-X-MEDIA-SEQUENCE:0\n"
    f"#EXTINF:3.93333,\na78525e1f86d_main_seg0.ts?session={MTX_SESSION}\n"
    f"#EXTINF:2.00000,\na78525e1f86d_main_seg1.ts?session={MTX_SESSION}\n"
)


class FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.text = content.decode(errors="replace")


class FakeCdn:
    """Stands in for CdnSession; records every URL the relay fetches."""

    def __init__(self, playlist: str = PLAYLIST, key: bytes = KEY_16) -> None:
        self.playlist = playlist
        self.key = key
        self.calls: list[str] = []
        self.segment_delay_s = 0.0
        self.error: Exception | None = None
        self.error_delay_s = 0.0
        self._lock = threading.Lock()

    def get(self, url: str, max_attempts: int = 4) -> FakeResponse:
        with self._lock:
            self.calls.append(url)
        assert url.startswith(config.cdn()), f"relay fetched outside the CDN: {url}"
        if self.error is not None:
            time.sleep(self.error_delay_s)
            raise self.error
        if url.endswith(".m3u8"):
            return FakeResponse(self.playlist.encode())
        if url.endswith("enc.key"):
            return FakeResponse(self.key)
        if self.segment_delay_s:
            time.sleep(self.segment_delay_s)
        return FakeResponse(b"TSDATA:" + url.encode())


class FakeMtx:
    """Stands in for ``routes_hls._mtx_fetch``: the local mediamtx server."""

    def __init__(self) -> None:
        self.urls: list[str] = []
        self.index = MTX_INDEX
        self.child = MTX_CHILD
        self.down = False
        self.status = 200

    def __call__(self, url: str, timeout_s: float) -> tuple[int, bytes]:
        self.urls.append(url)
        if self.down:
            raise ConnectionError("connection refused")
        if self.status != 200:
            return self.status, b'{"status":"error"}'
        path = url.split("?", 1)[0]
        if path.endswith("/index.m3u8"):
            return 200, self.index.encode()
        if path.endswith(".m3u8"):
            return 200, self.child.encode()
        return 200, b"MTXTS:" + path.encode()


@pytest.fixture()
def fake_cdn(monkeypatch):
    fake = FakeCdn()
    monkeypatch.setattr(routes_hls, "_session", fake)
    monkeypatch.setattr(routes_hls, "_PLAYLIST_CACHE", {})
    monkeypatch.setattr(routes_hls, "_BREAKER", routes_hls._Breaker())
    monkeypatch.setattr(routes_hls, "_CACHE", routes_hls._SingleFlightCache(
        routes_hls.CACHE_MAX_BYTES, routes_hls.CACHE_TTL_S))
    monkeypatch.setattr(routes_hls, "_PLAYLIST_GAP_S", 0.0)  # pacing has its own test
    monkeypatch.setattr(routes_hls, "_CDN_SERVED", {})
    # a deterministic live window (the /seg allow-list depends on it)
    monkeypatch.setattr(routes_hls.timeline, "live_position", lambda now: POSITION_S)
    return fake


@pytest.fixture()
def fake_mtx(monkeypatch):
    fake = FakeMtx()
    monkeypatch.setenv("SENTINEL_MEDIAMTX_HLS_PORT", str(MTX_PORT))
    monkeypatch.setattr(routes_hls, "_mtx_fetch", fake)
    monkeypatch.setattr(routes_hls, "_MTX_ALLOWED", type(routes_hls._MTX_ALLOWED)())
    monkeypatch.setattr(routes_hls, "_mtx_up", lambda: not fake.down)
    return fake


@pytest.fixture()
def client(tmp_path, monkeypatch, fake_cdn, fake_mtx):
    """Per-test DB with an HLS camera, a sandbox RTSP camera (catalogue,
    no hls_url), a local mediamtx feed, a replay camera and an off-origin
    row; the tee root pointed at a temp dir."""
    monkeypatch.setenv("SENTINEL_DB", str(tmp_path / "relay.db"))
    monkeypatch.setenv("SENTINEL_HLS_DIR", str(tmp_path / "hls"))
    con = dbmod.connect()
    dbmod.migrate(con)
    now = dbmod.utcnow()
    rows = [
        # camera_id, transport, hls_url, rtsp_url_template, source
        ("hlscam", "hls", f"{config.cdn()}/hls/hlscam/index.m3u8", None, "catalogue"),
        ("rtspcam", "rtsp", None, None, "catalogue"),
        ("localcam", "rtsp", None, "rtsp://localhost:8554/stream/local05", "manual"),
        ("replaycam", "replay", None, "tests/fixtures/synthetic_60s.mp4", "manual"),
        ("evilcam", "hls", "https://evil.example/hls/index.m3u8", None, "catalogue"),
    ]
    for camera_id, transport, hls_url, template, source in rows:
        con.execute(
            "INSERT INTO cameras (camera_id, transport, hls_url, rtsp_url_template, source,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (camera_id, transport, hls_url, template, source, now, now),
        )
    con.execute(
        "INSERT INTO users (username, password_hash, role, active, created_at)"
        " VALUES ('vic', ?, 'viewer', 1, ?)",
        (passwords.hash_password("relay-Passw0rd"), now),
    )
    con.commit()
    con.close()
    with TestClient(main_mod.create_app(), base_url="http://localhost") as c:
        yield c


def _write_tee(camera_id: str, age_s: float = 0.0) -> None:
    d = config.hls_dir() / camera_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "seg000001.ts").write_bytes(b"LOCALTS")
    idx = d / "index.m3u8"
    idx.write_text(
        "#EXTM3U\n#EXT-X-VERSION:6\n#EXT-X-TARGETDURATION:3\n"
        "#EXT-X-MEDIA-SEQUENCE:1\n#EXTINF:2.0,\nseg000001.ts\n",
        encoding="utf-8",
    )
    if age_s:
        past = time.time() - age_s
        os.utime(idx, (past, past))


def _uris(body: str) -> list[str]:
    return [ln for ln in body.splitlines() if ln and not ln.startswith("#")]


# ----------------------------------------------------------- the CDN window

def test_relay_rewrites_a_sliding_window(client, fake_cdn) -> None:
    r = client.get("/api/hls/hlscam/live.m3u8", headers=VIEWER)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.apple.mpegurl")
    assert r.headers["x-sentinel-source"] == "cdn"
    body = r.text
    uris = _uris(body)
    assert uris and all(u.startswith("/api/hls/hlscam/seg/") for u in uris)
    assert len(uris) == 10  # WINDOW_S 60 / 6 s segments
    assert '#EXT-X-KEY:METHOD=AES-128,URI="/api/hls/hlscam/key"' in body
    assert "cctv.corp8.cloud" not in body and "evil.example" not in body
    # The playlist is cached: a second request adds no CDN fetch.
    calls = len(fake_cdn.calls)
    assert client.get("/api/hls/hlscam/live.m3u8", headers=VIEWER).status_code == 200
    assert len(fake_cdn.calls) == calls


def test_segment_only_from_the_playlist_and_only_on_origin(client, fake_cdn) -> None:
    """B11: /seg/{name} proxies playlist-listed names only; the off-origin
    playlist entry and any invented name are refused. (Since 25 Sep only
    names of the live window just served — see the window test below.)"""
    assert client.get("/api/hls/hlscam/live.m3u8", headers=VIEWER).status_code == 200
    ok = client.get("/api/hls/hlscam/seg/seg00003.ts", headers=VIEWER)
    assert ok.status_code == 200
    assert ok.content.startswith(b"TSDATA:")
    assert ok.headers["content-type"] == "video/mp2t"

    assert client.get("/api/hls/hlscam/seg/evil.ts", headers=VIEWER).status_code == 403
    # leak.ts appears in the upstream playlist ONLY as an absolute
    # off-origin URI — never servable by bare name.
    assert client.get("/api/hls/hlscam/seg/leak.ts", headers=VIEWER).status_code == 403
    # Traversal-shaped names never reach a fetch (the client normalises
    # dot segments away, so ".." either 404s on the collapsed path or is
    # refused as off-playlist — never fetched either way).
    assert client.get("/api/hls/hlscam/seg/..", headers=VIEWER).status_code in (403, 404)
    assert not any("evil" in u or ".." in u for u in fake_cdn.calls)


def test_off_origin_camera_playlist_is_refused(client, fake_cdn) -> None:
    """A registry row pointing outside the configured CDN origin is refused
    before any fetch (B11: only inside the CDN origin)."""
    r = client.get("/api/hls/evilcam/live.m3u8", headers=VIEWER)
    assert r.status_code == 403
    assert not any("evil.example" in u for u in fake_cdn.calls)


def test_key_is_proxied_and_must_be_16_bytes(client, fake_cdn) -> None:
    """The key is proxied from inside the CDN origin and must be 16 bytes.
    (Since 25 Sep a good key sits in the relay's memory cache for ≤ 120 s,
    so the bad-key half clears that cache first — a short key is never
    cached, the check runs before the cache stores anything. Since 25 Sep
    the key, like /seg, follows a served window.)"""
    assert client.get("/api/hls/hlscam/live.m3u8", headers=VIEWER).status_code == 200
    r = client.get("/api/hls/hlscam/key", headers=VIEWER)
    assert r.status_code == 200
    assert r.content == KEY_16
    assert r.headers["cache-control"] == "no-store"

    routes_hls._CACHE.clear()
    fake_cdn.key = b"short"
    r = client.get("/api/hls/hlscam/key", headers=VIEWER)
    assert r.status_code == 502
    assert "16-byte" in r.json()["detail"]
    assert routes_hls._CACHE.size == 0


def test_cdn_segment_outside_the_served_window_is_refused(client, fake_cdn, monkeypatch) -> None:
    """Regression (25 Sep review, root rule 6): /seg/{name} checked only
    that a name was SOMEWHERE in the 12 h upstream VOD, so any signed-in
    viewer could walk seg00000..seg07199 of every sandbox camera through
    the backend's CDN session — a footage download proxy, and the burst
    that earns the account a ban. Only the live window actually served
    (plus one window of grace for a request racing the next reload) is
    fetched; nothing else ever reaches the CDN."""
    fake_cdn.playlist = VOD_12H
    position = [4909 * 6.0 + 1.0]  # live edge in segment 4909
    monkeypatch.setattr(routes_hls.timeline, "live_position", lambda now: position[0])

    r = client.get("/api/hls/rtspcam/live.m3u8", headers=VIEWER)
    assert r.status_code == 200
    served = [u.rsplit("/", 1)[1] for u in _uris(r.text)]
    assert served == [f"seg{i:05d}.ts" for i in range(4900, 4910)]
    before = list(fake_cdn.calls)
    for name in ("seg00000.ts", "seg03600.ts", "seg07199.ts", "seg04910.ts", "seg04889.ts"):
        r = client.get(f"/api/hls/rtspcam/seg/{name}", headers=VIEWER)
        assert r.status_code == 403, name
    assert fake_cdn.calls == before  # nothing outside the window was fetched upstream
    # the window itself, and the one before it (a request racing the reload)
    for name in ("seg04900.ts", "seg04909.ts", "seg04890.ts"):
        assert client.get(f"/api/hls/rtspcam/seg/{name}", headers=VIEWER).status_code == 200, name

    # the loop point: just after the wrap, the window before it is the grace
    position[0] = 1.0
    served = [u.rsplit("/", 1)[1]
              for u in _uris(client.get("/api/hls/rtspcam/live.m3u8", headers=VIEWER).text)]
    assert served == [f"seg{i:05d}.ts" for i in range(10)]
    for name, code in (("seg07199.ts", 200), ("seg07190.ts", 200), ("seg00009.ts", 200),
                       ("seg07189.ts", 403), ("seg00010.ts", 403)):
        assert client.get(f"/api/hls/rtspcam/seg/{name}", headers=VIEWER).status_code == code, name

    # a camera whose CDN window was never handed to anyone: no segment, no
    # key, and no upstream fetch at all (e.g. an analysed camera on its tee)
    assert client.get("/api/hls/hlscam/seg/seg04905.ts", headers=VIEWER).status_code == 403
    assert client.get("/api/hls/hlscam/key", headers=VIEWER).status_code == 403
    assert not any("/hlscam/" in u for u in fake_cdn.calls)


def test_cdn_redirect_off_origin_never_reaches_the_viewer(client, monkeypatch) -> None:
    """Regression (25 Sep review): the relay's CDN session followed a 3xx
    to any host and /seg returned whatever came back. With the real
    CdnSession on a mock CDN that redirects a segment off-origin, the
    viewer gets a 503 and the foreign host is never contacted."""
    import httpx

    from backend.core.cdn_session import CdnSession

    monkeypatch.setenv("SENTINEL_EMAIL", "tester@example.invalid")
    monkeypatch.setenv("SENTINEL_PASSWORD", "not-a-real-password")
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.host == "evil.example":
            return httpx.Response(200, content=b"INTERNAL-SECRET")
        if request.url.path == "/auth/login":
            return httpx.Response(200, headers={"set-cookie": "s=1; Path=/"})
        if request.url.path.endswith(".m3u8"):
            return httpx.Response(200, content=PLAYLIST.encode())
        return httpx.Response(302, headers={"location": "http://evil.example/leak.ts"})

    monkeypatch.setattr(routes_hls, "_session", CdnSession(transport=httpx.MockTransport(handler)))
    assert client.get("/api/hls/hlscam/live.m3u8", headers=VIEWER).status_code == 200
    r = client.get("/api/hls/hlscam/seg/seg00003.ts", headers=VIEWER)
    assert r.status_code == 503
    assert b"INTERNAL-SECRET" not in r.content
    assert not any("evil.example" in u for u in seen), seen


# ------------------------------------------------------------- the local tee

def test_fresh_tee_is_served_instead_of_the_cdn(client, fake_cdn) -> None:
    """C7: the wall shows the worker's own pull; no CDN call is made."""
    _write_tee("hlscam")
    r = client.get("/api/hls/hlscam/live.m3u8", headers=VIEWER)
    assert r.status_code == 200
    assert r.headers["x-sentinel-source"] == "tee"
    assert "/api/hls/hlscam/local/seg000001.ts" in r.text
    assert fake_cdn.calls == []

    seg = client.get("/api/hls/hlscam/local/seg000001.ts", headers=VIEWER)
    assert seg.status_code == 200 and seg.content == b"LOCALTS"
    gone = client.get("/api/hls/hlscam/local/seg999999.ts", headers=VIEWER)
    assert gone.status_code == 404


def test_stale_tee_older_than_120s_falls_to_the_cdn(client, fake_cdn) -> None:
    """A tee older than STALE_TEE_MAX_S (120 s) no longer represents the
    live pull, so the camera drops to the CDN relay. (Was 100 s under the
    old 20 s gate; 100 s is now inside the stale-tee grace, so the test
    ages the tee past 120 s instead.)"""
    _write_tee("hlscam", age_s=200.0)
    r = client.get("/api/hls/hlscam/live.m3u8", headers=VIEWER)
    assert r.status_code == 200
    assert r.headers["x-sentinel-source"] == "cdn"
    assert "/seg/" in r.text and "/local/" not in r.text
    assert fake_cdn.calls  # the upstream playlist was fetched


def test_stale_tee_younger_than_120s_is_kept(client, fake_cdn) -> None:
    """An analysed camera's brief worker hiccup must not flip the tile to
    another source: a 20-120 s old tee keeps serving its last seconds."""
    _write_tee("rtspcam", age_s=100.0)
    r = client.get("/api/hls/rtspcam/live.m3u8", headers=VIEWER)
    assert r.status_code == 200
    assert r.headers["x-sentinel-source"] == "stale-tee"
    assert "/api/hls/rtspcam/local/" in r.text
    assert fake_cdn.calls == []


def test_sandbox_rtsp_camera_falls_to_the_cdn_without_a_tee(client, fake_cdn) -> None:
    """Replaces ``test_rtsp_camera_never_falls_to_the_cdn`` (25 Sep): the
    five analysed cameras' workers hold five of the gateway's ~6 RTSP
    sessions (docs/sandbox-findings.md §3), so for the other 25 sandbox
    cameras the organisers' CDN copy — relayed once — is the only viewing
    path that keeps one pull per camera (rule 2). A catalogue camera with
    no ``hls_url`` uses the sandbox's documented ``{cdn}/<id>/index.m3u8``."""
    r = client.get("/api/hls/rtspcam/live.m3u8", headers=VIEWER)
    assert r.status_code == 200
    assert r.headers["x-sentinel-source"] == "cdn"
    assert _uris(r.text)[0].startswith("/api/hls/rtspcam/seg/")
    assert fake_cdn.calls == [f"{config.cdn()}/rtspcam/index.m3u8"]


def test_camera_with_no_source_answers_404_without_any_fetch(client, fake_cdn, fake_mtx) -> None:
    """A replay (file) camera has no tee, no local feed and no CDN copy."""
    r = client.get("/api/hls/replaycam/live.m3u8", headers=VIEWER)
    assert r.status_code == 404
    assert r.json()["detail"] == "no-live-source"
    assert fake_cdn.calls == [] and fake_mtx.urls == []


# ------------------------------------------------------------ mediamtx feeds

def test_local_feed_is_proxied_from_mediamtx_hls(client, fake_cdn, fake_mtx) -> None:
    """A local feed without a tee: mediamtx's multivariant index, child
    playlist and segments come through the relay with every URI rewritten
    to /api/hls/{cam}/mtx/{name}; the upstream host is pinned to 127.0.0.1
    and the port is config's HLS port, not the stored RTSP port."""
    r = client.get("/api/hls/localcam/live.m3u8", headers=VIEWER)
    assert r.status_code == 200
    assert r.headers["x-sentinel-source"] == "mediamtx"
    assert r.headers["cache-control"] == "no-store"
    child = _uris(r.text)
    assert child == [f"/api/hls/localcam/mtx/main_stream.m3u8?session={MTX_SESSION}"]
    assert "CODECS=\"avc1.640028\"" in r.text

    c = client.get(child[0], headers=VIEWER)
    assert c.status_code == 200
    assert c.headers["x-sentinel-source"] == "mediamtx"
    segs = _uris(c.text)
    assert segs == [
        f"/api/hls/localcam/mtx/a78525e1f86d_main_seg0.ts?session={MTX_SESSION}",
        f"/api/hls/localcam/mtx/a78525e1f86d_main_seg1.ts?session={MTX_SESSION}",
    ]
    s = client.get(segs[1], headers=VIEWER)
    assert s.status_code == 200
    assert s.headers["content-type"] == "video/mp2t"
    assert s.content.startswith(b"MTXTS:")
    # the child playlist stays reloadable
    assert client.get(child[0], headers=VIEWER).status_code == 200

    base = f"http://127.0.0.1:{MTX_PORT}/stream/local05/"
    assert fake_mtx.urls and all(u.startswith(base) for u in fake_mtx.urls)
    assert fake_mtx.urls[0] == base + "index.m3u8"
    assert fake_cdn.calls == []


def test_mediamtx_allow_list_refuses_unlisted_names(client, fake_mtx) -> None:
    """Only names listed in the playlist last fetched for that mediamtx
    session are proxied — an invented name, another session's name or a
    name before any playlist was fetched never reaches mediamtx."""
    seg0 = f"/api/hls/localcam/mtx/a78525e1f86d_main_seg0.ts?session={MTX_SESSION}"
    assert client.get(seg0, headers=VIEWER).status_code == 403  # nothing fetched yet
    assert fake_mtx.urls == []

    client.get("/api/hls/localcam/live.m3u8", headers=VIEWER)
    client.get(f"/api/hls/localcam/mtx/main_stream.m3u8?session={MTX_SESSION}", headers=VIEWER)
    fetched = len(fake_mtx.urls)
    refused = [
        f"/api/hls/localcam/mtx/other_seg9.ts?session={MTX_SESSION}",
        "/api/hls/localcam/mtx/a78525e1f86d_main_seg0.ts?session=another-session",
        "/api/hls/localcam/mtx/a78525e1f86d_main_seg0.ts",
    ]
    for url in refused:
        assert client.get(url, headers=VIEWER).status_code == 403, url
    assert client.get(
        "/api/hls/localcam/mtx/seg.ts?session=bad%2Fsession", headers=VIEWER
    ).status_code == 400
    # a non-local camera has no mediamtx path at all
    assert client.get(
        f"/api/hls/rtspcam/mtx/main_stream.m3u8?session={MTX_SESSION}", headers=VIEWER
    ).status_code == 404
    assert len(fake_mtx.urls) == fetched
    assert client.get(seg0, headers=VIEWER).status_code == 200


def test_mediamtx_playlist_with_an_absolute_uri_is_refused(client, fake_mtx) -> None:
    """An absolute or path-carrying URI from upstream is never rewritten
    into something the relay would fetch (B11 applied to mediamtx)."""
    fake_mtx.index = "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1\nhttp://evil.example/x.m3u8\n"
    r = client.get("/api/hls/localcam/live.m3u8", headers=VIEWER)
    assert r.status_code == 502
    assert "evil.example" not in r.text


def test_mediamtx_down_or_not_publishing_is_a_clear_503(client, fake_mtx) -> None:
    fake_mtx.down = True
    r = client.get("/api/hls/localcam/live.m3u8", headers=VIEWER)
    assert r.status_code == 503
    assert r.json()["detail"] == "local feed server not running"

    fake_mtx.down = False
    fake_mtx.status = 404  # mediamtx: "no stream is available on path"
    r = client.get("/api/hls/localcam/live.m3u8", headers=VIEWER)
    assert r.status_code == 503
    assert r.json()["detail"] == "local feed not publishing"


def test_mediamtx_cookie_check_redirect_is_followed_on_loopback_only() -> None:
    """Regression (found by the real-browser smoke, 25 Sep): mediamtx
    v1.21.1 answers a cookie-less first request with ``302`` to
    ``?cookieCheck=1`` and an empty body; the relay fetched with redirects
    off and handed hls.js an empty 200 "playlist" (manifestParsingError).
    The redirect is now followed — but only on the same loopback origin."""
    import httpx

    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if "cookieCheck" not in str(request.url):
            return httpx.Response(302, headers={
                "location": "/stream/local02/index.m3u8?cookieCheck=1",
                "set-cookie": "cookieCheck=1; HttpOnly; Secure; SameSite=None"})
        return httpx.Response(200, content=MTX_INDEX.encode())

    url = "http://127.0.0.1:18888/stream/local02/index.m3u8"
    status, body = routes_hls._mtx_fetch(url, 2.0, transport=httpx.MockTransport(handler))
    assert status == 200 and body.startswith(b"#EXTM3U")
    assert seen == [url, url + "?cookieCheck=1"]

    def off_origin(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://evil.example/x.m3u8"})

    status, body = routes_hls._mtx_fetch(url, 2.0, transport=httpx.MockTransport(off_origin))
    assert status == 502 and body == b""


def test_empty_mediamtx_answer_is_a_502_not_an_empty_playlist(client, fake_mtx) -> None:
    """The other half of the cookieCheck regression: whatever mediamtx
    answers, the relay never serves a 200 that is not a playlist."""
    fake_mtx.index = ""
    r = client.get("/api/hls/localcam/live.m3u8", headers=VIEWER)
    assert r.status_code == 502
    assert r.json()["detail"] == "local feed server returned no playlist"


def test_fresh_tee_beats_mediamtx_for_an_analysed_local_feed(client, fake_mtx) -> None:
    _write_tee("localcam")
    r = client.get("/api/hls/localcam/live.m3u8", headers=VIEWER)
    assert r.status_code == 200
    assert r.headers["x-sentinel-source"] == "tee"
    assert fake_mtx.urls == []


# ------------------------------------------------- CDN cache and back-off

def test_concurrent_viewers_of_one_segment_cost_one_upstream_fetch(client, fake_cdn) -> None:
    """N tiles (or N browsers) asking for the same CDN segment at once wait
    on ONE upstream fetch; a later request is served from memory."""
    client.get("/api/hls/hlscam/live.m3u8", headers=VIEWER)  # warm the playlist
    fake_cdn.segment_delay_s = 0.3
    results: list[bytes] = []
    errors: list[BaseException] = []

    def fetch() -> None:
        try:
            results.append(routes_hls.hls_segment("hlscam", "seg00007.ts", "vic", None).body)
        except BaseException as exc:  # noqa: BLE001 - surfaced by the assert below
            errors.append(exc)

    threads = [threading.Thread(target=fetch) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert not errors
    assert len(results) == 8 and len(set(results)) == 1
    seg_calls = [u for u in fake_cdn.calls if u.endswith("seg00007.ts")]
    assert len(seg_calls) == 1

    again = client.get("/api/hls/hlscam/seg/seg00007.ts", headers=VIEWER)
    assert again.status_code == 200
    assert len([u for u in fake_cdn.calls if u.endswith("seg00007.ts")]) == 1


def test_segment_cache_is_bounded_by_bytes_and_ttl(monkeypatch) -> None:
    cache = routes_hls._SingleFlightCache(max_bytes=10, ttl_s=120.0)
    for key in ("a", "b", "c"):
        assert cache.get_or_fetch(key, lambda k=key: k.encode() * 4) == key.encode() * 4
    assert cache.size <= 10
    fetched: list[str] = []
    cache.get_or_fetch("a", lambda: fetched.append("a") or b"aaaa")  # evicted -> refetched
    assert fetched == ["a"]

    clock = [1000.0]
    monkeypatch.setattr(routes_hls.time, "monotonic", lambda: clock[0])
    ttl = routes_hls._SingleFlightCache(max_bytes=100, ttl_s=120.0)
    ttl.get_or_fetch("k", lambda: b"one")
    clock[0] += 121.0
    assert ttl.get_or_fetch("k", lambda: b"two") == b"two"


def test_cdn_refusal_answers_503_and_backs_off(client, fake_cdn) -> None:
    """A refused CDN (403 ban / timeout) is a 503 with a machine-readable
    detail, and the relay then backs off (root rule 7) — the next request
    is answered without contacting the CDN at all."""
    fake_cdn.error = CdnError("gave up after 2 attempts", status=403)
    r = client.get("/api/hls/rtspcam/live.m3u8", headers=VIEWER)
    assert r.status_code == 503
    assert r.json()["detail"] == "cdn-unavailable"
    calls = len(fake_cdn.calls)

    r = client.get("/api/hls/hlscam/live.m3u8", headers=VIEWER)
    assert r.status_code == 503
    assert r.json()["detail"] == "cdn-backoff"
    assert int(r.headers["retry-after"]) >= 1
    assert len(fake_cdn.calls) == calls

    src = client.get("/api/hls/rtspcam/source", headers=VIEWER).json()
    assert src["source"] == "cdn" and "backing off" in src["detail"]


def test_unproven_cdn_gets_one_probe_not_a_burst(client, fake_cdn) -> None:
    """Regression (found by the frontend smoke, 25 Sep): a wall opening
    against a refusing CDN sent one login per tile at once — four
    concurrent failures, and the back-off ladder climbed four rungs in one
    episode. Until the CDN has answered, ONE request probes it; the others
    wait for that verdict and back off without touching the CDN."""
    fake_cdn.error = CdnError("gave up", status=403)
    fake_cdn.error_delay_s = 0.3
    codes: list[str] = []
    lock = threading.Lock()

    def fetch(i: int) -> None:
        try:
            routes_hls._cdn_get(f"{config.cdn()}/cam{i:02d}/index.m3u8")
        except HTTPException as exc:
            with lock:
                codes.append(exc.detail)

    threads = [threading.Thread(target=fetch, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)
    assert len(fake_cdn.calls) == 1
    assert sorted(codes) == ["cdn-backoff"] * 5 + ["cdn-unavailable"]
    assert routes_hls._BREAKER.failures == 1


def test_one_episode_of_concurrent_failures_counts_once() -> None:
    breaker = routes_hls._Breaker()
    breaker.fail("cdn-unavailable")
    breaker.fail("cdn-unavailable")  # a racing request of the same episode
    assert breaker.failures == 1


def test_expired_playlist_keeps_serving_when_the_refresh_fails(client, fake_cdn) -> None:
    """The VOD playlist is refreshed every ~10 min; a refresh that fails
    (or is still in flight) must not stall a playing tile — the cached copy
    keeps serving the window and the segment allow-list."""
    assert client.get("/api/hls/rtspcam/live.m3u8", headers=VIEWER).status_code == 200
    fetched_at, text, url, names = routes_hls._PLAYLIST_CACHE["rtspcam"]
    routes_hls._PLAYLIST_CACHE["rtspcam"] = (fetched_at - 3600, text, url, names)
    fake_cdn.error = CdnError("gave up", status="timeout")
    r = client.get("/api/hls/rtspcam/live.m3u8", headers=VIEWER)
    assert r.status_code == 200 and r.headers["x-sentinel-source"] == "cdn"
    assert _uris(r.text)[0].startswith("/api/hls/rtspcam/seg/")

    # while another request holds the refresh, the stale copy answers at once
    lock = routes_hls._playlist_lock("rtspcam")
    with lock:
        calls = len(fake_cdn.calls)
        text2, _base, names2 = routes_hls._upstream_playlist("rtspcam", url)
        assert text2 == text and names2 == names
        assert len(fake_cdn.calls) == calls


def test_upstream_playlist_fetches_are_paced(client, fake_cdn, monkeypatch) -> None:
    """A wall opening on several CDN cameras starts their ~215 KB VOD
    playlist fetches one per gap, never all at once."""
    monkeypatch.setattr(routes_hls, "_PLAYLIST_GAP_S", 0.4)
    monkeypatch.setattr(routes_hls, "_last_playlist_fetch", 0.0)
    t0 = time.monotonic()
    assert client.get("/api/hls/rtspcam/live.m3u8", headers=VIEWER).status_code == 200
    assert client.get("/api/hls/hlscam/live.m3u8", headers=VIEWER).status_code == 200
    assert time.monotonic() - t0 >= 0.4
    assert len([u for u in fake_cdn.calls if u.endswith(".m3u8")]) == 2


def test_open_breaker_never_queues_behind_the_playlist_pacer(client, fake_cdn, monkeypatch) -> None:
    """Regression (25 Sep review): the 1.5 s playlist pacer ran BEFORE the
    breaker check, so while the CDN was refusing us every playlist request
    for an uncached camera still slept its turn in the pacing queue (N x
    1.5 s on a threadpool thread) only to get 503 — a queue that starves
    anyio's 40 threads and with them login and the route query. An open
    breaker now answers at once, and one that opens while requests queue
    releases them without their sleeps."""
    monkeypatch.setattr(routes_hls, "_PLAYLIST_GAP_S", 1.0)
    monkeypatch.setattr(routes_hls, "_last_playlist_fetch", time.monotonic())  # a fetch just began
    routes_hls._BREAKER.open_until = time.monotonic() + 30.0  # the CDN is refusing us
    results: list[tuple[int, str, float]] = []
    lock = threading.Lock()

    def playlist(i: int) -> None:
        t0 = time.monotonic()
        try:
            routes_hls._upstream_playlist(f"cam{i:02d}", f"{config.cdn()}/cam{i:02d}/index.m3u8")
        except HTTPException as exc:
            with lock:
                results.append((exc.status_code, exc.detail, time.monotonic() - t0))

    threads = [threading.Thread(target=playlist, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)
    assert [r[:2] for r in results] == [(503, "cdn-backoff")] * 4
    assert max(r[2] for r in results) < 0.5, results
    assert fake_cdn.calls == []

    # the breaker opens while two requests wait behind a paced fetch
    monkeypatch.setattr(routes_hls, "_BREAKER", routes_hls._Breaker())
    monkeypatch.setattr(routes_hls, "_last_playlist_fetch", time.monotonic())
    pacer = threading.Thread(target=routes_hls._pace_playlist_fetch)  # sleeps ~1 s
    pacer.start()
    time.sleep(0.1)
    routes_hls._BREAKER.open_until = time.monotonic() + 30.0
    queued: list[tuple[str, float]] = []

    def wait_in_queue() -> None:
        t0 = time.monotonic()
        try:
            routes_hls._pace_playlist_fetch()
            outcome = "paced"
        except HTTPException as exc:
            outcome = exc.detail
        with lock:
            queued.append((outcome, time.monotonic() - t0))

    waiters = [threading.Thread(target=wait_in_queue) for _ in range(2)]
    for t in waiters:
        t.start()
    for t in [pacer, *waiters]:
        t.join(timeout=15)
    assert [q[0] for q in queued] == ["cdn-backoff"] * 2
    assert max(q[1] for q in queued) < 1.5, queued  # not 2 s and 3 s of sleeps


def test_cdn_login_failure_is_named(client, fake_cdn) -> None:
    fake_cdn.error = CdnError("login refused: HTTP 403", status="login")
    r = client.get("/api/hls/rtspcam/live.m3u8", headers=VIEWER)
    assert r.status_code == 503
    assert r.json()["detail"] == "cdn-login-failed"


# ------------------------------------------------------------ /source

def test_source_endpoint_names_the_path_taken(client, fake_cdn, fake_mtx) -> None:
    def source(cam: str) -> dict:
        r = client.get(f"/api/hls/{cam}/source", headers=VIEWER)
        assert r.status_code == 200
        body = r.json()
        assert set(body) == {"camera_id", "source", "detail"}
        assert body["camera_id"] == cam and body["detail"]
        return body

    assert source("rtspcam")["source"] == "cdn"
    assert source("localcam")["source"] == "mediamtx"
    assert source("replaycam")["source"] == "none"
    _write_tee("hlscam")
    assert source("hlscam")["source"] == "tee"
    _write_tee("rtspcam", age_s=60.0)
    assert source("rtspcam")["source"] == "stale-tee"
    fake_mtx.down = True
    assert source("localcam")["detail"] == "local feed server not running"
    # /source never touches an upstream
    assert fake_cdn.calls == [] and fake_mtx.urls == []

    assert client.get("/api/hls/nosuch/source", headers=VIEWER).status_code == 404
    assert client.get("/api/hls/rtspcam/source").status_code == 401


def test_source_endpoint_declares_its_response_model(client) -> None:
    spec = client.get("/openapi.json", headers=VIEWER).json()
    op = spec["paths"]["/api/hls/{camera_id}/source"]["get"]
    ref = op["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("/HlsSourceOut")
    props = spec["components"]["schemas"]["HlsSourceOut"]["properties"]
    assert set(props) == {"camera_id", "source", "detail"}
    assert set(props["source"]["enum"]) == {"tee", "stale-tee", "mediamtx", "cdn", "none"}


# ------------------------------------------------------------------ auth, 429

def test_every_relay_path_accepts_header_and_both_cookies(client) -> None:
    """docs/api.md §7: header, sentinel_key cookie (GET media transport)
    and sentinel_session cookie all reach the relay; nothing anonymous."""
    _write_tee("hlscam")
    assert client.get("/api/hls/hlscam/live.m3u8").status_code == 401
    assert client.get("/api/hls/hlscam/local/seg000001.ts").status_code == 401
    assert client.get("/api/hls/localcam/mtx/main_stream.m3u8").status_code == 401

    header = client.get("/api/hls/hlscam/live.m3u8", headers=VIEWER)
    assert header.status_code == 200

    with_key_cookie = TestClient(client.app, base_url="http://localhost")
    r = with_key_cookie.post("/api/session", json={"api_key": VIEWER["X-API-Key"]})
    assert r.status_code == 200
    assert with_key_cookie.get("/api/hls/hlscam/live.m3u8").status_code == 200

    with_session = TestClient(client.app, base_url="http://localhost")
    r = with_session.post(
        "/api/auth/login", json={"username": "vic", "password": "relay-Passw0rd"}
    )
    assert r.status_code == 200
    assert with_session.get("/api/hls/hlscam/live.m3u8").status_code == 200
    assert with_session.get("/api/hls/hlscam/local/seg000001.ts").status_code == 200
    assert with_session.get("/api/hls/hlscam/source").status_code == 200


def test_relay_rate_limit_answers_429(client, monkeypatch) -> None:
    """docs/api.md §9: the relay is rate-limited per identity."""
    _write_tee("hlscam")
    limiter = routes_hls._limit_hls
    monkeypatch.setattr(limiter, "limit", 2)
    monkeypatch.setattr(limiter, "_hits", {})
    codes = [
        client.get("/api/hls/hlscam/live.m3u8", headers=VIEWER).status_code
        for _ in range(3)
    ]
    assert codes == [200, 200, 429]


def test_relay_limit_fits_a_16_tile_wall() -> None:
    """docs/api.md §9 arithmetic: 16 tiles x (30 segments + up to 60
    playlist reloads)/min for 2 s segments = 1,440/min worst case; the
    limit is ~2x that for retries and a second tab. The old 600/min would
    429 a 9-tile wall of 2 s feeds within the first minute."""
    tiles, seg_s = 16, 2.0
    worst_per_tile = 60 / seg_s + 2 * 60 / seg_s  # segments + half-target reloads
    assert routes_hls._limit_hls.window_s == 60.0
    assert routes_hls._limit_hls.limit == 3000
    assert routes_hls._limit_hls.limit >= 2 * tiles * worst_per_tile


def test_breaker_raises_http_exception_with_retry_after() -> None:
    breaker = routes_hls._Breaker()
    breaker.check()  # closed: no exception
    breaker.fail("cdn-unavailable")
    with pytest.raises(HTTPException) as exc:
        breaker.check()
    assert exc.value.status_code == 503 and exc.value.detail == "cdn-backoff"
    breaker.ok()
    breaker.check()


def test_local_segment_path_traversal_cannot_read_the_database(client, tmp_path):
    """Regression (25 Sep review gate, CRITICAL): _SAFE_NAME admitted '..'
    and uvicorn percent-decodes the path, so /api/hls/%2E%2E/local/<file>
    read any file beside the tee root — data/sentinel.db with its raw
    session ids — with any viewer credential. The tee layout here is the
    production one: relay.db sits beside the hls/ folder."""
    assert (tmp_path / "relay.db").exists()
    for cam in ("%2E%2E", "%2e%2e", ".."):
        r = client.get(f"/api/hls/{cam}/local/relay.db", headers=VIEWER)
        assert r.status_code in (400, 404), (cam, r.status_code)
        assert not r.content.startswith(b"SQLite format 3")
    # a real camera id with a non-segment name, or a dotted name, is refused
    for name in ("relay.db", ".hidden.ts", "..", "index.m3u8"):
        r = client.get(f"/api/hls/hlscam/local/{name}", headers=VIEWER)
        assert r.status_code in (400, 404), (name, r.status_code)
    # an unregistered camera id is a 404, never a disk read
    assert client.get("/api/hls/nosuchcam/local/seg000001.ts",
                      headers=VIEWER).status_code == 404
