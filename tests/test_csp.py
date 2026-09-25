"""The Content-Security-Policy must permit what the real frontend loads.

Regression for 25 Sep: ``img-src https://*.tile.openstreetmap.org`` never
matched the bare ``tile.openstreetmap.org`` host every TileLayer used, so
every map tile was blocked (a blank grey map); and with no ``media-src``
the policy fell back to ``'self'``, which blocks the ``blob:`` MediaSource
URL hls.js attaches to each ``<video>`` — no Live Wall tile could play in a
real browser. The smoke never noticed: headless checks counted pins and
playlist requests, not painted tiles or playing video.

These tests read the frontend source for every tile URL, so adding a
basemap without widening the policy fails here, not in front of a judge.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import main as main_mod
from backend.core import db as dbmod

REPO = Path(__file__).resolve().parents[1]
FRONTEND_SRC = REPO / "frontend" / "src"

# a tile template: an https URL carrying the {z} placeholder
_TILE_URL = re.compile(r"https://([^/'\"`\s]+)/[^'\"`\s]*\{z\}")


def _directives(csp: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for part in csp.split(";"):
        tokens = part.split()
        if tokens:
            out[tokens[0]] = tokens[1:]
    return out


def _host_allowed(host: str, sources: list[str]) -> bool:
    """CSP host-source matching for https hosts (CSP3 §6.7.2.6, the subset
    used here): an exact host, or ``*.suffix`` matching strict subdomains
    only — never the bare suffix itself."""
    for src in sources:
        if not src.startswith("https://"):
            continue
        pattern = src[len("https://"):].rstrip("/")
        if pattern.startswith("*."):
            if host.endswith(pattern[1:]) and host != pattern[2:]:
                return True
        elif host == pattern:
            return True
    return False


def _frontend_tile_hosts() -> set[str]:
    hosts: set[str] = set()
    for path in FRONTEND_SRC.rglob("*.js*"):
        for m in _TILE_URL.finditer(path.read_text(encoding="utf-8")):
            # a {s} subdomain placeholder stands for a real subdomain letter
            hosts.add(m.group(1).replace("{s}", "a"))
    return hosts


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    """The real app on a per-test database (TrustedHost wants localhost)."""
    monkeypatch.setenv("SENTINEL_DB", str(tmp_path / "csp.db"))
    monkeypatch.delenv("SENTINEL_PUBLIC_HOST", raising=False)
    con = dbmod.connect()
    dbmod.migrate(con)
    con.close()
    return TestClient(main_mod.create_app(), base_url="http://localhost")


def _served_csp(client: TestClient) -> dict[str, list[str]]:
    r = client.get("/api/health")
    return _directives(r.headers["Content-Security-Policy"])


def test_csp_wildcard_never_matches_the_bare_host():
    # the exact shape of the 25 Sep defect, pinned
    assert not _host_allowed("tile.openstreetmap.org",
                             ["https://*.tile.openstreetmap.org"])
    assert _host_allowed("a.basemaps.cartocdn.com",
                         ["https://*.basemaps.cartocdn.com"])


def test_csp_permits_every_tile_host_the_frontend_uses(client):
    hosts = _frontend_tile_hosts()
    assert hosts, "no tile URL found in frontend/src — the scan is broken"
    img = _served_csp(client)["img-src"]
    blocked = sorted(h for h in hosts if not _host_allowed(h, img))
    assert not blocked, f"CSP img-src blocks these tile hosts: {blocked}"


def test_csp_lets_hlsjs_play_blob_media_and_run_its_worker(client):
    d = _served_csp(client)
    assert "blob:" in d.get("media-src", []), "hls.js MediaSource needs media-src blob:"
    assert "blob:" in d.get("worker-src", []), "hls.js demux worker needs worker-src blob:"
    # the rest of the policy stays tight
    assert d["default-src"] == ["'self'"]
    assert d["connect-src"] == ["'self'"]
    assert d["frame-ancestors"] == ["'none'"]
