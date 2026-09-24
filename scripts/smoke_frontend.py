"""Playwright smoke for the frontend foundation (task S3.2).

Run from the repo root as ``.venv/Scripts/python scripts/smoke_frontend.py``.

Starts the API itself (``python -m backend.app``) against a FRESH temp
test database — seeded by ``backend.tools.seed_registry`` (30 cameras)
with a viewer and an admin account created directly through
``backend.core.passwords`` — and drives the BUILT frontend served by the
API (``npm --prefix frontend run build`` first) through headless
Chromium. Asserts:

- visiting /map signed out lands on /login;
- signing in as the viewer works and shows the role in the header;
- /map renders one pin per camera (pins == camera count == 30);
- /cameras shows 30 rows; the onboarding form and CSV import are HIDDEN
  for the viewer;
- /watchlist hides add/remove for the viewer AND the API refuses the
  mutation (403 — hidden, then refused);
- as admin: the CSV import of tests/fixtures/import_3rows.csv shows
  2 accepted / 1 rejected, and a watchlist add/remove round-trips;
- screenshots of every page land in data/screens/.

The throwaway API keys and account passwords are generated per run and
never printed (root CLAUDE.md rule 1). Exits 0 on success.
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
import urllib.request
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

            browser.close()
    finally:
        api_proc.terminate()
        try:
            api_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            api_proc.kill()
        shutil.rmtree(_TMP, ignore_errors=True)

    print(f"\nscreenshots: {SCREENS}")
    print(f"SMOKE PASS — {len(_passed)} assertions green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
