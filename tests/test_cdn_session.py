"""backend/core/cdn_session.py — origin-guard regression (wave-2 review).

The fetch guard must be boundary-exact: with the CDN at
``https://cctv.example``, a bare ``startswith`` admitted
``https://cctv.example.evil.tld/...``. No network is touched — the guard
refuses before any request is made.
"""

from __future__ import annotations

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
