"""Authentication, roles and sessions (docs/api.md §7 "Auth transport", §9;
decisions F23, F41; task S3.0).

Two credentials reach the same authorisation check:

- **People sign in** (F41): ``POST /api/auth/login`` verifies a ``users``
  row (scrypt, ``backend/core/passwords.py``) and sets the
  ``sentinel_session`` cookie — ``HttpOnly``, ``SameSite=Strict``,
  ``Secure`` when ``SENTINEL_PUBLIC_HOST`` is set, ``SENTINEL_SESSION_TTL_H``
  hours (default 8), revocable server-side (``sessions.revoked_at``). The
  session authorises everything its role allows, mutations included; a
  session-authenticated mutation additionally requires an ``Origin`` header
  naming a configured host (CSRF defence — ``X-API-Key`` mutations are
  exempt, because a cross-site form cannot add a header).
- **Scripts use a key** (F23, unchanged): the ``X-API-Key`` header maps to
  ``viewer``/``admin``. The ``sentinel_key`` cookie set by
  ``POST /api/session`` is accepted for **GET** on ``/crops/*``,
  ``/api/hls/*`` and ``/api/alerts/stream`` only and never authorises a
  mutation.

Role ladder: ``viewer`` < ``evaluator`` < ``admin``.

Login throttle: 5 failures for one username, or from one address, lock
further attempts for 15 minutes; the lock lives in ``login_attempts`` so a
restart does not clear it. Login success, failure, lockout and logout each
write an ``audit`` row carrying the username — never a password.
"""

from __future__ import annotations

import secrets
import threading
import time
import urllib.parse
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from backend.core import config
from backend.core import db as dbmod
from backend.core import passwords

COOKIE_NAME = "sentinel_key"
SESSION_COOKIE = "sentinel_session"
_COOKIE_GET_PREFIXES = ("/crops/", "/api/hls/")
_COOKIE_GET_EXACT = ("/api/alerts/stream",)
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

ROLE_ORDER = {"viewer": 0, "evaluator": 1, "admin": 2}

_LOCK_AFTER = 5
_LOCK_MINUTES = 15
_USER_AGENT_MAX = 200

router = APIRouter(prefix="/api/auth", tags=["auth"])


# --- identity resolution ---------------------------------------------------

@dataclass(frozen=True)
class Identity:
    """Who is calling and how they authenticated."""

    actor: str                     # username, or "key:<role>" for key transport
    role: str                      # viewer | evaluator | admin
    transport: str                 # header | session | media-cookie
    session_id: str | None = None
    username: str | None = None
    expires_at: str | None = None


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


def _session_identity(request: Request) -> Identity | None:
    """Resolve the ``sentinel_session`` cookie to a live session, or None."""
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid:
        return None
    con = dbmod.connect()
    try:
        row = con.execute(
            "SELECT s.session_id, s.expires_at, s.revoked_at,"
            "       u.username, u.role, u.active"
            "  FROM sessions s JOIN users u ON u.user_id = s.user_id"
            " WHERE s.session_id = ?",
            (sid,),
        ).fetchone()
    finally:
        con.close()
    if row is None or row["revoked_at"] is not None or not row["active"]:
        return None
    if row["role"] not in ROLE_ORDER:
        return None
    try:
        expires = datetime.fromisoformat(row["expires_at"])
    except ValueError:
        return None
    if expires.tzinfo is None or expires <= datetime.now(timezone.utc):
        return None
    return Identity(
        actor=row["username"], role=row["role"], transport="session",
        session_id=row["session_id"], username=row["username"],
        expires_at=row["expires_at"],
    )


def resolve_identity(request: Request) -> Identity | None:
    """The effective identity: header key first, then the session cookie,
    then the legacy ``sentinel_key`` cookie on the allowed GET paths."""
    role = header_role(request)
    if role:
        return Identity(actor=f"key:{role}", role=role, transport="header")
    ident = _session_identity(request)
    if ident:
        return ident
    if _cookie_allowed(request):
        role = role_for_key(request.cookies.get(COOKIE_NAME))
        if role:
            return Identity(actor=f"key:{role}", role=role, transport="media-cookie")
    return None


def resolve_role(request: Request) -> str | None:
    """The effective role, or None (kept for callers of the S1.3a surface)."""
    ident = resolve_identity(request)
    return ident.role if ident else None


# --- CSRF: Origin on session-authenticated mutations ------------------------

def _allowed_origin_hosts() -> set[str]:
    hosts = {"localhost", "127.0.0.1"}
    if config.public_host():
        hosts.add(config.public_host())
    return hosts


def _check_origin(request: Request) -> None:
    """Session-cookie mutations must carry an Origin naming a configured
    host (docs/api.md §7: SameSite=Strict plus this check closes CSRF)."""
    origin = request.headers.get("Origin")
    if not origin:
        raise HTTPException(status_code=403, detail="mutation requires an Origin header")
    host = urllib.parse.urlsplit(origin).hostname
    if host is None or host.lower() not in _allowed_origin_hosts():
        raise HTTPException(status_code=403, detail="origin not allowed")


# --- authorisation dependencies --------------------------------------------

def _authorise(request: Request, minimum: str) -> str:
    ident = resolve_identity(request)
    if ident is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    if request.method not in _SAFE_METHODS and ident.transport == "session":
        _check_origin(request)
    if ROLE_ORDER[ident.role] < ROLE_ORDER[minimum]:
        raise HTTPException(status_code=403, detail=f"{minimum} role required")
    request.state.identity = ident
    request.state.role = ident.role
    request.state.actor = ident.actor
    return ident.role


def require_auth(request: Request) -> str:
    """Dependency: any authenticated identity; 401 otherwise."""
    return _authorise(request, "viewer")


def require_evaluator(request: Request) -> str:
    """Dependency: evaluator or admin (acknowledge, watchlist, reports,
    onboarding form — decision F41)."""
    return _authorise(request, "evaluator")


def require_admin(request: Request) -> str:
    """Dependency for admin-only mutations: an admin key, or an admin
    session with a matching Origin. The ``sentinel_key`` media cookie never
    authorises a mutation (it only resolves on GET)."""
    return _authorise(request, "admin")


def assert_keys_configured() -> None:
    """The API refuses to start if either key is unset (docs/api.md §7)."""
    if not config.api_key_admin() or not config.api_key_viewer():
        raise RuntimeError(
            "SENTINEL_API_KEY_ADMIN and SENTINEL_API_KEY_VIEWER must both be set "
            "(generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\")"
        )
    if config.api_key_admin() == config.api_key_viewer():
        raise RuntimeError("SENTINEL_API_KEY_ADMIN and SENTINEL_API_KEY_VIEWER must differ")


# --- reusable rate limit (docs/api.md §9) -----------------------------------

class RateLimiter:
    """Fixed-window in-process rate limit, used as a dependency:
    ``Depends(RateLimiter("route", limit=30, window_s=60))``.

    Keyed per identity (the authenticated actor when an auth dependency ran
    first, else the client address); over the limit returns 429 rather than
    queueing. State is per-instance and in-process — correct for the
    single-process demo API. Wired onto the route query, the report exports
    and the HLS relay when those land (S3.1a/S3.1b).
    """

    def __init__(self, name: str, limit: int, window_s: float) -> None:
        self.name = name
        self.limit = int(limit)
        self.window_s = float(window_s)
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def __call__(self, request: Request) -> None:
        """Count this request; raise HTTPException 429 over the limit."""
        key = getattr(request.state, "actor", None) or (
            request.client.host if request.client else "anonymous"
        )
        now = time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self.window_s:
                hits.popleft()
            if len(hits) >= self.limit:
                raise HTTPException(
                    status_code=429,
                    detail=f"rate limit exceeded ({self.name}); retry later",
                    headers={"Retry-After": str(int(self.window_s) or 1)},
                )
            hits.append(now)


# --- login throttle (database-backed; survives restart) ---------------------

def _throttle_keys(request: Request, username: str) -> tuple[str, str]:
    address = request.client.host if request.client else "unknown"
    return (f"user:{username.strip().lower()}", f"ip:{address}")


def _lock_active(con, keys: tuple[str, ...], now: datetime) -> bool:
    for key in keys:
        row = con.execute(
            "SELECT locked_until FROM login_attempts WHERE key = ?", (key,)
        ).fetchone()
        if row is None or not row["locked_until"]:
            continue
        try:
            locked_until = datetime.fromisoformat(row["locked_until"])
        except ValueError:
            continue
        if locked_until > now:
            return True
    return False


def _record_failure(con, keys: tuple[str, ...], now: datetime) -> None:
    for key in keys:
        row = con.execute(
            "SELECT failures, locked_until FROM login_attempts WHERE key = ?", (key,)
        ).fetchone()
        failures = int(row["failures"] or 0) if row else 0
        if row and row["locked_until"]:
            try:
                if datetime.fromisoformat(row["locked_until"]) <= now:
                    failures = 0  # the previous lock expired: a fresh window
            except ValueError:
                failures = 0
        failures += 1
        locked_until = (
            dbmod.iso(now + timedelta(minutes=_LOCK_MINUTES))
            if failures >= _LOCK_AFTER else None
        )
        con.execute(
            "INSERT INTO login_attempts (key, failures, locked_until) VALUES (?, ?, ?)"
            " ON CONFLICT(key) DO UPDATE SET failures = excluded.failures,"
            " locked_until = excluded.locked_until",
            (key, failures, locked_until),
        )


def _clear_attempts(con, keys: tuple[str, ...]) -> None:
    con.executemany("DELETE FROM login_attempts WHERE key = ?", [(k,) for k in keys])


def _audit_auth(con, *, actor: str | None, role: str | None, action: str) -> None:
    """One audit row for a login/logout event. Never receives a password."""
    con.execute(
        "INSERT INTO audit (at, actor, role, action, entity, entity_id)"
        " VALUES (?, ?, ?, ?, 'auth', ?)",
        (dbmod.utcnow(), actor, role, action, actor),
    )


_dummy_hash: str | None = None


def _get_dummy_hash() -> str:
    """A throwaway hash so unknown usernames cost the same as wrong
    passwords (no username enumeration by timing)."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = passwords.hash_password(secrets.token_urlsafe(16))
    return _dummy_hash


# --- the /api/auth endpoints ------------------------------------------------

class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024)


class MeOut(BaseModel):
    username: str | None    # null for key-authenticated callers
    role: str
    expires_at: str | None  # null for key-authenticated callers


class AuthMessageOut(BaseModel):
    detail: str


@router.post("/login", response_model=MeOut)
def login(body: LoginIn, request: Request, response: Response):
    """Sign in with a username and password; sets the ``sentinel_session``
    cookie (HttpOnly, SameSite=Strict, Secure when SENTINEL_PUBLIC_HOST is
    set). Throttled: 5 failures per username or address lock logins for
    15 minutes (the lock survives a restart). Audited on success and
    failure — the audit row never carries the password."""
    username = body.username.strip()
    keys = _throttle_keys(request, username)
    now = datetime.now(timezone.utc)
    con = dbmod.connect()
    try:
        if _lock_active(con, keys, now):
            _audit_auth(con, actor=username, role=None, action="auth.login.locked")
            con.commit()
            raise HTTPException(
                status_code=429,
                detail="too many failed logins; locked for 15 minutes",
                headers={"Retry-After": str(_LOCK_MINUTES * 60)},
            )
        user = con.execute(
            "SELECT user_id, username, password_hash, role, active FROM users"
            " WHERE username = ?",
            (username,),
        ).fetchone()
        stored = user["password_hash"] if user is not None else _get_dummy_hash()
        ok = passwords.verify_password(body.password, stored)
        if user is None or not user["active"] or user["role"] not in ROLE_ORDER or not ok:
            _record_failure(con, keys, now)
            _audit_auth(con, actor=username, role=None, action="auth.login.failure")
            con.commit()
            raise HTTPException(status_code=401, detail="invalid username or password")

        _clear_attempts(con, keys)
        session_id = secrets.token_urlsafe(32)
        ttl = timedelta(hours=config.session_ttl_h())
        issued_at, expires_at = dbmod.iso(now), dbmod.iso(now + ttl)
        user_agent = (request.headers.get("user-agent") or "")[:_USER_AGENT_MAX]
        con.execute(
            "INSERT INTO sessions (session_id, user_id, issued_at, expires_at, user_agent)"
            " VALUES (?, ?, ?, ?, ?)",
            (session_id, user["user_id"], issued_at, expires_at, user_agent),
        )
        con.execute(
            "UPDATE users SET last_login = ? WHERE user_id = ?", (issued_at, user["user_id"])
        )
        _audit_auth(con, actor=user["username"], role=user["role"], action="auth.login.success")
        con.commit()
    finally:
        con.close()

    request.state.role = user["role"]
    request.state.actor = user["username"]
    response.set_cookie(
        SESSION_COOKIE, session_id,
        max_age=int(ttl.total_seconds()), path="/",
        httponly=True, samesite="strict", secure=bool(config.public_host()),
    )
    return {"username": user["username"], "role": user["role"], "expires_at": expires_at}


@router.post("/logout", response_model=AuthMessageOut)
def logout(request: Request, response: Response):
    """Revoke the current session server-side and clear the cookie; audited."""
    ident = _session_identity(request)
    if ident is None:
        raise HTTPException(status_code=401, detail="no active session")
    _check_origin(request)  # a session mutation like any other
    con = dbmod.connect()
    try:
        con.execute(
            "UPDATE sessions SET revoked_at = ? WHERE session_id = ?",
            (dbmod.utcnow(), ident.session_id),
        )
        _audit_auth(con, actor=ident.username, role=ident.role, action="auth.logout")
        con.commit()
    finally:
        con.close()
    request.state.role = ident.role
    request.state.actor = ident.actor
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"detail": "signed out"}


@router.get("/me", response_model=MeOut)
def me(request: Request):
    """The signed-in username, role and session expiry (what the UI renders
    its menu from). Key-authenticated callers get their role with a null
    username and expiry."""
    ident = resolve_identity(request)
    if ident is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    request.state.role = ident.role
    request.state.actor = ident.actor
    return {"username": ident.username, "role": ident.role, "expires_at": ident.expires_at}
