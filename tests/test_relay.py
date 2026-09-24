"""S3.1b acceptance: the HLS relay (docs/api.md §7 hls row, B11; C7).

The relay serves the worker's local tee when fresh; an RTSP camera never
falls to the CDN (stale tee, then 503); the CDN path rewrites a sliding
window with the key and segment URIs pointed back at the relay; a segment
name not in the upstream playlist and any off-origin URL are refused; the
key must be 16 bytes; header, ``sentinel_key`` cookie and
``sentinel_session`` cookie all authenticate; the relay is rate-limited.
"""

from __future__ import annotations

import os
import time

import pytest
from fastapi.testclient import TestClient

import backend.app.main as main_mod
import backend.app.routes_hls as routes_hls
from backend.core import config, passwords
from backend.core import db as dbmod

ADMIN = {"X-API-Key": "test-admin-key-not-a-secret"}
VIEWER = {"X-API-Key": "test-viewer-key-not-a-secret"}

KEY_16 = b"0123456789abcdef"

#: 24 x 6 s VOD segments, AES key, plus one absolute off-origin URI that
#: must never become servable through /seg/{name}.
PLAYLIST = (
    "#EXTM3U\n#EXT-X-VERSION:6\n#EXT-X-TARGETDURATION:7\n"
    "#EXT-X-PLAYLIST-TYPE:VOD\n"
    '#EXT-X-KEY:METHOD=AES-128,URI="/enc.key",IV=0x00000000000000000000000000000000\n'
    + "".join(f"#EXTINF:6.0,\nseg{i:05d}.ts\n" for i in range(24))
    + "#EXTINF:6.0,\nhttps://evil.example/leak.ts\n#EXT-X-ENDLIST\n"
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

    def get(self, url: str) -> FakeResponse:
        self.calls.append(url)
        assert url.startswith(config.cdn()), f"relay fetched outside the CDN: {url}"
        if url.endswith(".m3u8"):
            return FakeResponse(self.playlist.encode())
        if url.endswith("enc.key"):
            return FakeResponse(self.key)
        return FakeResponse(b"TSDATA:" + url.encode())


@pytest.fixture()
def fake_cdn(monkeypatch):
    fake = FakeCdn()
    monkeypatch.setattr(routes_hls, "_session", fake)
    monkeypatch.setattr(routes_hls, "_PLAYLIST_CACHE", {})
    return fake


@pytest.fixture()
def client(tmp_path, monkeypatch, fake_cdn):
    """Per-test DB with an HLS camera, an RTSP camera and an off-origin
    row; the tee root pointed at a temp dir."""
    monkeypatch.setenv("SENTINEL_DB", str(tmp_path / "relay.db"))
    monkeypatch.setenv("SENTINEL_HLS_DIR", str(tmp_path / "hls"))
    con = dbmod.connect()
    dbmod.migrate(con)
    now = dbmod.utcnow()
    rows = [
        ("hlscam", "hls", f"{config.cdn()}/hls/hlscam/index.m3u8"),
        ("rtspcam", "rtsp", None),
        ("evilcam", "hls", "https://evil.example/hls/index.m3u8"),
    ]
    for camera_id, transport, hls_url in rows:
        con.execute(
            "INSERT INTO cameras (camera_id, transport, hls_url, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (camera_id, transport, hls_url, now, now),
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


# ----------------------------------------------------------- the CDN window

def test_relay_rewrites_a_sliding_window(client, fake_cdn) -> None:
    r = client.get("/api/hls/hlscam/live.m3u8", headers=VIEWER)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.apple.mpegurl")
    body = r.text
    uris = [ln for ln in body.splitlines() if ln and not ln.startswith("#")]
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
    playlist entry and any invented name are refused."""
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
    r = client.get("/api/hls/hlscam/key", headers=VIEWER)
    assert r.status_code == 200
    assert r.content == KEY_16
    assert r.headers["cache-control"] == "no-store"

    fake_cdn.key = b"short"
    r = client.get("/api/hls/hlscam/key", headers=VIEWER)
    assert r.status_code == 502
    assert "16-byte" in r.json()["detail"]


# ------------------------------------------------------------- the local tee

def test_fresh_tee_is_served_instead_of_the_cdn(client, fake_cdn) -> None:
    """C7: the wall shows the worker's own pull; no CDN call is made."""
    _write_tee("hlscam")
    r = client.get("/api/hls/hlscam/live.m3u8", headers=VIEWER)
    assert r.status_code == 200
    assert "/api/hls/hlscam/local/seg000001.ts" in r.text
    assert fake_cdn.calls == []

    seg = client.get("/api/hls/hlscam/local/seg000001.ts", headers=VIEWER)
    assert seg.status_code == 200 and seg.content == b"LOCALTS"
    gone = client.get("/api/hls/hlscam/local/seg999999.ts", headers=VIEWER)
    assert gone.status_code == 404


def test_stale_tee_falls_to_the_cdn_for_an_hls_camera(client, fake_cdn) -> None:
    """The 20 s freshness gate: a stale tee no longer represents the live
    pull, so an HLS camera drops to the CDN relay."""
    _write_tee("hlscam", age_s=100.0)
    r = client.get("/api/hls/hlscam/live.m3u8", headers=VIEWER)
    assert r.status_code == 200
    assert "/seg/" in r.text and "/local/" not in r.text
    assert fake_cdn.calls  # the upstream playlist was fetched


def test_rtsp_camera_never_falls_to_the_cdn(client, fake_cdn) -> None:
    """An RTSP camera's live view is its own tee: stale tee served through
    a reconnect, 503 without one — the CDN is a different source."""
    _write_tee("rtspcam", age_s=100.0)
    r = client.get("/api/hls/rtspcam/live.m3u8", headers=VIEWER)
    assert r.status_code == 200
    assert "/api/hls/rtspcam/local/" in r.text

    idx = config.hls_dir() / "rtspcam" / "index.m3u8"
    idx.unlink()
    r = client.get("/api/hls/rtspcam/live.m3u8", headers=VIEWER)
    assert r.status_code == 503
    assert fake_cdn.calls == []


# ------------------------------------------------------------------ auth, 429

def test_every_relay_path_accepts_header_and_both_cookies(client) -> None:
    """docs/api.md §7: header, sentinel_key cookie (GET media transport)
    and sentinel_session cookie all reach the relay; nothing anonymous."""
    _write_tee("hlscam")
    assert client.get("/api/hls/hlscam/live.m3u8").status_code == 401
    assert client.get("/api/hls/hlscam/local/seg000001.ts").status_code == 401

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
