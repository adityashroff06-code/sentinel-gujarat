"""Real-browser playback proof for the live relay (relay lane, 25 Sep).

Run from the repo root as ``.venv/Scripts/python scripts/smoke_playback.py``
after ``npm --prefix frontend run build``.

What it does, end to end, with nothing mocked:

1. starts mediamtx (checksum-verified, ``scripts/replay_publish.py``) bound
   to 127.0.0.1 only, RTSP on 18554 and its HLS server on 18888 — never
   the real platform's 8554/8888 — with the HLS settings the feeds lane
   uses (``MTX_HLSVARIANT=mpegts``, 2 s segments, 7 kept, no always-remux);
2. loop-publishes ``<footage>/feeds/local02.mp4`` in copy mode;
3. starts the API (``python -m backend.app``) on a random free port
   against a FRESH temp database (same approach as
   ``scripts/smoke_frontend.py``) with ``SENTINEL_MEDIAMTX_HLS_PORT=18888``
   and the CDN disabled for this run (no sandbox traffic);
4. registers ``local02`` with ``rtsp_url_template
   rtsp://127.0.0.1:18554/stream/local02`` and a throwaway viewer account;
5. signs in through /login in Microsoft Edge (``channel="msedge"`` —
   Playwright's bundled Chromium has no H.264) and asserts that the wall
   tile's <video> ACTUALLY PLAYS: ``readyState >= 2`` and ``currentTime``
   advancing by more than 1 s over ~4 s; the tile's source badge reads
   LOCAL FEED; the browser never contacts mediamtx directly (every video
   request goes through ``/api/hls/``); the ``?cam=local02`` deep link
   plays 1-up too; and the console shows ZERO Content-Security-Policy
   violations;
6. proves the CDN branch the same way WITHOUT touching the organisers'
   CDN: a local STAND-IN CDN (a thread in this process, 127.0.0.1 only)
   mimics the sandbox's contract — form login setting a session cookie,
   403 for a non-browser User-Agent or a missing cookie, an AES-128 VOD
   playlist at ``/<id>/index.m3u8`` with ``URI="/enc.key"`` and
   ``segNNNNN.ts`` names — built by ffmpeg from ``local05.mp4``. A
   catalogue camera ``cam90`` (no ``hls_url``, like cam01..cam30) then
   plays through ``/seg/`` + ``/key`` (hls.js decrypts in the browser) in
   TWO pages at once, and the stand-in counts that every segment and the
   key were fetched upstream ONCE (the single-flight cache);
7. writes an H.265 worker-style tee (``cam91``, stream copy of a libx265
   clip, the way ``ml/ingest/rtsp.py`` tees cam06/cam26) and asserts that
   a browser without hvc1 MSE support (Edge 153 on the demo laptop) shows
   the H.265 message and never requests the playlist — or plays it where
   hvc1 is supported; an H.265 CDN copy (``cam92``, served by the
   stand-in) is TRIED and, on the decode failure, shows the same message;
   with ``--hevc-chrome`` both H.265 tiles are also opened in HEADED
   Google Chrome (headless browsers get no hardware HEVC) and must play;
8. kills every process it started (finally blocks).

The throwaway API keys, the account password and the stand-in CDN's
credentials are generated per run and never printed (root CLAUDE.md rule
1). Exits 0 on success.
"""

from __future__ import annotations

import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
PY = sys.executable  # the venv this script runs under
SCREENS = REPO / "data" / "screens"

RTSP_PORT = 18554
HLS_PORT = 18888
CAMERA = "local02"

_TMP = Path(tempfile.mkdtemp(prefix="sentinel-playback-"))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


API_PORT = _free_port()
BASE = f"http://127.0.0.1:{API_PORT}"
CDN_PORT = _free_port()  # the stand-in CDN (never the organisers')
CDN_CAMERA = "cam90"
HEVC_CAMERA = "cam91"  # H.265 from a worker-style tee
HEVC_CDN_CAMERA = "cam92"  # H.265 from the (stand-in) CDN
#: --hevc-chrome: also open the H.265 tile in HEADED Google Chrome (a
#: window appears for ~20 s) — headless browsers get no hardware HEVC.
HEVC_CHROME = "--hevc-chrome" in sys.argv[1:]
CDN_USER, CDN_PASS = "standin@example.invalid", secrets.token_urlsafe(12)

# Set BEFORE any backend import so config reads these, not .env / defaults.
os.environ.update(
    {
        "SENTINEL_DB": str(_TMP / "playback.db"),
        "SENTINEL_LOG_DIR": str(_TMP / "logs"),
        "SENTINEL_HLS_DIR": str(_TMP / "hls"),  # no worker tee: the mediamtx path
        "SENTINEL_API_PORT": str(API_PORT),
        "SENTINEL_API_KEY_ADMIN": secrets.token_urlsafe(32),
        "SENTINEL_API_KEY_VIEWER": secrets.token_urlsafe(32),
        "SENTINEL_HEALTH_INTERVAL_S": "0",
        "SENTINEL_PUBLIC_HOST": "",
        "SENTINEL_MEDIAMTX_HLS_PORT": str(HLS_PORT),
        # no sandbox traffic from a smoke: the CDN origin is the local
        # stand-in and its throwaway credentials win over .env
        # (override=False) — the organisers' CDN is never contacted
        "SENTINEL_EMAIL": CDN_USER,
        "SENTINEL_PASSWORD": CDN_PASS,
        "SENTINEL_CDN": f"http://127.0.0.1:{CDN_PORT}",
    }
)

from backend.core import config  # noqa: E402  (env first)

USER, PASSWORD = "playback_smoke", secrets.token_urlsafe(12)
_passed: list[str] = []


def ok(label: str) -> None:
    _passed.append(label)
    print(f"PASS: {label}", flush=True)


def fail(label: str) -> None:
    print(f"FAIL: {label}", flush=True)
    raise SystemExit(1)


def check(cond: bool, label: str) -> None:
    ok(label) if cond else fail(label)


def _wait_port(port: int, proc: subprocess.Popen, what: str, timeout_s: float = 15.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            fail(f"{what} exited rc={proc.returncode} before binding 127.0.0.1:{port}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(0.2)
    fail(f"{what} did not open 127.0.0.1:{port} within {timeout_s:.0f}s")


def start_mediamtx() -> subprocess.Popen:
    """mediamtx with RTSP + HLS on loopback test ports; everything else off."""
    import replay_publish as rp  # scripts/ is on sys.path when run as a script

    rp.verify_zip()
    for port in (RTSP_PORT, HLS_PORT):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                fail(f"127.0.0.1:{port} is already in use — stop whatever holds it")
    env = {
        **os.environ,
        "MTX_RTSPADDRESS": f"127.0.0.1:{RTSP_PORT}",
        "MTX_RTSPTRANSPORTS": "tcp",
        "MTX_READTIMEOUT": "30s", "MTX_WRITETIMEOUT": "30s",
        "MTX_HLS": "yes",
        "MTX_HLSADDRESS": f"127.0.0.1:{HLS_PORT}",
        "MTX_HLSVARIANT": "mpegts",
        "MTX_HLSSEGMENTDURATION": "2s",
        "MTX_HLSSEGMENTCOUNT": "7",
        "MTX_HLSALWAYSREMUX": "no",
        "MTX_RTMP": "no", "MTX_WEBRTC": "no", "MTX_SRT": "no", "MTX_API": "no",
        "MTX_METRICS": "no", "MTX_PPROF": "no", "MTX_PLAYBACK": "no", "MTX_MOQ": "no",
    }
    log = open(_TMP / "mediamtx.log", "ab")
    exe = rp.mediamtx_exe()
    proc = subprocess.Popen([str(exe), str(rp.TOOLS_DIR / "mediamtx.yml")],
                            cwd=str(rp.TOOLS_DIR), env=env, stdout=log, stderr=log)
    try:
        _wait_port(RTSP_PORT, proc, "mediamtx (RTSP)")
        _wait_port(HLS_PORT, proc, "mediamtx (HLS)")
    except SystemExit:
        proc.kill()
        raise
    return proc


def start_publisher(clip: Path) -> subprocess.Popen:
    cmd = [
        config.ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "warning",
        "-re", "-stream_loop", "-1", "-i", str(clip),
        "-c", "copy", "-an", "-f", "rtsp", "-rtsp_transport", "tcp",
        f"rtsp://127.0.0.1:{RTSP_PORT}/stream/{CAMERA}",
    ]
    log = open(_TMP / "publisher.log", "ab")
    return subprocess.Popen(cmd, stdout=log, stderr=log)


def build_standin_vod(clip: Path, out: Path, key_file: Path) -> int:
    """An AES-128 HLS VOD shaped like the sandbox CDN's (6 s segments,
    ``segNNNNN.ts``, ``URI="/enc.key"``, IV 0 — one key for every camera,
    as on the sandbox) from 120 s of *clip*, stream copied. Returns the
    segment count."""
    out.mkdir(parents=True, exist_ok=True)
    if not key_file.is_file():
        key_file.write_bytes(secrets.token_bytes(16))
    (out / "keyinfo.txt").write_text(
        f"/enc.key\n{key_file}\n{'0' * 32}\n", encoding="utf-8")
    cmd = [
        config.ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-stream_loop", "-1", "-t", "120", "-i", str(clip), "-c", "copy", "-an",
        "-f", "hls", "-hls_time", "6", "-hls_playlist_type", "vod",
        "-hls_key_info_file", str(out / "keyinfo.txt"),
        "-hls_segment_filename", str(out / "seg%05d.ts"),
        str(out / "index.m3u8"),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print(r.stderr[-1500:], file=sys.stderr)
        fail("ffmpeg built the stand-in CDN's encrypted VOD")
    text = (out / "index.m3u8").read_text(encoding="utf-8")
    # ffmpeg writes IV=0x000...; the sandbox names the same IV explicitly
    return text.count("#EXTINF")


class StandInCdn:
    """The sandbox CDN's contract on 127.0.0.1 (docs/sandbox-findings.md
    §1-§2): POST /auth/login sets a session cookie; every GET needs that
    cookie AND a browser User-Agent (else 403); /<camera>/index.m3u8,
    /enc.key and /<camera>/segNNNNN.ts for each camera in *roots*. Counts
    every GET per path."""

    def __init__(self, roots: dict[str, Path], key_file: Path) -> None:
        import http.server
        import threading
        from collections import Counter

        self.hits: Counter[str] = Counter()
        self.logins = 0
        self.refused = 0
        cookie = secrets.token_urlsafe(16)
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:  # quiet
                return

            def _deny(self) -> None:
                outer.refused += 1
                self.send_response(403)
                self.end_headers()

            def do_POST(self) -> None:  # noqa: N802 - http.server API
                length = int(self.headers.get("Content-Length") or 0)
                form = urllib.parse.parse_qs(self.rfile.read(length).decode())
                if (self.path != "/auth/login" or form.get("email") != [CDN_USER]
                        or form.get("password") != [CDN_PASS]):
                    return self._deny()
                outer.logins += 1
                self.send_response(200)
                self.send_header("Set-Cookie", f"sentinel={cookie}; Path=/; HttpOnly")
                self.end_headers()

            def do_GET(self) -> None:  # noqa: N802 - http.server API
                if ("Mozilla" not in (self.headers.get("User-Agent") or "")
                        or f"sentinel={cookie}" not in (self.headers.get("Cookie") or "")):
                    return self._deny()
                path = self.path.split("?", 1)[0]
                outer.hits[path] += 1
                camera, _, name = path.lstrip("/").partition("/")
                root = roots.get(camera)
                if path == "/enc.key":
                    target, ctype = key_file, "application/octet-stream"
                elif root is not None and name == "index.m3u8":
                    target, ctype = root / "index.m3u8", "application/vnd.apple.mpegurl"
                elif (root is not None and name.startswith("seg") and name.endswith(".ts")
                      and "/" not in name):
                    target, ctype = root / name, "video/mp2t"
                else:
                    target, ctype = None, ""
                if target is None or not target.is_file():
                    self.send_response(404)
                    self.end_headers()
                    return
                body = target.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", CDN_PORT), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def build_hevc_clip(clip: Path, out: Path) -> Path:
    """12 s of *clip* re-encoded to H.265 (libx265 ultrafast, 2 s GOP) —
    a stand-in for the six HEVC sandbox cameras (cam06, cam12, cam17,
    cam18, cam22, cam26), two of which are analysed and so play from
    their worker's stream-copied tee."""
    cmd = [
        config.ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-t", "12", "-i", str(clip), "-an", "-vf", "scale=960:-2,fps=25",
        "-c:v", "libx265", "-preset", "ultrafast", "-g", "50", "-keyint_min", "50",
        "-x265-params", "log-level=error:scenecut=0", "-pix_fmt", "yuv420p", str(out),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print(r.stderr[-1500:], file=sys.stderr)
        fail("ffmpeg built the H.265 test clip")
    return out


def start_hevc_tee(hevc: Path, camera: str) -> subprocess.Popen:
    """Write a live HLS window exactly as the worker's tee does
    (``ml/ingest/rtsp.py``: stream copy, 2 s, delete_segments,
    omit_endlist) into the relay's tee directory for *camera*."""
    tee = config.hls_dir() / camera
    tee.mkdir(parents=True, exist_ok=True)
    cmd = [
        config.ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "warning",
        "-re", "-stream_loop", "-1", "-i", str(hevc),
        "-map", "0:v:0", "-an", "-c:v", "copy", "-f", "hls",
        "-hls_time", "2", "-hls_list_size", "10",
        "-hls_flags", "delete_segments+omit_endlist+independent_segments",
        "-hls_segment_filename", str(tee / "seg%06d.ts"),
        str(tee / "index.m3u8"),
    ]
    log = open(_TMP / "hevc_tee.log", "ab")
    return subprocess.Popen(cmd, stdout=log, stderr=log)


def seed_database() -> None:
    from backend.core import db as dbmod
    from backend.core import passwords

    con = dbmod.connect()
    try:
        dbmod.migrate(con)
        now = dbmod.utcnow()
        con.execute(
            "INSERT INTO cameras (camera_id, department, location_name, lat, lon, codec,"
            " rtsp_url_template, transport, fps_tier, source, created_at, updated_at)"
            " VALUES (?, 'Municipal', 'Sample feed 2 - market junction (stock footage)',"
            " 23.2225, 72.6441, 'h264', ?, 'rtsp', 'registered', 'manual', ?, ?)",
            (CAMERA, f"rtsp://127.0.0.1:{RTSP_PORT}/stream/{CAMERA}", now, now),
        )
        # a sandbox-shaped camera: from the catalogue, RTSP transport, no
        # hls_url and no worker — exactly how cam01..cam30 sit in the registry
        con.execute(
            "INSERT INTO cameras (camera_id, department, location_name, lat, lon, codec,"
            " transport, fps_tier, source, created_at, updated_at)"
            " VALUES (?, 'Police', 'Stand-in CDN camera (smoke only)', 23.03, 72.58,"
            " 'h264', 'rtsp', 'registered', 'catalogue', ?, ?)",
            (CDN_CAMERA, now, now),
        )
        # an analysed H.265 camera: its worker tee is a stream copy of HEVC
        con.execute(
            "INSERT INTO cameras (camera_id, department, location_name, lat, lon, codec,"
            " transport, fps_tier, source, created_at, updated_at)"
            " VALUES (?, 'GSRTC', 'H.265 tee camera (smoke only)', 23.04, 72.59,"
            " 'hevc', 'rtsp', 'active', 'catalogue', ?, ?)",
            (HEVC_CAMERA, now, now),
        )
        # an H.265 sandbox camera without a worker: its CDN copy is H.265 too
        con.execute(
            "INSERT INTO cameras (camera_id, department, location_name, lat, lon, codec,"
            " transport, fps_tier, source, created_at, updated_at)"
            " VALUES (?, 'Health', 'H.265 CDN camera (smoke only)', 23.05, 72.60,"
            " 'hevc', 'rtsp', 'registered', 'catalogue', ?, ?)",
            (HEVC_CDN_CAMERA, now, now),
        )
        con.execute(
            "INSERT INTO users (username, password_hash, role, active, created_at)"
            " VALUES (?, ?, 'viewer', 1, ?)",
            (USER, passwords.hash_password(PASSWORD), now),
        )
        con.commit()
    finally:
        con.close()


def start_api() -> subprocess.Popen:
    log = open(_TMP / "api.log", "w", encoding="utf-8")
    proc = subprocess.Popen([PY, "-m", "backend.app"], cwd=REPO, env=os.environ.copy(),
                            stdout=log, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            break
        try:
            with urllib.request.urlopen(f"{BASE}/api/health", timeout=2) as r:
                if r.status == 200:
                    return proc
        except OSError:
            time.sleep(0.5)
    proc.kill()
    log.close()
    print((_TMP / "api.log").read_text(encoding="utf-8")[-3000:], file=sys.stderr)
    fail("API came up on /api/health")
    raise AssertionError("unreachable")


VIDEO_STATE = """(sel) => {
    const v = document.querySelector(sel);
    return v ? {readyState: v.readyState, currentTime: v.currentTime,
                paused: v.paused, w: v.videoWidth, h: v.videoHeight,
                error: v.error ? v.error.message || String(v.error.code) : null} : null;
}"""

CSP_HOOK = """
window.__cspViolations = [];
document.addEventListener('securitypolicyviolation', (e) => {
  window.__cspViolations.push(e.violatedDirective + ' ' + e.blockedURI);
});
"""


#: (status, url) of every /api/hls/ response and the page's console errors —
#: printed when playback fails, so a red run says why.
_responses: list[tuple[int, str]] = []
_console_errors: list[str] = []


def _diagnose(page, selector: str) -> None:
    camera = selector.split("data-camera-id=\"", 1)[-1].split("\"", 1)[0]
    tile = selector.rsplit(" video", 1)[0]
    try:
        text = page.locator(tile).inner_text(timeout=2000).replace("\n", " | ")
        print("  tile text:", text.encode("ascii", "replace").decode())
        title = page.locator(f"{tile} .tile-state").get_attribute("title", timeout=2000)
        print("  tile state detail:", (title or "").encode("ascii", "replace").decode())
    except Exception as exc:  # noqa: BLE001 - diagnostics only
        print("  tile text unavailable:", exc)
    try:
        body = page.evaluate(
            "async (u) => { const r = await fetch(u, {credentials: 'same-origin'});"
            " return r.status + ' ' + (r.headers.get('X-Sentinel-Source') || '-') + '\\n'"
            " + (await r.text()); }",
            f"/api/hls/{camera}/live.m3u8",
        )
        print("  live.m3u8 as the browser sees it:\n    " + body[:800].replace("\n", "\n    "))
    except Exception as exc:  # noqa: BLE001 - diagnostics only
        print("  live.m3u8 fetch failed:", exc)
    for status, url in _responses[-15:]:
        print(f"  {status} {url.replace(BASE, '')}")
    for text in _console_errors[-10:]:
        print("  console:", text)
    log = _TMP / "api.log"
    if log.is_file():
        print("  api.log tail:\n" + log.read_text(encoding="utf-8", errors="replace")[-1500:])


def assert_plays(page, selector: str, label: str) -> dict:
    """Wait for readyState >= 2, then require currentTime to advance > 1 s
    over ~4 s. Returns the last observed state."""
    deadline = time.monotonic() + 45
    state = None
    while time.monotonic() < deadline:
        state = page.evaluate(VIDEO_STATE, selector)
        if state and state["readyState"] >= 2 and state["currentTime"] > 0:
            break
        time.sleep(0.25)
    if not (state and state["readyState"] >= 2):
        _diagnose(page, selector)
    check(bool(state) and state["readyState"] >= 2,
          f"{label}: <video> reached readyState >= 2 (got {state})")
    t0 = state["currentTime"]
    time.sleep(4.0)
    state = page.evaluate(VIDEO_STATE, selector)
    advanced = state["currentTime"] - t0
    check(advanced > 1.0,
          f"{label}: currentTime advanced {advanced:.2f} s over ~4 s "
          f"(readyState {state['readyState']}, {state['w']}x{state['h']}, paused={state['paused']})")
    return state


def main() -> int:
    if not (REPO / "frontend" / "dist" / "index.html").is_file():
        print("frontend/dist is missing — run: npm --prefix frontend run build", file=sys.stderr)
        return 2
    clip = config.footage_dir() / "feeds" / f"{CAMERA}.mp4"
    if not clip.is_file():
        print(f"{clip} is missing — run scripts/prepare_feeds.py first", file=sys.stderr)
        return 2
    SCREENS.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(REPO / "scripts"))

    procs: list[subprocess.Popen] = []
    standin: StandInCdn | None = None
    try:
        vod_clip = config.footage_dir() / "feeds" / "local05.mp4"
        hevc = build_hevc_clip(vod_clip, _TMP / "hevc.mp4")
        key_file = _TMP / "enc.key"
        n_segs = build_standin_vod(vod_clip, _TMP / "standin", key_file)
        n_hevc = build_standin_vod(hevc, _TMP / "standin-hevc", key_file)
        standin = StandInCdn({CDN_CAMERA: _TMP / "standin",
                              HEVC_CDN_CAMERA: _TMP / "standin-hevc"}, key_file)
        ok(f"stand-in CDN on 127.0.0.1:{CDN_PORT}: AES-128 VODs of {n_segs} (H.264) and"
           f" {n_hevc} (H.265) x 6 s segments (the organisers' CDN is never contacted)")
        procs.append(start_hevc_tee(hevc, HEVC_CAMERA))
        ok(f"H.265 tee for {HEVC_CAMERA} written like the worker's (stream copy, 2 s)")
        procs.append(start_mediamtx())
        ok(f"mediamtx up on 127.0.0.1:{RTSP_PORT} (RTSP) and 127.0.0.1:{HLS_PORT} (HLS)")
        procs.append(start_publisher(clip))
        seed_database()
        ok(f"temp registry has {CAMERA} -> rtsp://127.0.0.1:{RTSP_PORT}/stream/{CAMERA},"
           f" catalogue camera {CDN_CAMERA} (no hls_url), H.265 tee camera {HEVC_CAMERA}"
           f" and H.265 CDN camera {HEVC_CDN_CAMERA}")
        procs.append(start_api())
        ok(f"API up on {BASE}")

        from playwright.sync_api import sync_playwright

        console_csp: list[str] = []
        hls_urls: list[str] = []
        foreign: list[str] = []

        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="msedge", headless=True)
            ok(f"launched Microsoft Edge {browser.version} (channel=msedge)")
            ctx = browser.new_context(viewport={"width": 1366, "height": 768})
            ctx.add_init_script(CSP_HOOK)
            page = ctx.new_page()

            def on_console(msg) -> None:
                text = msg.text
                if "Content Security Policy" in text or "Content-Security-Policy" in text:
                    console_csp.append(text[:200])
                if msg.type in ("error", "warning"):
                    _console_errors.append(text[:300])

            def on_response(resp) -> None:
                if "/api/hls/" in resp.url:
                    _responses.append((resp.status, resp.url))

            page.on("response", on_response)

            def on_request(req) -> None:
                url = req.url
                if "/api/hls/" in url:
                    hls_urls.append(url)
                if any(f":{p}" in url for p in (HLS_PORT, RTSP_PORT, CDN_PORT)):
                    foreign.append(url)

            page.on("console", on_console)
            page.on("request", on_request)

            page.goto(f"{BASE}/wall")
            page.wait_for_url("**/login**", timeout=15000)
            page.fill("#login-username", USER)
            page.fill("#login-password", PASSWORD)
            page.click("button[type=submit]")
            page.wait_for_url("**/wall", timeout=15000)
            ok("signed in through /login and returned to /wall")

            tile = f'.tile[data-camera-id="{CAMERA}"]'
            page.wait_for_selector(tile, timeout=15000)
            t_start = time.monotonic()
            assert_plays(page, f"{tile} video", "wall tile")
            print(f"  (first frames after {time.monotonic() - t_start:.1f} s on the wall)")
            badge = page.locator(f"{tile} .src-badge").inner_text(timeout=10000).strip()
            check(badge == "LOCAL FEED", f"tile source badge reads LOCAL FEED (got {badge!r})")
            check(page.locator(tile).get_attribute("data-source") == "mediamtx",
                  "tile reports source=mediamtx")
            check(page.locator(f"{tile} .tile-state").count() == 0,
                  "no state overlay over a playing tile")
            page.screenshot(path=str(SCREENS / "smoke-playback-wall.png"))

            page.goto(f"{BASE}/wall?cam={CAMERA}")
            page.wait_for_selector(f".wall .grid.g1 {tile}", timeout=15000)
            assert_plays(page, f".wall .grid.g1 {tile} video", "?cam deep link (1-up)")
            page.screenshot(path=str(SCREENS / "smoke-playback-1up.png"))

            mtx_segments = [u for u in hls_urls if f"/api/hls/{CAMERA}/mtx/" in u and ".ts" in u]
            check(len(mtx_segments) >= 2,
                  f"segments came through the relay's /mtx/ path ({len(mtx_segments)} requests)")

            # ---- the CDN branch against the stand-in: two viewers ------
            cdn_tile = f'.tile[data-camera-id="{CDN_CAMERA}"]'
            cdn_video = f".wall .grid.g1 {cdn_tile} video"
            seg_marker = f"/api/hls/{CDN_CAMERA}/seg/"
            browser_segs_before = sum(1 for u in hls_urls if seg_marker in u)
            page.goto(f"{BASE}/wall?cam={CDN_CAMERA}")
            page.wait_for_selector(f".wall .grid.g1 {cdn_tile}", timeout=15000)
            assert_plays(page, cdn_video, "CDN branch, viewer 1 (AES-128, decrypted by hls.js)")
            badge = page.locator(f"{cdn_tile} .src-badge").inner_text(timeout=10000).strip()
            check(badge == "CDN RECORDING", f"CDN tile badge reads CDN RECORDING (got {badge!r})")
            page2 = ctx.new_page()
            page2.on("console", on_console)
            page2.on("request", on_request)
            page2.goto(f"{BASE}/wall?cam={CDN_CAMERA}")
            page2.wait_for_selector(f".wall .grid.g1 {cdn_tile}", timeout=15000)
            assert_plays(page2, cdn_video, "CDN branch, viewer 2 (second page, same time)")
            page.evaluate(VIDEO_STATE, cdn_video)  # pump viewer 1's pending events
            page2.screenshot(path=str(SCREENS / "smoke-playback-cdn.png"))
            # every cam90 viewer of this run (the wall tile, then two 1-up
            # pages) shares one upstream fetch per segment: the run is well
            # inside the cache's 120 s TTL
            browser_segs = sum(1 for u in hls_urls if seg_marker in u)
            window_segs = browser_segs - browser_segs_before
            all_upstream = {p: n for p, n in standin.hits.items() if "/seg" in p}
            upstream = {p: n for p, n in all_upstream.items()
                        if p.startswith(f"/{CDN_CAMERA}/")}
            check(bool(upstream) and max(all_upstream.values()) == 1,
                  f"no segment was fetched upstream twice ({len(upstream)} segments upstream"
                  f" for {browser_segs} browser segment requests, {window_segs} of them while"
                  f" two pages played)")
            check(browser_segs > len(upstream),
                  "repeat viewers were served from the relay's memory cache")
            check(standin.hits["/enc.key"] == 1 and standin.hits[f"/{CDN_CAMERA}/index.m3u8"] == 1,
                  f"key and VOD playlist fetched upstream once each"
                  f" (key {standin.hits['/enc.key']}, playlist"
                  f" {standin.hits[f'/{CDN_CAMERA}/index.m3u8']})")
            check(standin.logins == 1 and standin.refused == 0,
                  f"one CDN login, no refused request (logins {standin.logins},"
                  f" refused {standin.refused})")
            check(not foreign,
                  f"the browser never contacted mediamtx or the CDN directly ({foreign[:2]})")

            # ---- H.265: Edge on this laptop cannot decode it via MSE ------
            hevc_tile = f'.tile[data-camera-id="{HEVC_CAMERA}"]'
            hevc_ok = page.evaluate(
                "() => MediaSource.isTypeSupported('video/mp4; codecs=\"hvc1.1.6.L123.B0\"')")
            hevc_playlists_before = sum(
                1 for u in hls_urls if f"/api/hls/{HEVC_CAMERA}/live.m3u8" in u)
            page.goto(f"{BASE}/wall?cam={HEVC_CAMERA}")
            page.wait_for_selector(f".wall .grid.g1 {hevc_tile}", timeout=15000)
            if hevc_ok:
                assert_plays(page, f".wall .grid.g1 {hevc_tile} video",
                             "H.265 tee in this Edge (MSE reports hvc1 support)")
            else:
                page.wait_for_selector(f"{hevc_tile} .tile-state.blocked", timeout=15000)
                said = page.locator(f"{hevc_tile} .tile-state").inner_text()
                page.evaluate("() => 0")  # pump request events
                tried = sum(1 for u in hls_urls
                            if f"/api/hls/{HEVC_CAMERA}/live.m3u8" in u) - hevc_playlists_before
                check("H.265 feed" in said and "Google Chrome" in said and tried == 0,
                      f"Edge {browser.version} reports no hvc1 MSE support: the H.265 tile says"
                      f" so in operator words and never requests a playlist ({tried} requests)")
                page.screenshot(path=str(SCREENS / "smoke-playback-hevc-edge.png"))

            # an H.265 CDN copy: its codec is only known once the segments
            # are demuxed, so the tile tries, then names the problem
            hevc_cdn_tile = f'.tile[data-camera-id="{HEVC_CDN_CAMERA}"]'
            marker = f"/api/hls/{HEVC_CDN_CAMERA}/live.m3u8"
            tried_before = sum(1 for u in hls_urls if marker in u)
            page.goto(f"{BASE}/wall?cam={HEVC_CDN_CAMERA}")
            page.wait_for_selector(f".wall .grid.g1 {hevc_cdn_tile}", timeout=15000)
            if hevc_ok:
                assert_plays(page, f".wall .grid.g1 {hevc_cdn_tile} video",
                             "H.265 CDN copy in this Edge (MSE reports hvc1 support)")
            else:
                page.wait_for_selector(f"{hevc_cdn_tile} .tile-state.blocked", timeout=30000)
                said = page.locator(f"{hevc_cdn_tile} .tile-state").inner_text()
                tried = sum(1 for u in hls_urls if marker in u) - tried_before
                check("H.265 feed" in said and tried >= 1,
                      f"H.265 CDN copy in Edge: the tile tried the stream ({tried} playlist"
                      f" requests), hit the decode failure and said H.265 in operator words")
            # Regression (25 Sep, live laptop): Edge sometimes resumes a
            # stalled hls.js player WITHOUT a 'playing' event (seen across
            # the looped feeds), and the event-only watchdog then left "Feed
            # stalled" over tiles whose video kept advancing - local01..04
            # for minutes. Reproduce the exact condition: a 'waiting' event
            # that no 'playing' follows, on a tile that keeps playing.
            page.goto(f"{BASE}/wall?cam={CAMERA}")
            one = f".wall .grid.g1 {tile}"
            page.wait_for_selector(one, timeout=15000)
            assert_plays(page, f"{one} video", "stall-watchdog tile")
            t0 = page.eval_on_selector(f"{one} video", "v => { v.dispatchEvent(new Event('waiting'));"
                                                       " return v.currentTime }")
            page.wait_for_timeout(11000)  # past the tile's 8 s STALL_MS
            t1 = page.eval_on_selector(f"{one} video", "v => v.currentTime")
            stalled = page.locator(f"{one} .tile-state.stalled").count()
            check(t1 - t0 > 5 and stalled == 0,
                  f"a 'waiting' with no 'playing' after it never leaves 'Feed stalled' over"
                  f" advancing video (advanced {t1 - t0:.1f} s, stalled overlays {stalled})")
            violations = (page.evaluate("() => window.__cspViolations") or []) + (
                page2.evaluate("() => window.__cspViolations") or [])
            check(not violations and not console_csp,
                  f"zero CSP violations (events {violations[:3]}, console {console_csp[:3]})")
            browser.close()

            if HEVC_CHROME:
                # headed Google Chrome: the browser the tile recommends
                chrome = pw.chromium.launch(channel="chrome", headless=False)
                cpage = chrome.new_page(viewport={"width": 1366, "height": 768})
                cpage.goto(f"{BASE}/wall?cam={HEVC_CAMERA}")
                cpage.wait_for_url("**/login**", timeout=15000)
                cpage.fill("#login-username", USER)
                cpage.fill("#login-password", PASSWORD)
                cpage.click("button[type=submit]")
                cpage.wait_for_url(f"**/wall?cam={HEVC_CAMERA}", timeout=15000)
                supported = cpage.evaluate(
                    "() => MediaSource.isTypeSupported('video/mp4; codecs=\"hvc1.1.6.L123.B0\"')")
                check(supported, f"Google Chrome {chrome.version} (headed) reports hvc1 MSE support")
                assert_plays(cpage, f".wall .grid.g1 {hevc_tile} video",
                             f"H.265 tee in Google Chrome {chrome.version}")
                badge = cpage.locator(f"{hevc_tile} .src-badge").inner_text(timeout=10000)
                check("LIVE" in badge and "RTSP" in badge,
                      f"H.265 tee tile badge reads LIVE · RTSP (got {badge!r})")
                cpage.screenshot(path=str(SCREENS / "smoke-playback-hevc-chrome.png"))
                hevc_cdn_tile = f'.tile[data-camera-id="{HEVC_CDN_CAMERA}"]'
                cpage.goto(f"{BASE}/wall?cam={HEVC_CDN_CAMERA}")
                cpage.wait_for_selector(f".wall .grid.g1 {hevc_cdn_tile}", timeout=15000)
                assert_plays(cpage, f".wall .grid.g1 {hevc_cdn_tile} video",
                             f"H.265 CDN copy (AES-128) in Google Chrome {chrome.version}")
                chrome.close()
    finally:
        for proc in reversed(procs):
            try:
                proc.kill()
                proc.wait(timeout=10)
            except Exception as exc:  # noqa: BLE001 - best-effort teardown, reported
                print(f"teardown: {exc}", file=sys.stderr)
        if standin is not None:
            standin.close()
        shutil.rmtree(_TMP, ignore_errors=True)

    shots = ", ".join(p.name for p in sorted(SCREENS.glob("smoke-playback-*.png")))
    print(f"\nscreenshots in {SCREENS}: {shots}")
    print(f"PLAYBACK SMOKE PASS — {len(_passed)} assertions green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
