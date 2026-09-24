"""HLS relay — Pipeline 1 live view (relay only, stores nothing).

Ported from ``D:\\projects\\Sentinel_Repo\\src\\api\\routes_hls.py`` (F52)
and adapted to this repo's contract (docs/api.md §7 hls row, B11; decisions
C7, F41):

- The browser cannot carry the CDN session cookie cross-origin and the CDN
  403s non-browser agents (docs/sandbox-findings.md §1-§2), so the live
  wall plays through this relay. For RTSP cameras the worker's ffmpeg tees
  a stream-copied local HLS window (one pull per camera, C7) which is
  served **when fresh (< 20 s)**, rewritten to ``/local/{seg}``.
- Otherwise the CDN relay: a **sliding window** of the upstream VOD
  playlist at the shared-timeline position (``backend/core/timeline.py``),
  segment URLs rewritten to ``/seg/{name}`` and the AES key URI to
  ``/key``. Upstream playlists are cached ~10 minutes to spare the CDN
  rate limiter (backend/CLAUDE.md).
- **Input hygiene (B11):** ``/seg/{name}`` proxies only names present in
  the fetched playlist, and every upstream fetch must resolve inside the
  configured CDN origin; ``/key`` requires a 16-byte AES-128 key.
- An RTSP camera's live view is **its own tee — never the CDN**, whose
  copy is a different source (and unreachable from the demo laptop): a
  stale tee (the last good seconds) is served rather than a dead CDN key
  (the old build's LAUNCHER RUN 1 lesson, kept).
- Every path accepts header or cookie auth — ``X-API-Key``,
  ``sentinel_session`` and the ``sentinel_key`` media cookie all resolve
  on GET ``/api/hls/*`` (backend/app/auth.py) — and is rate-limited
  (docs/api.md §9 names the relay).

Nothing is persisted here — segments stream straight through.
"""

from __future__ import annotations

import re
import sqlite3
import threading
import time
import urllib.parse
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response

from backend.app.auth import RateLimiter, require_auth
from backend.core import config, timeline
from backend.core import db as dbmod
from backend.core.cdn_session import CdnError, CdnSession
from backend.core.logging_setup import setup

log = setup("hls-relay")

router = APIRouter(prefix="/api/hls", tags=["hls"])

#: Seconds of video behind the live edge (the window of segments served).
WINDOW_S = 60
#: Upstream playlists are static VOD; cache them to spare the rate limiter.
_PLAYLIST_TTL_S = 600
#: The worker's tee is live when younger than this (task S3.1b: < 20 s).
TEE_FRESH_S = 20.0
#: An RTSP camera with a stale tee serves its last good seconds up to this
#: age rather than falling to the CDN (a different, often dead source).
STALE_TEE_MAX_S = 86_400.0

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")
_KEY_LINE = re.compile(r'#EXT-X-KEY:METHOD=AES-128,URI="([^"]+)"([^\n]*)')
_SEGMENT = re.compile(r"#EXTINF:([\d.]+)[^\n]*\n(?!#)(\S+)")

_M3U8 = "application/vnd.apple.mpegurl"
_NO_STORE = {"Cache-Control": "no-store"}

#: docs/api.md §9: rate-limited, generously — a 9-tile wall polls playlists
#: and segments continuously; 429 rather than queueing.
_limit_hls = RateLimiter("hls", limit=600, window_s=60.0)

_PLAYLIST_RESPONSE = {
    200: {
        "description": "The rewritten HLS media playlist",
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

# ------------------------------------------------------------- CDN session

_session_lock = threading.Lock()
_session: CdnSession | None = None

#: camera_id -> (fetched_at, playlist_text, base_url, servable segment names)
_PLAYLIST_CACHE: dict[str, tuple[float, str, str, frozenset[str]]] = {}


def _cdn() -> CdnSession:
    """The one shared CDN session (lazy; tests replace ``_session``)."""
    global _session
    with _session_lock:
        if _session is None:
            _session = CdnSession()
        return _session


def _camera(camera_id: str) -> sqlite3.Row:
    con = dbmod.connect()
    try:
        row = con.execute(
            "SELECT camera_id, hls_url, transport, health FROM cameras WHERE camera_id = ?",
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


def _upstream_playlist(camera_id: str, hls_url: str) -> tuple[str, str, frozenset[str]]:
    """(playlist_text, base_url, servable_names) for a camera, cached ~10 min."""
    cached = _PLAYLIST_CACHE.get(camera_id)
    if cached and time.time() - cached[0] < _PLAYLIST_TTL_S:
        return cached[1], cached[2], cached[3]
    _require_cdn_origin(hls_url)
    try:
        text = _cdn().get(hls_url).text
    except CdnError as exc:
        raise HTTPException(status_code=502, detail=f"upstream unavailable: {exc}") from exc
    if "#EXTINF" not in text:
        raise HTTPException(status_code=502, detail="upstream did not return a media playlist")
    # Only simple names are servable through /seg/{name}; an absolute or
    # path-carrying URI in the playlist is never proxied (B11).
    names = frozenset(seg for _, seg in _SEGMENT.findall(text) if _SAFE_NAME.match(seg))
    _PLAYLIST_CACHE[camera_id] = (time.time(), text, hls_url, names)
    return text, hls_url, names


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


# -------------------------------------------------------------- endpoints

@router.get("/{camera_id}/live.m3u8", responses=_PLAYLIST_RESPONSE)
def live_playlist(
    camera_id: str,
    _: str = Depends(require_auth),
    __: None = Depends(_limit_hls),
) -> PlainTextResponse:
    """A live playlist for the wall: the worker's local tee when fresh
    (< 20 s), else an RTSP camera's stale tee (never the CDN), else a
    sliding window over the CDN recording at the shared-timeline position."""
    if not _SAFE_NAME.match(camera_id):
        raise HTTPException(status_code=400, detail="bad camera id")
    cam = _camera(camera_id)

    local = _local_playlist(camera_id, TEE_FRESH_S)
    if local:
        return PlainTextResponse(local, media_type=_M3U8, headers=_NO_STORE)

    if cam["transport"] == "rtsp":
        # This camera's live view is its own pull; serve the last good
        # seconds through a reconnect rather than a different (dead) source.
        stale = _local_playlist(camera_id, STALE_TEE_MAX_S)
        if stale:
            return PlainTextResponse(stale, media_type=_M3U8, headers=_NO_STORE)
        raise HTTPException(status_code=503, detail=f"{camera_id} pull reconnecting")

    if not cam["hls_url"]:
        raise HTTPException(status_code=404, detail=f"{camera_id} has no live source")

    text, base, _names = _upstream_playlist(camera_id, cam["hls_url"])
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
    return PlainTextResponse("\n".join(lines) + "\n", media_type=_M3U8, headers=_NO_STORE)


@router.get("/{camera_id}/key", responses=_BYTES_RESPONSE)
def hls_key(
    camera_id: str,
    _: str = Depends(require_auth),
    __: None = Depends(_limit_hls),
) -> Response:
    """Proxy the AES-128 key named by the upstream playlist, with the
    backend's CDN session; refused unless it is a 16-byte key from inside
    the CDN origin. Never cached."""
    if not _SAFE_NAME.match(camera_id):
        raise HTTPException(status_code=400, detail="bad camera id")
    cam = _camera(camera_id)
    if not cam["hls_url"]:
        raise HTTPException(status_code=404, detail=f"{camera_id} has no CDN playlist")
    text, base, _names = _upstream_playlist(camera_id, cam["hls_url"])
    key = _KEY_LINE.search(text)
    if not key:
        raise HTTPException(status_code=404, detail="upstream playlist names no key")
    key_url = urllib.parse.urljoin(base, key.group(1))
    _require_cdn_origin(key_url)
    try:
        content = _cdn().get(key_url).content
    except CdnError as exc:
        raise HTTPException(status_code=502, detail=f"key unavailable: {exc}") from exc
    if len(content) != 16:
        raise HTTPException(status_code=502, detail="upstream key is not a 16-byte AES-128 key")
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
    (B11). Relay only; nothing is written to disk."""
    if not _SAFE_NAME.match(camera_id) or not _SAFE_NAME.match(name):
        raise HTTPException(status_code=400, detail="bad name")
    cam = _camera(camera_id)
    if not cam["hls_url"]:
        raise HTTPException(status_code=404, detail=f"{camera_id} has no CDN playlist")
    _text, base, names = _upstream_playlist(camera_id, cam["hls_url"])
    if name not in names:
        raise HTTPException(status_code=403, detail="segment is not in the upstream playlist")
    seg_url = urllib.parse.urljoin(base, name)
    _require_cdn_origin(seg_url)
    try:
        content = _cdn().get(seg_url).content
    except CdnError as exc:
        raise HTTPException(status_code=502, detail=f"segment unavailable: {exc}") from exc
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
