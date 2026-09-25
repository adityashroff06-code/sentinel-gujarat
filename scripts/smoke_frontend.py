"""Playwright smoke for the frontend (tasks S3.2 + S3.3).

Run from the repo root as ``.venv/Scripts/python scripts/smoke_frontend.py``.

Starts the API itself (``python -m backend.app``) against a FRESH temp
test database — seeded by ``backend.tools.seed_registry`` (30 cameras)
with a viewer and an admin account created directly through
``backend.core.passwords`` — and drives the BUILT frontend served by the
API (``npm --prefix frontend run build`` first) through headless
Chromium. The SSE assertion runs through the real port, never TestClient
(S3.1a surprise). Asserts:

S3.2 (foundation — all kept green):
- visiting /map signed out lands on /login;
- signing in as the viewer works and shows the role in the header;
- /map renders one pin per camera (pins == camera count == 30);
- /cameras shows 30 rows; the onboarding form and CSV import are HIDDEN
  for the viewer;
- /watchlist hides add/remove for the viewer AND the API refuses the
  mutation (403 — hidden, then refused);
- as admin: the CSV import of tests/fixtures/import_3rows.csv shows
  2 accepted / 1 rejected, and a watchlist add/remove round-trips;

S3.3 (operations screens), after ``backend.tools.demo_seed inject``
against the same temp database (with a throwaway crop image attached to
the demo rows, since the seeder writes no image files):
- /command: the F46 "Start here" panel names a plate to try, a person
  count is shown, and — with /api/workers stubbed to ``available:false``
  — the feed-status strip says the pipeline is down, never a blank page;
- /route/GJ01AB1234: numbered pins on 3 cameras, 4 timeline entries with
  crops (the near-miss marked ambiguity), a header naming 3 departments,
  a provenance badge on every stop;
- /search?plate=GJ01: rows with crop <img> thumbnails loaded through the
  session cookie, provenance badges on every row; filtering by vehicle
  class ``truck`` returns only truck rows;
- /alerts: the seeded alerts render with provenance badges; an alert
  inserted via ``backend.core.alerts.create_alert`` in THIS process
  appears within 3 s over SSE without a reload; acknowledge persists
  across a reload;
- /wall at 4 tiles: exactly 4 playlist requests (one per visible tile;
  the streams may 404/503 — no worker runs), and paging destroys the
  first 4 players (0 further playlist/segment requests for them);
- role gating: Reports and Zones are hidden from the viewer's nav,
  /reports reached directly shows the needs-evaluator-access state, and
  ack buttons are hidden for the viewer;
- screenshots of every screen land in data/screens/.

The throwaway API keys and account passwords are generated per run and
never printed (root CLAUDE.md rule 1). Exits 0 on success.
"""

from __future__ import annotations

import base64
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))  # `backend` imports work from scripts/ too
PY = str(REPO / ".venv" / "Scripts" / "python.exe")
SCREENS = REPO / "data" / "screens"
FIXTURE_CSV = REPO / "tests" / "fixtures" / "import_3rows.csv"

# --- environment for the API + tools: a fresh, isolated database ------------
# Set BEFORE any backend import so config reads these, not .env / defaults.

_TMP = Path(tempfile.mkdtemp(prefix="sentinel-smoke-"))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = _free_port()
BASE = f"http://127.0.0.1:{PORT}"

os.environ.update(
    {
        "SENTINEL_DB": str(_TMP / "smoke.db"),
        "SENTINEL_LOG_DIR": str(_TMP / "logs"),
        "SENTINEL_API_PORT": str(PORT),
        "SENTINEL_API_KEY_ADMIN": secrets.token_urlsafe(32),
        "SENTINEL_API_KEY_VIEWER": secrets.token_urlsafe(32),
        "SENTINEL_HEALTH_INTERVAL_S": "0",  # no background probing here
        "SENTINEL_PUBLIC_HOST": "",  # local run: cookie must not be Secure
    }
)

VIEWER_USER, VIEWER_PASS = "viewer_smoke", secrets.token_urlsafe(12)
ADMIN_USER, ADMIN_PASS = "admin_smoke", secrets.token_urlsafe(12)

_passed: list[str] = []


def ok(label: str) -> None:
    _passed.append(label)
    print(f"PASS: {label}")


def fail(label: str) -> None:
    print(f"FAIL: {label}")
    raise SystemExit(1)


def check(cond: bool, label: str) -> None:
    ok(label) if cond else fail(label)


def seed_database() -> int:
    """Seed the catalogue registry and create the two accounts. Returns
    the camera count."""
    r = subprocess.run(
        [PY, "-m", "backend.tools.seed_registry"],
        cwd=REPO, env=os.environ.copy(), capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        fail("seed_registry seeded the fresh database")
    print(r.stdout.strip())

    from backend.core import db as dbmod  # imported after env is set
    from backend.core import passwords

    con = dbmod.connect()
    try:
        dbmod.migrate(con)
        now = dbmod.utcnow()
        for username, password, role in (
            (VIEWER_USER, VIEWER_PASS, "viewer"),
            (ADMIN_USER, ADMIN_PASS, "admin"),
        ):
            con.execute(
                "INSERT INTO users (username, password_hash, role, active, created_at)"
                " VALUES (?, ?, ?, 1, ?)",
                (username, passwords.hash_password(password), role, now),
            )
        con.commit()
        return con.execute("SELECT COUNT(*) FROM cameras").fetchone()[0]
    finally:
        con.close()


def start_api() -> subprocess.Popen:
    log = open(_TMP / "api.log", "w", encoding="utf-8")
    proc = subprocess.Popen(
        [PY, "-m", "backend.app"],
        cwd=REPO, env=os.environ.copy(), stdout=log, stderr=subprocess.STDOUT,
    )
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
    log.close()
    print((_TMP / "api.log").read_text(encoding="utf-8")[-3000:], file=sys.stderr)
    fail("API came up on /api/health")


# ---------------------------------------------------------------- S3.3 setup

CROPS_DIR = REPO / "data" / "crops"
SMOKE_CROP_REL = "smoke/smoke_demo.jpg"  # crop_path stored on the demo rows

#: 1x1 white JPEG — fallback when OpenCV is unavailable in the venv.
_TINY_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHR"
    "ofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QA"
    "FAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AVN"
    "//2Q=="
)


def seed_demo() -> None:
    """Run ``backend.tools.demo_seed inject`` against the smoke's temp DB
    (the env at module top points every backend tool at it)."""
    r = subprocess.run(
        [PY, "-m", "backend.tools.demo_seed", "inject"],
        cwd=REPO, env=os.environ.copy(), capture_output=True, text=True,
        timeout=300,
    )
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        fail("demo_seed inject seeded the demo route")
    print(r.stdout.strip())


def demo_sighting_count() -> int:
    """Count the demo rows the seeder wrote (provenance='demo')."""
    from backend.core import db as dbmod

    con = dbmod.connect()
    try:
        return con.execute(
            "SELECT COUNT(*) FROM sightings WHERE provenance = 'demo'"
        ).fetchone()[0]
    finally:
        con.close()


def attach_demo_crops() -> None:
    """Write a throwaway crop image and point every demo sighting at it:
    demo_seed stores no image, but the smoke must prove that crop <img>
    thumbnails load through the session cookie. Cleaned up in main()."""
    target = CROPS_DIR / SMOKE_CROP_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    try:  # a real-looking crop when OpenCV is around (it ships with ml/)
        import cv2
        import numpy as np

        img = np.full((90, 160, 3), 40, dtype=np.uint8)
        cv2.rectangle(img, (10, 25), (150, 65), (205, 205, 205), -1)
        cv2.putText(img, "DEMO", (34, 58), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                    (30, 30, 30), 2)
        cv2.imwrite(str(target), img)
    except ImportError:
        target.write_bytes(base64.b64decode(_TINY_JPEG_B64))

    from backend.core import db as dbmod

    con = dbmod.connect()
    try:
        con.execute(
            "UPDATE sightings SET crop_path = ? WHERE provenance = 'demo'",
            (SMOKE_CROP_REL,),
        )
        con.commit()
    finally:
        con.close()


def insert_live_alert():
    """Insert one fresh watchlist alert through the REAL
    ``backend.core.alerts.create_alert`` in this process, against the
    temp DB. Uses cam06 (its seeded alert is ~20 min in the past, so the
    5-minute cooldown is clear). Returns the alert row or None."""
    from backend.core import db as dbmod
    from backend.core.alerts import create_alert

    con = dbmod.connect()
    try:
        sight = con.execute(
            "SELECT * FROM sightings WHERE plate = 'GJ01AB1234'"
            " AND camera_id = 'cam06' ORDER BY sighting_id DESC LIMIT 1"
        ).fetchone()
        wl = con.execute(
            "SELECT * FROM watchlist WHERE plate = 'GJ01AB1234'"
        ).fetchone()
        if sight is None or wl is None:
            return None
        row = create_alert(
            con, kind="watchlist", camera_id="cam06", severity=wl["severity"],
            seen_at=datetime.now(timezone.utc), clock_source="demo",
            sighting=sight, wl_row=wl, rule="exact", distance=0.0,
        )
        con.commit()
        return row
    finally:
        con.close()


def sign_in(page, username: str, password: str) -> None:
    page.fill("#login-username", username)
    page.fill("#login-password", password)
    page.click("button[type=submit]")
    page.wait_for_url("**/map", timeout=15000)


def count_when_stable(locator, expected: int, timeout_s: float = 15.0) -> int:
    """Poll a locator until it reaches `expected` (or timeout); returns
    the final count."""
    deadline = time.monotonic() + timeout_s
    n = -1
    while time.monotonic() < deadline:
        n = locator.count()
        if n == expected:
            return n
        time.sleep(0.25)
    return n


def main() -> int:
    if not (REPO / "frontend" / "dist" / "index.html").is_file():
        print("frontend/dist is missing — run: npm --prefix frontend run build", file=sys.stderr)
        return 2
    SCREENS.mkdir(parents=True, exist_ok=True)

    camera_count = seed_database()
    check(camera_count == 30, f"fresh registry seeded with 30 cameras (got {camera_count})")

    api_proc = start_api()
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 768})

            # --- signed out: /map lands on /login ---------------------------
            page.goto(f"{BASE}/map")
            page.wait_for_url("**/login**", timeout=15000)
            page.wait_for_selector("#login-username", timeout=10000)
            check("/login" in page.url, "visiting /map signed out lands on /login")
            page.screenshot(path=str(SCREENS / "s32-login.png"))

            # --- viewer session ---------------------------------------------
            sign_in(page, VIEWER_USER, VIEWER_PASS)
            role = page.locator(".session .role").inner_text(timeout=10000)
            check(role.strip().lower() == "viewer", "signed in as the seeded viewer (role shown)")

            # /map: one pin per camera
            page.wait_for_selector(".leaflet-container", timeout=15000)
            pins = count_when_stable(
                page.locator(".leaflet-overlay-pane path"), camera_count
            )
            check(
                pins == camera_count,
                f"map pins == camera count ({pins} == {camera_count})",
            )
            page.screenshot(path=str(SCREENS / "s32-map.png"))

            # /cameras: 30 rows; onboarding + import hidden for the viewer
            page.goto(f"{BASE}/cameras")
            page.wait_for_selector(".cameras-table tbody tr", timeout=15000)
            rows = count_when_stable(
                page.locator(".cameras-table tbody tr"), camera_count
            )
            check(rows == 30, f"cameras table has 30 rows (got {rows})")
            check(
                page.locator("#add-camera").count() == 0
                and page.locator("#import-csv").count() == 0,
                "onboarding form and CSV import hidden for the viewer",
            )
            page.screenshot(path=str(SCREENS / "s32-cameras.png"), full_page=True)

            # /watchlist: add/remove hidden for the viewer, then refused
            page.goto(f"{BASE}/watchlist")
            page.wait_for_selector(".state-empty, .watchlist-table", timeout=15000)
            check(
                page.locator("#add-watchlist").count() == 0,
                "watchlist add form hidden for the viewer",
            )
            status = page.evaluate(
                """async () => {
                    const r = await fetch('/api/watchlist', {
                        method: 'POST', credentials: 'same-origin',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({plate: 'GJ00SMOKE1',
                            category: 'suspect', severity: 'low'})
                    });
                    return r.status;
                }"""
            )
            check(status == 403, f"watchlist mutation refused for the viewer (403, got {status})")
            page.screenshot(path=str(SCREENS / "s32-watchlist.png"))

            # --- sign out, sign in as admin ---------------------------------
            page.click(".session button")
            page.wait_for_url("**/login**", timeout=15000)
            ok("sign-out returns to /login")
            sign_in(page, ADMIN_USER, ADMIN_PASS)

            # CSV import: 2 accepted / 1 rejected, per-row reasons
            page.goto(f"{BASE}/cameras")
            page.wait_for_selector("#import-csv", timeout=15000)
            page.set_input_files("#import-file", str(FIXTURE_CSV))
            page.click("#import-csv button[type=submit]")
            page.wait_for_selector(".import-results", timeout=15000)
            accepted = page.locator(".import-results .accepted").first.inner_text()
            rejected = page.locator(".import-results .rejected").first.inner_text()
            check(
                accepted.startswith("2 ") and rejected.startswith("1 "),
                f"CSV import shows 2 accepted / 1 rejected (got '{accepted}' / '{rejected}')",
            )
            check(
                page.locator(".import-results .rejected-list li").count() == 1,
                "rejected row carries its per-row reason",
            )
            page.screenshot(path=str(SCREENS / "s32-cameras-import.png"), full_page=True)

            # watchlist round-trip as admin
            page.goto(f"{BASE}/watchlist")
            page.wait_for_selector("#add-watchlist", timeout=15000)
            page.fill("#wl-plate", "GJ05AB1234")
            page.fill("#wl-reason", "smoke round-trip")
            page.click("#add-watchlist button[type=submit]")
            page.wait_for_selector(".watchlist-table td.plate", timeout=15000)
            plate_cell = page.locator(".watchlist-table td.plate").first.inner_text()
            check(plate_cell.strip() == "GJ05AB1234", "watchlist add round-trips as admin")
            page.screenshot(path=str(SCREENS / "s32-watchlist-admin.png"))
            page.click(".watchlist-table button.danger")
            page.wait_for_selector(".state-empty", timeout=15000)
            ok("watchlist remove round-trips as admin")

            # ==========================================================
            # S3.3 — operations screens (still signed in as admin)
            # ==========================================================
            seed_demo()
            n_demo = demo_sighting_count()
            check(n_demo == 24, f"demo_seed injected the demo route (24 sightings, got {n_demo})")
            attach_demo_crops()

            # --- Command: Start here, person count, feed-status (F46) ---
            # /api/workers stubbed to the no-snapshot shape so the strip's
            # "pipeline dead" state is asserted deterministically.
            page.route(
                "**/api/workers",
                lambda route: route.fulfill(
                    status=200, content_type="application/json",
                    body='{"available": false}',
                ),
            )
            page.goto(f"{BASE}/command")
            page.wait_for_selector("#start-here", timeout=15000)
            start_txt = page.locator("#start-here").inner_text()
            check(
                "GJ01AB1234" in start_txt,
                "Start here panel names a plate to try (GJ01AB1234)",
            )
            person_txt = page.locator("#person-count").inner_text(timeout=10000)
            check(
                any(ch.isdigit() for ch in person_txt),
                f"Command shows a person count ({person_txt.split()[0]!r})",
            )
            strip_txt = page.locator(".feed-status").inner_text(timeout=10000)
            check(
                "pipeline down" in strip_txt.lower(),
                "feed-status strip says the pipeline is down when worker stats are absent",
            )
            page.screenshot(path=str(SCREENS / "s33-command.png"), full_page=True)
            page.unroute("**/api/workers")

            # --- Route: THE scored view ---------------------------------
            page.goto(f"{BASE}/route/GJ01AB1234")
            page.wait_for_selector(".route-stop", timeout=15000)
            stops = count_when_stable(page.locator(".route-stop"), 4)
            check(stops == 4, f"route timeline has 4 entries (got {stops})")
            check(
                page.locator(".route-stop .match-chip.match-ambiguity").count() == 1,
                "the near-miss stop is marked ambiguity",
            )
            pins = count_when_stable(page.locator(".seqtip"), 3)
            check(pins == 3, f"numbered route pins on 3 cameras (got {pins})")
            depts = page.locator("#route-header .route-depts .badge").count()
            check(depts == 3, f"route header names 3 departments (got {depts})")
            check(
                page.locator(".route-stop .prov-badge").count() == 4,
                "every route stop carries a provenance badge",
            )
            check(
                page.locator(".route-stop img.crop-thumb").count() == 4,
                "route timeline entries carry crops",
            )
            page.screenshot(path=str(SCREENS / "s33-route.png"), full_page=True)

            # --- Search: thumbnails via cookie, provenance, class filter -
            page.goto(f"{BASE}/search?plate=GJ01")
            page.wait_for_selector(".search-table tbody tr", timeout=15000)
            rows = page.locator(".search-table tbody tr").count()
            check(rows >= 3, f"/search?plate=GJ01 returns rows ({rows})")
            check(
                page.locator(".search-table tbody .prov-badge").count() == rows,
                "every search row carries a provenance badge",
            )
            deadline = time.monotonic() + 10
            loaded = 0
            while time.monotonic() < deadline:
                loaded = page.evaluate(
                    "() => [...document.querySelectorAll('.search-table img.crop-thumb')]"
                    ".filter((i) => i.complete && i.naturalWidth > 0).length"
                )
                if loaded >= 1:
                    break
                time.sleep(0.25)
            check(loaded >= 1, f"search crop <img> thumbnails load via cookie auth ({loaded} loaded)")
            page.screenshot(path=str(SCREENS / "s33-search.png"), full_page=True)

            page.fill("#s-plate", "")
            page.click("form[role=search] button[type=submit]")
            all_rows = count_when_stable(page.locator(".search-table tbody tr"), n_demo)
            check(all_rows == n_demo, f"unfiltered search shows all {n_demo} demo rows (got {all_rows})")
            page.select_option("#s-class", "truck")
            classes = page.eval_on_selector_all(
                ".search-table tbody td.vclass", "els => els.map((e) => e.textContent.trim())"
            )
            check(
                len(classes) > 0 and all(c == "truck" for c in classes),
                f"class filter 'truck' returns only truck rows ({len(classes)} rows)",
            )

            # --- Alerts: SSE through the real port, ack persists ---------
            page.goto(f"{BASE}/alerts")
            page.wait_for_selector(".alert-card", timeout=15000)
            initial = count_when_stable(page.locator(".alert-card"), 4)
            check(initial == 4, f"alerts page shows the 4 seeded demo alerts (got {initial})")
            check(
                page.locator(".alert-card .prov-badge").count() == initial,
                "every alert card carries a provenance badge",
            )
            time.sleep(1.0)  # let the EventSource finish subscribing
            new_alert = insert_live_alert()
            check(new_alert is not None, "create_alert inserted a fresh alert (cooldown clear)")
            t0 = time.monotonic()
            appeared = False
            while time.monotonic() - t0 < 3.0:
                if page.locator(".alert-card").count() >= initial + 1:
                    appeared = True
                    break
                time.sleep(0.1)
            check(appeared, "SSE alert card appeared within 3 s without reload")
            card_sel = f'.alert-card[data-alert-id="{new_alert["alert_id"]}"]'
            page.click(f"{card_sel} button.ack")
            page.wait_for_selector(f"{card_sel}.acked", timeout=5000)
            page.reload()
            page.wait_for_selector(card_sel, timeout=15000)
            check(
                "acked" in (page.locator(card_sel).get_attribute("class") or ""),
                "acknowledge persists across a reload",
            )
            page.screenshot(path=str(SCREENS / "s33-alerts.png"), full_page=True)

            # --- Live Wall: one pull per visible tile, paging destroys ---
            playlist_re = re.compile(r"/api/hls/([^/]+)/live\.m3u8")
            hls_re = re.compile(r"/api/hls/([^/]+)/")
            hls_log: list[str] = []

            def on_request(req) -> None:
                if "/api/hls/" in req.url:
                    hls_log.append(req.url)

            page.on("request", on_request)
            page.goto(f"{BASE}/wall")
            page.wait_for_selector(".wall .grid.g4 .tile", timeout=15000)
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if len([u for u in hls_log if playlist_re.search(u)]) >= 4:
                    break
                time.sleep(0.1)
            first_playlists = [playlist_re.search(u).group(1) for u in hls_log if playlist_re.search(u)]
            check(
                len(first_playlists) == 4 and len(set(first_playlists)) == 4,
                f"wall at 4 tiles made exactly 4 playlist requests, one per visible tile (got {len(first_playlists)})",
            )
            first4 = set(first_playlists)
            page.click("#wall-next")
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                new_cams = {
                    m.group(1) for u in hls_log
                    if (m := playlist_re.search(u)) and m.group(1) not in first4
                }
                if len(new_cams) >= 4:
                    break
                time.sleep(0.1)
            check(
                len(new_cams) == 4 and new_cams.isdisjoint(first4),
                f"paging mounted 4 new players ({sorted(new_cams)})",
            )
            time.sleep(0.7)  # let anything already in flight settle
            baseline = len([u for u in hls_log if (m := hls_re.search(u)) and m.group(1) in first4])
            time.sleep(4.5)  # a leaked player's jittered retry would fire here
            after = len([u for u in hls_log if (m := hls_re.search(u)) and m.group(1) in first4])
            check(
                after == baseline,
                f"first 4 players destroyed on paging (0 further playlist/segment requests, {after - baseline} seen)",
            )
            page.remove_listener("request", on_request)
            page.screenshot(path=str(SCREENS / "s33-wall.png"))

            # --- Zones (admin) ------------------------------------------
            page.goto(f"{BASE}/zones")
            page.wait_for_selector("#zone-cam", timeout=15000)
            check(
                page.locator(".zone-canvas").count() == 1
                and page.locator("#save-zones").count() == 1,
                "zone editor renders (camera select, canvas, save)",
            )
            page.screenshot(path=str(SCREENS / "s33-zones.png"), full_page=True)

            # --- Reports (admin): links, person column, provenance -------
            page.goto(f"{BASE}/reports")
            page.wait_for_selector("#report-links", timeout=15000)
            check(
                page.locator("#report-links a").count() >= 4,
                "report export links present (detections, gap, OpenAPI)",
            )
            check(
                "person" in page.locator(".objects-table thead").inner_text().lower(),
                "reports object-counts table includes a person column",
            )
            page.wait_for_selector("#report-preview tbody tr", timeout=15000)
            prev_rows = page.locator("#report-preview tbody tr").count()
            check(
                prev_rows > 0
                and page.locator("#report-preview .prov-badge").count() == prev_rows,
                "reports preview rows carry provenance badges",
            )
            page.screenshot(path=str(SCREENS / "s33-reports.png"), full_page=True)

            # --- role gating for the viewer (hidden, not just refused) ---
            page.click(".session button")
            page.wait_for_url("**/login**", timeout=15000)
            sign_in(page, VIEWER_USER, VIEWER_PASS)
            check(
                page.locator('.nav a[href="/reports"]').count() == 0
                and page.locator('.nav a[href="/zones"]').count() == 0,
                "Reports and Zones hidden from the viewer's nav",
            )
            page.goto(f"{BASE}/reports")
            page.wait_for_selector(".needs-access", timeout=15000)
            check(
                "evaluator" in page.locator(".needs-access").inner_text().lower(),
                "direct /reports as viewer shows the needs-evaluator-access state",
            )
            page.goto(f"{BASE}/alerts")
            page.wait_for_selector(".alert-card", timeout=15000)
            check(
                page.locator(".alert-card button.ack").count() == 0,
                "ack buttons hidden for the viewer",
            )

            browser.close()
    finally:
        api_proc.terminate()
        try:
            api_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            api_proc.kill()
        shutil.rmtree(_TMP, ignore_errors=True)
        # the throwaway crop written for the demo rows (attach_demo_crops)
        shutil.rmtree(CROPS_DIR / "smoke", ignore_errors=True)

    print(f"\nscreenshots: {SCREENS}")
    print(f"SMOKE PASS — {len(_passed)} assertions green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
