"""Authentication and roles (docs/api.md §7 auth transport; decisions F4, F23).

``X-API-Key`` header everywhere (roles ``viewer``/``admin`` from the two
configured keys). Additionally the ``sentinel_key`` cookie — set by
``POST /api/session`` — is accepted for **GET** on ``/crops/*``,
``/api/hls/*`` and ``/api/alerts/stream`` only, because ``<img>``, hls.js
and ``EventSource`` cannot send custom headers. Mutations always require
the header **and** admin; a cookie alone never authorises a change.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from backend.core import config

COOKIE_NAME = "sentinel_key"
_COOKIE_GET_PREFIXES = ("/crops/", "/api/hls/")
_COOKIE_GET_EXACT = ("/api/alerts/stream",)


def role_for_key(key: str | None) -> str | None:
    """Map an API key to its role; None for anything else (or unset keys)."""
    if not key:
        return None
    if key == config.api_key_admin():
        return "admin"
    if key == config.api_key_viewer():
        return "viewer"
    return None


def _cookie_allowed(request: Request) -> bool:
    if request.method != "GET":
        return False
    path = request.url.path
    return path.startswith(_COOKIE_GET_PREFIXES) or path in _COOKIE_GET_EXACT


def header_role(request: Request) -> str | None:
    return role_for_key(request.headers.get("X-API-Key"))


def resolve_role(request: Request) -> str | None:
    """The effective role: header first; the cookie only where allowed."""
    role = header_role(request)
    if role:
        return role
    if _cookie_allowed(request):
        return role_for_key(request.cookies.get(COOKIE_NAME))
    return None


def require_auth(request: Request) -> str:
    """Dependency: any authenticated role; 401 otherwise."""
    role = resolve_role(request)
    if role is None:
        raise HTTPException(status_code=401, detail="missing or invalid API key")
    request.state.role = role
    return role


def require_admin(request: Request) -> str:
    """Dependency for mutations: header-derived admin only (never the cookie)."""
    role = header_role(request)
    if role is None:
        raise HTTPException(status_code=401, detail="missing or invalid API key")
    if role != "admin":
        raise HTTPException(status_code=403, detail="admin key required")
    request.state.role = role
    return role


def assert_keys_configured() -> None:
    """The API refuses to start if either key is unset (docs/api.md §7)."""
    if not config.api_key_admin() or not config.api_key_viewer():
        raise RuntimeError(
            "SENTINEL_API_KEY_ADMIN and SENTINEL_API_KEY_VIEWER must both be set "
            "(generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\")"
        )
    if config.api_key_admin() == config.api_key_viewer():
        raise RuntimeError("SENTINEL_API_KEY_ADMIN and SENTINEL_API_KEY_VIEWER must differ")
