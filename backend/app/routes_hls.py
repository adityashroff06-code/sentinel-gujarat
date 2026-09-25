"""HLS relay — Pipeline 1 live view (relay only, stores nothing).

Ported from ``D:\\projects\\Sentinel_Repo\\src\\api\\routes_hls.py`` (F52)
and adapted to this repo's contract (docs/api.md §7 hls row, B11; decisions
C7, F41). Every camera in the registry plays on the wall through this one
relay; the browser never talks to an upstream. Per camera, in order:

1. **tee** — the analytics worker's stream-copied local HLS window (one
   pull per camera, C7), served when fresh (< 20 s) and rewritten to
   ``/local/{seg}``.
2. **mediamtx** — a LOCAL feed (``rtsp_url_template`` on 127.0.0.1 /
   localhost, e.g. ``rtsp://127.0.0.1:8554/stream/local05``) without a
   fresh tee: mediamtx's own HLS server at
   ``http://127.0.0.1:{config.mediamtx_hls_port()}/{path}/`` is proxied.
   Child-playlist and segment URIs are rewritten to
   ``/api/hls/{cam}/mtx/{name}``; only names present in the playlist last
   fetched for that viewer's mediamtx session are proxied; the upstream
   host is pinned to 127.0.0.1 whatever the stored URL says (and the RTSP
   port is irrelevant — the HLS port comes from config).
3. **stale-tee** — a sandbox camera whose tee is between 20 s and 120 s
   old keeps its last good seconds, so an analysed camera's brief
   reconnect never flips the tile to a different source.
4. **cdn** — any other sandbox camera: a **sliding window** of the
   organisers' CDN VOD playlist at the shared-timeline position
   (``backend/core/timeline.py``), segment URLs rewritten to
   ``/seg/{name}`` and the AES key URI to ``/key``.

**Why sandbox cameras now fall to the CDN** (this replaces the earlier
"an RTSP camera never falls to the CDN" rule, 25 Sep): the five analysed
cameras' workers already hold five of the gateway's ~6 RTSP sessions
(docs/sandbox-findings.md §3), so a live-wall pull of any other camera
over RTSP would break rule 2 and starve the workers. The organisers' own
HLS copy, relayed once through this backend, is the only viewing path for
the other 25 that respects one-pull-per-camera. It is a recording on the
shared timeline, and the tile says so ("CDN RECORDING").

- **Input hygiene (B11):** ``/seg/{name}`` proxies only names present in
  the fetched playlist, and every CDN fetch must resolve inside the
  configured CDN origin; ``/key`` requires a 16-byte AES-128 key;
  ``/mtx/{name}`` fetches only from 127.0.0.1 and only listed names.
- **One upstream fetch per segment:** CDN segments and keys go through a
  bounded in-memory single-flight cache (48 MB, 120 s) so N viewers cost
  one CDN request per segment; nothing touches disk (Pipeline 1 stores
  nothing). Upstream VOD playlists are cached ~10 minutes per camera.
- **The CDN rate-limits hard:** short timeouts, two attempts, and a relay
  circuit breaker with jittered exponential backoff (root rule 7) answer
  ``503`` immediately while the CDN is refusing us, instead of every tile
  retrying into a ban.
- **Errors are machine-readable:** ``503`` details ``cdn-backoff``,
  ``cdn-unavailable``, ``cdn-login-failed``, ``cdn-not-configured``,
  ``local feed server not running``, ``local feed not publishing``.
- **Source visibility:** every playlist response carries
  ``X-Sentinel-Source``; ``GET /{camera_id}/source`` says which path the
  next playlist request would take, without touching any upstream.
- Every path accepts header or cookie auth — ``X-API-Key``,
  ``sentinel_session`` and the ``sentinel_key`` media cookie all resolve
  on GET ``/api/hls/*`` (backend/app/auth.py) — and is rate-limited
  (docs/api.md §9 names the relay and gives the wall arithmetic).
"""

from __future__ import annotations

import re
import socket
import sqlite3
import threading
import time
import urllib.parse
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel

from backend.app.auth import RateLimiter, require_auth
from backend.core import config, timeline
from backend.core import db as dbmod
from backend.core.cdn_session import CdnError, CdnSession, backoff_delay
from backend.core.logging_setup import setup

log = setup("hls-relay")

router = APIRouter(prefix="/api/hls", tags=["hls"])

#: Seconds of video behind the live edge (the window of segments served).
WINDOW_S = 60
#: Upstream playlists are static VOD; cache them to spare the rate limiter.
_PLAYLIST_TTL_S = 600
#: The worker's tee is live when younger than this (task S3.1b: < 20 s).
TEE_FRESH_S = 20.0
#: A sandbox camera with a stale tee keeps serving it up to this age, so a
#: worker's brief reconnect never flips the tile to the CDN; older -> CDN.
STALE_TEE_MAX_S = 120.0

#: CDN fetches: per-operation timeout, two attempts (one re-login on 403).
#: 15 s because the CDN answered cam10's playlist in 9.85 s (after a
#: 5.3 s login) on the laptop on 25 Sep — 8 s would time out a healthy CDN.
CDN_TIMEOUT_S = 15.0
CDN_ATTEMPTS = 2
#: The single-flight segment/key cache (memory only — Pipeline 1 stores nothing).
CACHE_MAX_BYTES = 48 * 1024 * 1024
CACHE_TTL_S = 120.0
#: A follower waits this long for the leader's upstream fetch (two
#: attempts at CDN_TIMEOUT_S plus one jittered pause).
_FLIGHT_WAIT_S = 40.0

#: mediamtx: the first index request blocks until the muxer has segments
#: (observed ~4.7 s on v1.21.1 with 2 s segments), so it gets longer.
MTX_INDEX_TIMEOUT_S = 12.0
MTX_TIMEOUT_S = 5.0
#: Per-viewer mediamtx sessions whose allow-list is remembered.
_MTX_SESSION_TTL_S = 120.0
_MTX_MAX_SESSIONS = 512

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")
_SESSION_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")
_MTX_PATH = re.compile(r"^[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-][A-Za-z0-9_.-]*)*$")
_KEY_LINE = re.compile(r'#EXT-X-KEY:METHOD=AES-128,URI="([^"]+)"([^\n]*)')
_SEGMENT = re.compile(r"#EXTINF:([\d.]+)[^\n]*\n(?!#)(\S+)")

_M3U8 = "application/vnd.apple.mpegurl"
_NO_STORE = {"Cache-Control": "no-store"}
_LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost"})

Source = Literal["tee", "stale-tee", "mediamtx", "cdn", "none"]

#: docs/api.md §9: a 16-tile wall is ~1,500 requests/min at worst (2 s
#: segments + playlist reloads on every tile); x2 headroom for retries and
#: a second tab. 429 rather than queueing.
_limit_hls = RateLimiter("hls", limit=3000, window_s=60.0)

_PLAYLIST_RESPONSE = {
    200: {
        "description": "The rewritten HLS playlist (X-Sentinel-Source names the path taken)",
        "content": {_M3U8: {"schema": {"type": "string"}}},
    }
}
_BYTES_RESPONSE = {
    200: {
        "description": "The proxied bytes",
        "content": {
            "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
        },
    }
}
_MTX_RESPONSE = {
    200: {
        "description": "A rewritten child playlist, or the proxied segment bytes",
        "content": {
            _M3U8: {"schema": {"type": "string"}},
            "video/mp2t": {"schema": {"type": "string", "format": "binary"}},
        },
    }
}


class HlsSourceOut(BaseModel):
    """Which path ``/api/hls/{camera_id}/live.m3u8`` takes right now."""

    camera_id: str
    source: Source
    detail: str


# ------------------------------------------------------------- CDN session

_session_lock = threading.Lock()
_session: CdnSession | None = None

#: camera_id -> (fetched_at, playlist_text, base_url, servable segment names)
_PLAYLIST_CACHE: dict[str, tuple[float, str, str, frozenset[str]]] = {}
_playlist_locks: dict[str, threading.Lock] = {}
_playlist_locks_guard = threading.Lock()


def _cdn() -> CdnSession:
    """The one shared CDN session (lazy; tests replace ``_session``)."""
    global _session
    with _session_lock:
        if _session is None:
            _session = CdnSession(timeout_s=CDN_TIMEOUT_S)
        return _session


class _Breaker:
    """Relay-wide CDN circuit breaker (root rule 7).

    - After a refusal the relay answers 503 ``cdn-backoff`` without
      contacting the CDN for a jittered, exponentially growing pause
      (base 2 s, cap 30 s); concurrent failures of one episode count once.
    - Until the CDN has answered once (and again after any refusal) only
      ONE upstream request is in flight — a 16-tile wall opening against a
      banned CDN sends one probe, not sixteen logins (the CDN bans bursts,
      docs/sandbox-findings.md §1). Once proven, requests run in parallel.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._probe = threading.Lock()
        self.failures = 0
        self.open_until = 0.0
        self.last_code = ""
        self.proven = False

    def remaining_s(self) -> float:
        with self._lock:
            return max(0.0, self.open_until - time.monotonic())

    def check(self) -> None:
        wait = self.remaining_s()
        if wait > 0:
            raise HTTPException(
                status_code=503, detail="cdn-backoff",
                headers={"Retry-After": str(max(1, int(wait + 0.999)))},
            )

    def enter(self) -> bool:
        """Admit one upstream request. Returns True when the caller holds
        the probe slot (release it with :meth:`leave`). Raises 503
        ``cdn-backoff`` while open, or when the probe never frees up."""
        self.check()
        with self._lock:
            if self.proven:
                return False
        if not self._probe.acquire(timeout=CDN_TIMEOUT_S * CDN_ATTEMPTS + 5):
            raise HTTPException(status_code=503, detail="cdn-backoff")
        with self._lock:
            proven = self.proven
        if proven:  # the probe we waited for succeeded: run in parallel
            self._probe.release()
            return False
        try:
            self.check()  # the probe we waited for failed: back off
        except HTTPException:
            self._probe.release()
            raise
        return True

    def leave(self, held: bool) -> None:
        if held:
            self._probe.release()

    def fail(self, code: str) -> None:
        with self._lock:
            now = time.monotonic()
            self.proven = False
            self.last_code = code
            if now < self.open_until:
                return  # another request of this episode already backed off
            _base, delay = backoff_delay(self.failures)
            self.failures += 1
            self.open_until = now + delay
            failures = self.failures
        log.warning("cdn relay backing off %.1fs after %s (failure %d)", delay, code, failures)

    def ok(self) -> None:
        with self._lock:
            self.failures = 0
            self.open_until = 0.0
            self.last_code = ""
            self.proven = True


_BREAKER = _Breaker()


def _cdn_error_code(exc: Exception) -> str:
    status = getattr(exc, "status", None)
    if status == "login":
        if "not set" in str(exc):
            return "cdn-not-configured"
        return "cdn-unavailable" if "unreachable" in str(exc) else "cdn-login-failed"
    if status == 404:
        return "cdn-not-found"
    return "cdn-unavailable"


def _cdn_get(url: str) -> httpx.Response:
    """One CDN GET through the shared session, behind the breaker. Raises
    HTTPException 503 (machine-readable detail) on refusal or outage, 502
    ``cdn-not-found`` when the CDN has no such object."""
    held = _BREAKER.enter()
    try:
        try:
            response = _cdn().get(url, max_attempts=CDN_ATTEMPTS)
        except (CdnError, httpx.HTTPError) as exc:
            code = _cdn_error_code(exc)
            log.warning("cdn relay fetch refused (%s): %s", code, config.masked(str(exc)))
            if code == "cdn-not-found":
                raise HTTPException(status_code=502, detail=code) from exc
            _BREAKER.fail(code)
            raise HTTPException(status_code=503, detail=code) from exc
        _BREAKER.ok()  # before the probe slot frees, so waiters see it
        return response
    finally:
        _BREAKER.leave(held)


class _Flight:
    __slots__ = ("event", "value", "error")

    def __init__(self) -> None:
        self.event = threading.Event()
        self.value: bytes | None = None
        self.error: BaseException | None = None


class _SingleFlightCache:
    """Bounded in-memory byte cache with single-flight fills: concurrent
    requests for one key wait on ONE upstream fetch; entries expire after
    ``ttl_s`` and the oldest are evicted past ``max_bytes``. Failures are
    never cached (the breaker paces the retry). Nothing touches disk."""

    def __init__(self, max_bytes: int, ttl_s: float) -> None:
        self.max_bytes = max_bytes
        self.ttl_s = ttl_s
        self._lock = threading.Lock()
        self._items: OrderedDict[str, tuple[float, bytes]] = OrderedDict()
        self._inflight: dict[str, _Flight] = {}
        self.size = 0

    def _drop(self, key: str) -> None:
        _exp, data = self._items.pop(key)
        self.size -= len(data)

    def get_or_fetch(self, key: str, fetch: Callable[[], bytes]) -> bytes:
        """The cached bytes for *key*, else the result of ONE ``fetch()``
        shared by every concurrent caller. Re-raises the fetch's error."""
        now = time.monotonic()
        with self._lock:
            hit = self._items.get(key)
            if hit is not None:
                if hit[0] > now:
                    self._items.move_to_end(key)
                    return hit[1]
                self._drop(key)
            flight = self._inflight.get(key)
            leader = flight is None
            if leader:
                flight = _Flight()
                self._inflight[key] = flight
        if not leader:
            if not flight.event.wait(_FLIGHT_WAIT_S):
                raise HTTPException(status_code=503, detail="cdn-unavailable")
            if flight.error is not None:
                err = flight.error
                if isinstance(err, HTTPException):
                    raise HTTPException(status_code=err.status_code, detail=err.detail,
                                        headers=err.headers)
                raise HTTPException(status_code=503, detail="cdn-unavailable")
            assert flight.value is not None
            return flight.value
        try:
            value = fetch()
            flight.value = value
            with self._lock:
                if len(value) <= self.max_bytes:
                    self._items[key] = (time.monotonic() + self.ttl_s, value)
                    self.size += len(value)
                    while self.size > self.max_bytes and self._items:
                        self._drop(next(iter(self._items)))
            return value
        except BaseException as exc:
            flight.error = exc
            raise
        finally:
            with self._lock:
                self._inflight.pop(key, None)
            flight.event.set()

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self.size = 0


_CACHE = _SingleFlightCache(CACHE_MAX_BYTES, CACHE_TTL_S)


def _camera(camera_id: str) -> sqlite3.Row:
    con = dbmod.connect()
    try:
        row = con.execute(
            "SELECT camera_id, hls_url, rtsp_url_template, transport, health, source,"
            " codec FROM cameras WHERE camera_id = ?",
            (camera_id,),
        ).fetchone()
    finally:
        con.close()
    if row is None:
        raise HTTPException(status_code=404, detail=f"unknown camera {camera_id}")
    return row


def _require_cdn_origin(url: str) -> None:
    """Refuse any upstream URL outside the configured CDN origin (B11)."""
    if not url.startswith(config.cdn() + "/"):
        raise HTTPException(
            status_code=403, detail="upstream URL is outside the configured CDN origin"
        )


def _cdn_playlist_url(cam: sqlite3.Row) -> str | None:
    """The camera's CDN VOD playlist: the registry's ``hls_url`` when the
    catalogue supplied one, else — for a camera from the organisers'
    catalogue — the sandbox's documented shape ``{cdn}/<id>/index.m3u8``
    (docs/reference/sandbox-access-spec.md). None for anything else (a
    manual, replay or local camera has no CDN copy)."""
    if cam["hls_url"]:
        return cam["hls_url"]
    if cam["source"] == "catalogue":
        return f"{config.cdn()}/{cam['camera_id']}/index.m3u8"
    return None


def _playlist_lock(camera_id: str) -> threading.Lock:
    with _playlist_locks_guard:
        return _playlist_locks.setdefault(camera_id, threading.Lock())


#: Upstream VOD playlists (~215 KB each) start at most one per this many
#: seconds relay-wide: a 16-tile wall opening on CDN cameras must not fire
#: 16 playlist fetches at once — a sequential sweep of all 30 playlists
#: already tripped the CDN's limiter on 14 Sep (docs/sandbox-findings.md §3).
_PLAYLIST_GAP_S = 1.5
_pace_lock = threading.Lock()
_last_playlist_fetch = 0.0


def _pace_playlist_fetch() -> None:
    """Block until this caller may start an upstream playlist fetch."""
    global _last_playlist_fetch
    with _pace_lock:
        wait = _last_playlist_fetch + _PLAYLIST_GAP_S - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_playlist_fetch = time.monotonic()


def _upstream_playlist(camera_id: str, hls_url: str) -> tuple[str, str, frozenset[str]]:
    """(playlist_text, base_url, servable_names) for a camera, cached ~10 min.

    One fetch per camera at a time: the first request waits for it (a
    login plus the ~215 KB VOD playlist took ~15 s on 25 Sep). Once a copy
    exists, an expired one keeps serving while ONE caller refreshes it, and
    survives a failed refresh — the VOD recording does not change, and a
    10-minute refresh must never stall the segments of a playing tile."""
    lock = _playlist_lock(camera_id)
    cached = _PLAYLIST_CACHE.get(camera_id)
    usable = cached if cached and cached[2] == hls_url else None
    if usable and time.time() - usable[0] < _PLAYLIST_TTL_S:
        return usable[1], usable[2], usable[3]
    if usable:
        if not lock.acquire(blocking=False):
            return usable[1], usable[2], usable[3]  # someone is refreshing it
    else:
        lock.acquire()
    try:
        cached = _PLAYLIST_CACHE.get(camera_id)  # filled while we waited?
        if cached and cached[2] == hls_url and time.time() - cached[0] < _PLAYLIST_TTL_S:
            return cached[1], cached[2], cached[3]
        _require_cdn_origin(hls_url)
        _pace_playlist_fetch()
        try:
            text = _cdn_get(hls_url).text
        except HTTPException:
            if usable:
                log.warning("cdn playlist refresh failed for %s; serving the cached copy", camera_id)
                return usable[1], usable[2], usable[3]
            raise
        if "#EXTINF" not in text:
            raise HTTPException(status_code=502, detail="upstream did not return a media playlist")
        # Only simple names are servable through /seg/{name}; an absolute or
        # path-carrying URI in the playlist is never proxied (B11).
        names = frozenset(seg for _, seg in _SEGMENT.findall(text) if _SAFE_NAME.match(seg))
        _PLAYLIST_CACHE[camera_id] = (time.time(), text, hls_url, names)
        return text, hls_url, names
    finally:
        lock.release()


# -------------------------------------------------------------- local tee

def _local_playlist(camera_id: str, max_age_s: float) -> str | None:
    """The worker's tee playlist rewritten to ``/local/{seg}``, or None
    when the tee is absent, older than *max_age_s*, or empty."""
    from backend.services.health import tee_age_s, tee_playlist

    age = tee_age_s(camera_id)
    if age is None or age > max_age_s:
        return None
    try:
        text = tee_playlist(camera_id).read_text(encoding="utf-8")
    except OSError:
        return None
    if "#EXTINF" not in text:
        return None
    out = []
    for line in text.splitlines():
        if line and not line.startswith("#"):
            line = f"/api/hls/{camera_id}/local/{line.strip()}"
        out.append(line)
    return "\n".join(out) + "\n"


# -------------------------------------------------------------- mediamtx

def _local_mtx_path(cam: sqlite3.Row) -> str | None:
    """The mediamtx path (``stream/local05``) of a LOCAL feed — an RTSP URL
    on 127.0.0.1/localhost — or None for any other camera."""
    template = (cam["rtsp_url_template"] or "").strip()
    if not template:
        return None
    try:
        parts = urllib.parse.urlsplit(template)
    except ValueError:
        return None
    if parts.scheme.lower() not in ("rtsp", "rtsps") or parts.hostname not in _LOCAL_HOSTS:
        return None
    path = parts.path.strip("/")
    if not _MTX_PATH.match(path) or ".." in path.split("/"):
        return None
    return path


_REDIRECTS = frozenset({301, 302, 303, 307, 308})


def _mtx_fetch(url: str, timeout_s: float,
               transport: httpx.BaseTransport | None = None) -> tuple[int, bytes]:
    """GET *url* on the local mediamtx HLS server -> (status, body).

    mediamtx v1.21 answers a cookie-less first request with a ``302`` to
    ``?cookieCheck=1`` (observed 25 Sep): that redirect is followed, but
    only while it stays on the same loopback origin (host pin) and at most
    twice; anything else is a ``502``. Raises ``ConnectionError`` when
    nothing listens, ``TimeoutError`` on a timeout (tests replace this
    function, or pass a mock *transport*)."""
    origin = "/".join(url.split("/", 3)[:3])  # http://127.0.0.1:<port>
    try:
        with httpx.Client(timeout=timeout_s, trust_env=False, follow_redirects=False,
                          transport=transport) as client:
            for _hop in range(3):
                response = client.get(url)
                if response.status_code not in _REDIRECTS:
                    return response.status_code, response.content
                target = urllib.parse.urljoin(url, response.headers.get("location", ""))
                if not target.startswith(origin + "/"):
                    log.warning("mediamtx redirected off its loopback origin; refused")
                    return 502, b""
                url = target
    except httpx.ConnectError as exc:
        raise ConnectionError(str(exc)) from exc
    except httpx.TimeoutException as exc:
        raise TimeoutError(str(exc)) from exc
    except httpx.HTTPError as exc:
        raise ConnectionError(str(exc)) from exc
    return 502, b""  # a redirect loop


def _mtx_get(path: str, name: str, session: str, timeout_s: float) -> bytes:
    """One object from mediamtx's HLS server, host pinned to 127.0.0.1."""
    query = f"?session={session}" if session else ""
    url = f"http://127.0.0.1:{config.mediamtx_hls_port()}/{path}/{name}{query}"
    try:
        status, body = _mtx_fetch(url, timeout_s)
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail="local feed server not running") from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=503, detail="local feed server timed out") from exc
    if status == 404:
        raise HTTPException(status_code=503, detail="local feed not publishing")
    if status >= 400:
        raise HTTPException(status_code=502, detail=f"local feed server answered {status}")
    return body


#: (camera_id, mediamtx session) -> (touched_at, names in the playlist last
#: fetched for that session, names in the one before it). The /mtx/
#: allow-list: one generation of grace covers a segment request racing
#: the next playlist reload; nothing older is ever servable.
_MTX_ALLOWED: OrderedDict[tuple[str, str], tuple[float, frozenset[str], frozenset[str]]] = (
    OrderedDict()
)
_mtx_lock = threading.Lock()


def _mtx_remember(camera_id: str, session: str, names: set[str]) -> None:
    now = time.monotonic()
    key = (camera_id, session)
    with _mtx_lock:
        entry = _MTX_ALLOWED.pop(key, None)
        previous = entry[1] if entry else frozenset()
        _MTX_ALLOWED[key] = (now, frozenset(names), previous)
        while _MTX_ALLOWED:
            oldest_key, oldest = next(iter(_MTX_ALLOWED.items()))
            if len(_MTX_ALLOWED) > _MTX_MAX_SESSIONS or now - oldest[0] > _MTX_SESSION_TTL_S:
                _MTX_ALLOWED.pop(oldest_key)
            else:
                break


def _mtx_allowed(camera_id: str, session: str, name: str) -> bool:
    with _mtx_lock:
        entry = _MTX_ALLOWED.get((camera_id, session))
    return entry is not None and (name in entry[1] or name in entry[2])


def _mtx_rewrite(camera_id: str, text: str) -> tuple[str, dict[str, set[str]]]:
    """Rewrite every URI line of a mediamtx playlist to
    ``/api/hls/{cam}/mtx/{name}[?session=..]`` and return the listed names
    per session. An absolute or path-carrying URI is refused (502)."""
    out: list[str] = []
    listed: dict[str, set[str]] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            parts = urllib.parse.urlsplit(stripped)
            session = urllib.parse.parse_qs(parts.query).get("session", [""])[0]
            if (parts.scheme or parts.netloc or not _SAFE_NAME.match(parts.path)
                    or parts.path.startswith(".")
                    or (session and not _SESSION_ID.match(session))):
                raise HTTPException(status_code=502, detail="unexpected entry in local feed playlist")
            listed.setdefault(session, set()).add(parts.path)
            query = f"?session={session}" if session else ""
            line = f"/api/hls/{camera_id}/mtx/{urllib.parse.quote(parts.path)}{query}"
        out.append(line)
    return "\n".join(out) + "\n", listed


def _mtx_playlist(camera_id: str, path: str, name: str, session: str) -> str:
    """Fetch, rewrite and allow-list one mediamtx playlist."""
    timeout = MTX_INDEX_TIMEOUT_S if name == "index.m3u8" else MTX_TIMEOUT_S
    body = _mtx_get(path, name, session, timeout).decode("utf-8", errors="replace")
    if not body.lstrip().startswith("#EXTM3U"):
        # never hand hls.js an empty "playlist" (it reports a parsing error)
        raise HTTPException(status_code=502, detail="local feed server returned no playlist")
    text, listed = _mtx_rewrite(camera_id, body)
    for sess, names in listed.items():
        if sess == session:
            names = names | {name}  # the child playlist itself stays reloadable
        _mtx_remember(camera_id, sess, names)
    return text


def _mtx_up() -> bool:
    """True when something listens on mediamtx's HLS port (loopback only)."""
    try:
        with socket.create_connection(("127.0.0.1", config.mediamtx_hls_port()), timeout=0.3):
            return True
    except OSError:
        return False


# -------------------------------------------------------------- the policy

@dataclass(frozen=True)
class _Plan:
    source: Source
    detail: str
    tee_text: str | None = None
    mtx_path: str | None = None
    cdn_url: str | None = None


def _plan(cam: sqlite3.Row) -> _Plan:
    """Decide the path for *cam* (module docstring order). Reads only the
    tee on disk and the registry row — never an upstream."""
    from backend.services.health import tee_age_s

    camera_id = cam["camera_id"]
    fresh = _local_playlist(camera_id, TEE_FRESH_S)
    if fresh:
        age = tee_age_s(camera_id) or 0.0
        return _Plan("tee", f"analytics worker's own pull, tee {age:.0f}s old", tee_text=fresh)

    mtx_path = _local_mtx_path(cam)
    if mtx_path:
        return _Plan("mediamtx", f"local feed {mtx_path} via mediamtx HLS on 127.0.0.1",
                     mtx_path=mtx_path)

    stale = _local_playlist(camera_id, STALE_TEE_MAX_S)
    if stale:
        age = tee_age_s(camera_id) or 0.0
        return _Plan("stale-tee",
                     f"analytics worker reconnecting; last good seconds, tee {age:.0f}s old",
                     tee_text=stale)

    cdn_url = _cdn_playlist_url(cam)
    if cdn_url:
        return _Plan("cdn", "organisers' CDN recording at the shared-timeline position",
                     cdn_url=cdn_url)

    return _Plan("none", "no live source: no analytics worker, no local feed and no CDN copy")


def _playlist_response(text: str, source: Source) -> PlainTextResponse:
    return PlainTextResponse(
        text, media_type=_M3U8, headers={**_NO_STORE, "X-Sentinel-Source": source}
    )


def _cdn_window(camera_id: str, url: str) -> str:
    text, _base, _names = _upstream_playlist(camera_id, url)
    segs = [(dur, seg) for dur, seg in _SEGMENT.findall(text) if _SAFE_NAME.match(seg)]
    if not segs:
        raise HTTPException(status_code=502, detail="no servable segments in upstream playlist")

    seg_dur = float(segs[0][0]) or 6.0
    total = len(segs)
    window = max(1, int(WINDOW_S / seg_dur))
    # The same live edge as the analytics workers (shared timeline), so
    # what the operator watches is what the detector would be reading.
    pos = timeline.live_position(datetime.now(timezone.utc)) % (total * seg_dur)
    start = max(0, min(int(pos / seg_dur) - window + 1, total - window))
    chosen = segs[start:start + window]

    lines = [
        "#EXTM3U",
        "#EXT-X-VERSION:6",
        f"#EXT-X-TARGETDURATION:{int(seg_dur) + 1}",
        f"#EXT-X-MEDIA-SEQUENCE:{start}",
    ]
    key = _KEY_LINE.search(text)
    if key:
        lines.append(
            f'#EXT-X-KEY:METHOD=AES-128,URI="/api/hls/{camera_id}/key"{key.group(2)}'
        )
    for dur, seg in chosen:
        lines.append(f"#EXTINF:{dur},")
        lines.append(f"/api/hls/{camera_id}/seg/{urllib.parse.quote(seg, safe='')}")
    return "\n".join(lines) + "\n"


def _cdn_camera_url(cam: sqlite3.Row) -> str:
    url = _cdn_playlist_url(cam)
    if not url:
        raise HTTPException(status_code=404, detail=f"{cam['camera_id']} has no CDN playlist")
    return url


# -------------------------------------------------------------- endpoints

@router.get("/{camera_id}/source", response_model=HlsSourceOut)
def hls_source(
    camera_id: str,
    _: str = Depends(require_auth),
    __: None = Depends(_limit_hls),
) -> HlsSourceOut:
    """Which path this camera's live playlist takes right now (``tee`` |
    ``stale-tee`` | ``mediamtx`` | ``cdn`` | ``none``) and why. Touches no
    upstream: the tee on disk, the registry row, a loopback port check for
    mediamtx and the relay's CDN back-off state."""
    if not _SAFE_NAME.match(camera_id):
        raise HTTPException(status_code=400, detail="bad camera id")
    plan = _plan(_camera(camera_id))
    detail = plan.detail
    if plan.source == "mediamtx" and not _mtx_up():
        detail = "local feed server not running"
    elif plan.source == "cdn":
        wait = _BREAKER.remaining_s()
        if wait > 0:
            detail = (f"CDN refusing the relay ({_BREAKER.last_code}); "
                      f"backing off {wait:.0f}s")
    return HlsSourceOut(camera_id=camera_id, source=plan.source, detail=detail)


@router.get("/{camera_id}/live.m3u8", responses=_PLAYLIST_RESPONSE)
def live_playlist(
    camera_id: str,
    _: str = Depends(require_auth),
    __: None = Depends(_limit_hls),
) -> PlainTextResponse:
    """The wall's playlist for one camera: the worker's tee when fresh,
    else a local feed through mediamtx, else a sandbox camera's stale tee
    (< 120 s), else a sliding window over the CDN recording. The
    ``X-Sentinel-Source`` header names the path taken."""
    if not _SAFE_NAME.match(camera_id):
        raise HTTPException(status_code=400, detail="bad camera id")
    plan = _plan(_camera(camera_id))
    if plan.source in ("tee", "stale-tee"):
        return _playlist_response(plan.tee_text or "", plan.source)
    if plan.source == "mediamtx":
        text = _mtx_playlist(camera_id, plan.mtx_path or "", "index.m3u8", "")
        return _playlist_response(text, "mediamtx")
    if plan.source == "cdn":
        return _playlist_response(_cdn_window(camera_id, plan.cdn_url or ""), "cdn")
    raise HTTPException(status_code=404, detail="no-live-source")


@router.get("/{camera_id}/mtx/{name}", responses=_MTX_RESPONSE)
def mtx_object(
    camera_id: str,
    name: str,
    session: str = Query("", max_length=64),
    _: str = Depends(require_auth),
    __: None = Depends(_limit_hls),
) -> Response:
    """A local feed's child playlist or segment from mediamtx's HLS server
    (127.0.0.1 only) — **only** a name listed in the playlist last fetched
    for this viewer's mediamtx session. Relay only; nothing is written."""
    if (not _SAFE_NAME.match(camera_id) or not _SAFE_NAME.match(name)
            or name.startswith(".")):  # no dot-segments towards mediamtx
        raise HTTPException(status_code=400, detail="bad name")
    if session and not _SESSION_ID.match(session):
        raise HTTPException(status_code=400, detail="bad session")
    path = _local_mtx_path(_camera(camera_id))
    if not path:
        raise HTTPException(status_code=404, detail=f"{camera_id} is not a local feed")
    if not _mtx_allowed(camera_id, session, name):
        raise HTTPException(status_code=403, detail="not in the local feed playlist")
    if name.endswith(".m3u8"):
        return _playlist_response(_mtx_playlist(camera_id, path, name, session), "mediamtx")
    body = _mtx_get(path, name, session, MTX_TIMEOUT_S)
    media = "video/mp4" if name.endswith((".mp4", ".m4s")) else "video/mp2t"
    return Response(content=body, media_type=media, headers=_NO_STORE)


@router.get("/{camera_id}/key", responses=_BYTES_RESPONSE)
def hls_key(
    camera_id: str,
    _: str = Depends(require_auth),
    __: None = Depends(_limit_hls),
) -> Response:
    """Proxy the AES-128 key named by the upstream playlist, with the
    backend's CDN session; refused unless it is a 16-byte key from inside
    the CDN origin. Held only in the relay's memory cache (≤ 120 s)."""
    if not _SAFE_NAME.match(camera_id):
        raise HTTPException(status_code=400, detail="bad camera id")
    cam = _camera(camera_id)
    text, base, _names = _upstream_playlist(camera_id, _cdn_camera_url(cam))
    key = _KEY_LINE.search(text)
    if not key:
        raise HTTPException(status_code=404, detail="upstream playlist names no key")
    key_url = urllib.parse.urljoin(base, key.group(1))
    _require_cdn_origin(key_url)

    def fetch() -> bytes:
        content = _cdn_get(key_url).content
        if len(content) != 16:
            raise HTTPException(status_code=502, detail="upstream key is not a 16-byte AES-128 key")
        return content

    content = _CACHE.get_or_fetch(key_url, fetch)
    return Response(content=content, media_type="application/octet-stream", headers=_NO_STORE)


@router.get("/{camera_id}/seg/{name}", responses=_BYTES_RESPONSE)
def hls_segment(
    camera_id: str,
    name: str,
    _: str = Depends(require_auth),
    __: None = Depends(_limit_hls),
) -> Response:
    """Proxy one media segment — **only** a name present in the fetched
    upstream playlist, resolved **only** inside the configured CDN origin
    (B11). N concurrent viewers share one upstream fetch (memory cache);
    nothing is written to disk."""
    if not _SAFE_NAME.match(camera_id) or not _SAFE_NAME.match(name):
        raise HTTPException(status_code=400, detail="bad name")
    cam = _camera(camera_id)
    _text, base, names = _upstream_playlist(camera_id, _cdn_camera_url(cam))
    if name not in names:
        raise HTTPException(status_code=403, detail="segment is not in the upstream playlist")
    seg_url = urllib.parse.urljoin(base, name)
    _require_cdn_origin(seg_url)
    content = _CACHE.get_or_fetch(seg_url, lambda: _cdn_get(seg_url).content)
    return Response(content=content, media_type="video/mp2t", headers=_NO_STORE)


@router.get("/{camera_id}/local/{name}", responses=_BYTES_RESPONSE)
def local_segment(
    camera_id: str,
    name: str,
    _: str = Depends(require_auth),
    __: None = Depends(_limit_hls),
) -> Response:
    """One segment of the worker's local live window (the RTSP tee)."""
    if not _SAFE_NAME.match(camera_id) or not _SAFE_NAME.match(name):
        raise HTTPException(status_code=400, detail="bad name")
    path = config.hls_dir() / camera_id / name
    try:
        data = path.read_bytes()
    except OSError:
        # The window moved on and ffmpeg deleted the segment: expected.
        raise HTTPException(status_code=404, detail="segment gone") from None
    return Response(content=data, media_type="video/mp2t", headers=_NO_STORE)
