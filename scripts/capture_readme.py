"""Live screenshots and GIFs for the README, and the README gallery itself.

Run on the laptop with the platform up (``python launch.py start``; the
worker alive, ``feeds: 28/28``, Command's strip showing cam06 READING):

    .venv/Scripts/python scripts/capture_readme.py --user <name>

1. Signs in through /login in **headed Google Chrome** (``channel="chrome"``:
   the six H.265 sandbox cameras, cam06 among them, decode only there and
   only headed - F62; Playwright's bundled Chromium has no H.264 either).
2. Captures every screen except Zones at 1920x1080 into ``docs/readme/``,
   waiting on the tile screens until live video is actually playing
   (``readyState >= 2`` and ``currentTime`` advancing), and says per screen
   how many tiles were playing - a screen captured without playing video
   is reported, never passed off.
3. Records two short clips of live video (Command and the Live Wall) and
   turns them into GIFs with ffmpeg (``backend.core.config.ffmpeg()``, F25).
4. Regenerates the README hero and gallery between their markers, so the
   README only ever links images that exist.

``--gallery-only`` skips the browser and only regenerates the README blocks;
each image then falls back to the deck's 25 Sep live captures under
``deliverables/deck/img/``. Standard library only in that mode.

The password is read with getpass and never printed, logged or written
(root rules 1 and 11). Screenshots are of the page, never the address bar.
Exits 0 when every screen was captured.
"""
from __future__ import annotations

import argparse
import getpass
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "readme"
DECK = ROOT / "deliverables" / "deck" / "img"
README = ROOT / "README.md"
DEMO_PLATE = "GJ01AB1234"
DEMO_LOOKALIKE = "GJ01A81234"  # 8<->B: finds the demo vehicle ANPR-tolerant
VIEWPORT = {"width": 1920, "height": 1080}


@dataclass(frozen=True)
class Shot:
    """One README image: its file stem, where it comes from, its caption."""
    name: str
    caption: str
    path: str = ""               # route to open ("" = not a browser shot)
    wall_filter: str = ""        # Live Wall button to press ("Analysed", ...)
    videos: int = 0              # playing tiles to wait for (0 = none)
    fallback: str = ""           # deck capture used until this one exists


SHOTS: list[Shot] = [
    Shot("command", "**Command.** One screen for the control room: live tiles, the camera network, headline counts, "
         "the feed-status strip, and the *Start here* panel that tells an evaluator what to try and which rows are "
         "demonstration data.", "/command", videos=2, fallback="dashboard.png"),
    Shot("live-wall", "**Live Wall: the government feed.** The analysed sandbox cameras, each pulled live over RTSP "
         "once and relayed from the worker's own 20-second window (`LIVE · RTSP`).",
         "/wall", wall_filter="Analysed", videos=3, fallback="wall.png"),
    Shot("live-wall-local", "**Live Wall: the second system.** 28 local feeds from our own media server, stock "
         "traffic clips at seeded coordinates and labelled as such (`LOCAL FEED`), in the same viewer.",
         "/wall", wall_filter="Local feeds", videos=3, fallback="wall-local.png"),
    Shot("map", "**Map.** Every camera by department, clustered below street zoom with each cluster's department "
         "share; the analysed ring, health, 24-hour activity and coverage gaps as layers.",
         "/map", fallback="map.png"),
    Shot("map-street", "**Map at street zoom.** Field-of-view wedges and the camera's registry record, with its "
         "24-hour activity split into live and demonstration reads.",
         "/map?cam=local01", fallback="gis.png"),
    Shot("search", "**ANPR search.** A plate read live from the government feed: every read with its crop, "
         "confidence, vehicle class, camera and time, each marked `LIVE`.",
         "/search?plate={live_plate}&match=anpr", fallback="search.png"),
    Shot("search-ambiguity", f"**OCR-tolerant search.** `{DEMO_LOOKALIKE}` still finds `{DEMO_PLATE}` (8 and B "
         "look alike to OCR): the labelled demonstration vehicle, badged `DEMO`, with its watchlist hit.",
         f"/search?plate={DEMO_LOOKALIKE}&match=anpr", fallback="search-ambiguity.png"),
    Shot("route", f"**Route: the scored capability.** `{DEMO_PLATE}`, the labelled demonstration vehicle: numbered "
         "stops across three cameras and three departments, with times, speeds and the OCR near-miss it still "
         "matched.", f"/route/{DEMO_PLATE}", fallback="route.png"),
    Shot("alerts", "**Alerts.** Pushed over Server-Sent Events from the alerts table: plate crop, severity, "
         "category, match type, camera and department. These are the demonstration vehicle's, badged `DEMO`.",
         "/alerts", fallback="alerts.png"),
    Shot("reports", "**Reports.** The timestamped detection report (HTML or CSV), the gap-analysis report and "
         "the route export; object counts per camera; the latest live detections with their provenance.",
         "/reports", fallback="reports.png"),
    Shot("cameras", "**Cameras.** The registry every other component reads: onboarding by form, by bulk CSV or "
         "over the API, with transport, tier and health per camera.", "/cameras"),
    Shot("watchlist", "**Watchlist.** Category, severity and reason per plate; every read is matched against a "
         "cached copy locally, never with a round trip per detection.", "/watchlist"),
    Shot("login", "**Sign in.** Role-based access for viewer, evaluator and admin. Nothing but this page and the "
         "health check is reachable without a session.", "/login"),
]
GIFS = {"command": "/command", "live-wall": "/wall"}  # animated live video

PLAYING_JS = ("() => Array.from(document.querySelectorAll('video'))"
              ".map(v => [v.readyState, v.currentTime])")


# --- README blocks ------------------------------------------------------------

def image_for(shot: Shot, prefer_gif: bool = False) -> str | None:
    """Repo-relative path of the best existing image for *shot*: the GIF
    (when asked), then this script's PNG, then the deck fallback. Returns
    None when none exists; never raises."""
    candidates = []
    if prefer_gif:
        candidates.append(OUT / f"{shot.name}.gif")
    candidates.append(OUT / f"{shot.name}.png")
    if shot.fallback:
        candidates.append(DECK / shot.fallback)
    for c in candidates:
        if c.exists():
            return c.relative_to(ROOT).as_posix()
    return None


def gallery_blocks() -> dict[str, str]:
    """The README's ``hero`` and ``gallery`` blocks from the images on disk.
    Returns {marker name: block body}; never raises."""
    by_name = {s.name: s for s in SHOTS}
    hero_img = image_for(by_name["command"], prefer_gif=True)
    hero = (f'<p align="center"><img src="{hero_img}" alt="Sentinel Command screen with live camera tiles" '
            'width="100%"></p>') if hero_img else ""
    cells = []
    for shot in SHOTS[1:]:
        img = image_for(shot, prefer_gif=shot.name in GIFS)
        if img:
            title = re.match(r"\*\*(.+?)\.?\*\*", shot.caption)
            alt = title.group(1) if title else shot.name
            cells.append(f'<td width="50%" valign="top"><img src="{img}" alt="{alt}" width="100%"><br>'
                         f"<sub>{md_inline(shot.caption)}</sub></td>")
    rows = ["<tr>" + "".join(cells[i:i + 2]) + "</tr>" for i in range(0, len(cells), 2)]
    gallery = "<table>\n" + "\n".join(rows) + "\n</table>" if rows else ""
    return {"hero": hero, "gallery": gallery}


def md_inline(text: str) -> str:
    """Bold and code spans to HTML, for captions inside an HTML table (GitHub
    does not render Markdown inside a <td> on one line). Returns HTML."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", text)


def write_readme_blocks() -> None:
    """Replace each ``<!-- NAME:start -->…<!-- NAME:end -->`` block in the
    README. Raises SystemExit if a marker pair is missing."""
    text = README.read_text(encoding="utf-8")
    for name, body in gallery_blocks().items():
        pattern = re.compile(rf"(<!-- {name}:start -->)(.*?)(<!-- {name}:end -->)", re.S)
        if not pattern.search(text):
            raise SystemExit(f"README.md has no <!-- {name}:start --> / <!-- {name}:end --> markers")
        text = pattern.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(3)}", text)
    README.write_text(text, encoding="utf-8")
    for shot in SHOTS:
        img = image_for(shot, prefer_gif=shot.name in GIFS)
        print(f"  README {shot.name:16} <- {img or '(not captured yet: left out)'}")


# --- live capture -----------------------------------------------------------

def count_playing(page, window_ms: int = 2000) -> int:
    """Tiles whose <video> is decoding and advancing over *window_ms*.
    Returns the count; never raises on a page without video."""
    before = page.evaluate(PLAYING_JS)
    page.wait_for_timeout(window_ms)
    after = page.evaluate(PLAYING_JS)
    return sum(1 for (_, t0), (ready, t1) in zip(before, after) if ready >= 2 and t1 - t0 > 0.5)


def wait_playing(page, need: int, timeout_s: float = 60.0) -> int:
    """Poll until *need* tiles play or the timeout passes. Returns how many
    were playing at the end."""
    deadline = time.monotonic() + timeout_s
    playing = 0
    while time.monotonic() < deadline:
        playing = count_playing(page)
        if playing >= need:
            break
    return playing


def open_shot(page, base: str, shot: Shot, live_plate: str) -> int:
    """Navigate to *shot* and let it settle. Returns the playing-tile count
    (0 for screens without video)."""
    page.goto(base + shot.path.format(live_plate=live_plate))
    page.wait_for_load_state("networkidle")
    if shot.wall_filter:
        page.get_by_role("button", name=re.compile(rf"^{shot.wall_filter}")).click()
    if shot.path.startswith("/map"):
        page.wait_for_function("document.querySelectorAll('.leaflet-tile-loaded').length > 8", timeout=30000)
    page.wait_for_timeout(2500)  # fonts, crops and SSE backlog
    return wait_playing(page, shot.videos) if shot.videos else 0


def pick_live_plate(page, base: str) -> str:
    """The most-read live plate seen on a sandbox (non-local) camera, from
    GET /api/plates/suggest. Raises SystemExit if there is none."""
    data = page.request.get(f"{base}/api/plates/suggest?limit=50").json()
    for item in data.get("top_live", []):
        cams = item.get("camera_ids") or []
        if cams and any(not str(c).startswith("local") for c in cams):
            return item["plate"]
    raise SystemExit("no live plate read on a sandbox camera yet - wait for cam06 to read one")


def to_gif(ffmpeg: str, webm: Path, start_s: float, out: Path) -> None:
    """6 s of *webm* from *start_s* as a looping 960 px GIF. Raises
    CalledProcessError if ffmpeg fails."""
    vf = ("fps=10,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=160[p];"
          "[b][p]paletteuse=dither=bayer:bayer_scale=4")
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-ss", f"{start_s:.2f}", "-t", "6", "-i", str(webm),
                    "-vf", vf, "-loop", "0", str(out)], check=True)


def capture(base: str, user: str) -> int:
    """Sign in, capture every shot and both GIFs. Returns the number of
    screens that needed live video and did not get it."""
    from playwright.sync_api import sync_playwright  # laptop venv only
    sys.path.insert(0, str(ROOT))
    from backend.core import config

    password = getpass.getpass(f"Password for {user}: ")
    OUT.mkdir(parents=True, exist_ok=True)
    short = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=False)
        try:
            ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=1)
            page = ctx.new_page()
            page.goto(f"{base}/login?next=/command")
            page.wait_for_selector("#login-username")
            page.wait_for_timeout(1000)
            page.screenshot(path=str(OUT / "login.png"))
            print("  login            captured")
            page.fill("#login-username", user)
            page.fill("#login-password", password)
            page.click("button[type=submit]")
            page.wait_for_url("**/command", timeout=20000)
            live_plate = pick_live_plate(page, base)
            print(f"  live plate for Search: {live_plate}")
            for shot in SHOTS:
                if shot.name == "login":
                    continue
                playing = open_shot(page, base, shot, live_plate)
                page.screenshot(path=str(OUT / f"{shot.name}.png"))
                note = f"{playing}/{shot.videos} tiles playing" if shot.videos else "captured"
                if shot.videos and playing < shot.videos:
                    short += 1
                    note += "  <-- FEWER THAN WANTED: recapture when the feeds are up"
                print(f"  {shot.name:16} {note}")
            state = ctx.storage_state()
            ctx.close()

            with tempfile.TemporaryDirectory(prefix="readme-gif-") as tmp:
                for name, path in GIFS.items():
                    shot = next(s for s in SHOTS if s.name == name)
                    rec = browser.new_context(viewport=VIEWPORT, storage_state=state,
                                              record_video_dir=tmp,
                                              record_video_size={"width": 1280, "height": 720})
                    t0 = time.monotonic()
                    rpage = rec.new_page()
                    playing = open_shot(rpage, base, shot, live_plate)
                    start = time.monotonic() - t0
                    rpage.wait_for_timeout(7000)
                    video = rpage.video
                    rec.close()
                    if playing < shot.videos:
                        short += 1
                        print(f"  {name}.gif      skipped: {playing}/{shot.videos} tiles playing")
                        continue
                    to_gif(config.ffmpeg(), Path(video.path()), start, OUT / f"{name}.gif")
                    size = (OUT / f"{name}.gif").stat().st_size / 1e6
                    print(f"  {name}.gif      {playing} tiles playing, {size:.1f} MB")
        finally:
            browser.close()
    return short


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--user", help="platform account to sign in with (password is prompted)")
    ap.add_argument("--base", default="http://127.0.0.1:8000", help="platform URL (default: the laptop)")
    ap.add_argument("--gallery-only", action="store_true", help="only regenerate the README blocks")
    args = ap.parse_args()
    short = 0
    if not args.gallery_only:
        if not args.user:
            ap.error("--user is required unless --gallery-only")
        short = capture(args.base.rstrip("/"), args.user)
    write_readme_blocks()
    if short:
        print(f"{short} capture(s) had fewer playing tiles than wanted - rerun when the feeds are up")
    return 1 if short else 0


if __name__ == "__main__":
    raise SystemExit(main())
