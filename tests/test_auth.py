"""S3.0 acceptance: login, roles, sessions and public-exposure hardening
(docs/api.md §7 "Auth transport", §9; decisions F41, F42, F23).

Covers: login sets the cookie and /api/auth/me answers; wrong password →
401 with an audit row carrying no password; 5 failures lock and the lock
survives a restart; the role ladder (evaluator may ack and edit the
watchlist, not users or camera tiers; viewer mutates nothing); the Origin
check on session mutations (X-API-Key exempt); crops via the session
cookie; /docs and /openapi.json behind the login; the five security
headers; the unchanged S1.3a key path; and the route walk — every route
except /, /assets/*, /api/health and /api/auth/login rejects an
unauthenticated request.
"""

from __future__ import annotations

import io
import json
import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends, Request
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import backend.app.main as main_mod
from backend.app import auth
from backend.core import db as dbmod
from backend.core import passwords

ADMIN = {"X-API-Key": "test-admin-key-not-a-secret"}
VIEWER = {"X-API-Key": "test-viewer-key-not-a-secret"}
ORIGIN = {"Origin": "http://localhost"}

PW = "s3ntinel-Passw0rd!"
WRONG = "not-the-Passw0rd"
# One scrypt hash, computed once (the users share a test password).
PW_HASH = passwords.hash_password(PW)

USERS = (("ada", "admin"), ("eva", "evaluator"), ("vic", "viewer"))


def _seed_users(con) -> None:
    now = dbmod.utcnow()
    for username, role in USERS:
        con.execute(
            "INSERT INTO users (username, password_hash, role, active, created_at)"
            " VALUES (?, ?, ?, 1, ?)",
            (username, PW_HASH, role, now),
        )
    con.commit()


def _seed_alert(con) -> None:
    now = dbmod.utcnow()
    con.execute(
        "INSERT INTO cameras (camera_id, created_at, updated_at) VALUES ('cam01', ?, ?)",
        (now, now),
    )
    con.execute(
        "INSERT INTO alerts (alert_id, kind, camera_id, severity, clock_source, fired_at)"
        " VALUES ('ALERT-20260924-0001', 'watchlist', 'cam01', 'high', 'demo', ?)",
        (now,),
    )
    con.commit()


@pytest.fixture()
def app(tmp_path, monkeypatch):
    """A migrated per-test database with three seeded users, and a fresh app."""
    monkeypatch.setenv("SENTINEL_DB", str(tmp_path / "auth.db"))
    monkeypatch.delenv("SENTINEL_PUBLIC_HOST", raising=False)
    con = dbmod.connect()
    dbmod.migrate(con)
    _seed_users(con)
    con.close()
    return main_mod.create_app()


def _client(app) -> TestClient:
    # TrustedHostMiddleware rejects the default "testserver" Host.
    return TestClient(app, base_url="http://localhost")


def _login_as(app, username: str, password: str = PW) -> TestClient:
    c = _client(app)
    r = c.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return c


def _audit_rows() -> list[dict]:
    con = dbmod.connect()
    try:
        return [dict(r) for r in con.execute("SELECT * FROM audit")]
    finally:
        con.close()


# --------------------------------------------------------------- passwords.py

def test_password_hash_format_and_verify():
    stored = passwords.hash_password(PW)
    scheme, n, r, p, salt, digest = stored.split("$")
    assert scheme == "scrypt" and (n, r, p) == ("16384", "8", "1")
    assert salt and digest
    assert passwords.verify_password(PW, stored)
    assert not passwords.verify_password(WRONG, stored)
    # per-user salt: the same password never hashes to the same string
    assert passwords.hash_password(PW) != stored
    # malformed stored values are a mismatch, never a crash
    assert not passwords.verify_password(PW, "scrypt$garbage")
    assert not passwords.verify_password(PW, "md5$1$1$1$aa$bb")
    assert not passwords.verify_password(PW, "")
    with pytest.raises(ValueError):
        passwords.hash_password("")


# --------------------------------------------------------------------- login

def test_login_sets_cookie_and_me_answers(app):
    c = _client(app)
    before = datetime.now(timezone.utc)
    r = c.post("/api/auth/login", json={"username": "eva", "password": PW})
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "eva" and body["role"] == "evaluator"

    set_cookie = r.headers["set-cookie"]
    attrs = [p.strip().lower() for p in set_cookie.split(";")]
    assert set_cookie.startswith("sentinel_session=")
    assert "httponly" in attrs and "samesite=strict" in attrs
    assert "secure" not in attrs  # SENTINEL_PUBLIC_HOST unset in this test

    me = c.get("/api/auth/me")
    assert me.status_code == 200
    payload = me.json()
    assert set(payload) == {"username", "role", "expires_at"}
    assert payload["username"] == "eva" and payload["role"] == "evaluator"
    # 8-hour expiry (SENTINEL_SESSION_TTL_H default)
    expires = datetime.fromisoformat(payload["expires_at"])
    assert timedelta(hours=7, minutes=55) < (expires - before) < timedelta(hours=8, minutes=5)


def test_wrong_password_401_and_audit_row_has_no_password(app):
    c = _client(app)
    r = c.post("/api/auth/login", json={"username": "eva", "password": WRONG})
    assert r.status_code == 401
    rows = _audit_rows()
    failures = [row for row in rows if row["action"] == "auth.login.failure"]
    assert failures and failures[-1]["actor"] == "eva"
    dumped = json.dumps(rows)
    assert WRONG not in dumped and PW not in dumped and "password" not in dumped.lower()


def test_5_failures_lock_and_the_lock_survives_restart(app):
    c = _client(app)
    for _ in range(5):
        assert c.post(
            "/api/auth/login", json={"username": "eva", "password": WRONG}
        ).status_code == 401
    locked = c.post("/api/auth/login", json={"username": "eva", "password": WRONG})
    assert locked.status_code == 429
    # even the correct password is refused while locked
    assert c.post(
        "/api/auth/login", json={"username": "eva", "password": PW}
    ).status_code == 429
    # "restart": a brand-new app over the same database keeps the lock
    c2 = _client(main_mod.create_app())
    assert c2.post(
        "/api/auth/login", json={"username": "eva", "password": PW}
    ).status_code == 429


def test_logout_revokes_the_session_server_side(app):
    c = _login_as(app, "eva")
    assert c.get("/api/auth/me").status_code == 200
    assert c.post("/api/auth/logout", headers=ORIGIN).status_code == 200
    assert c.get("/api/auth/me").status_code == 401
    con = dbmod.connect()
    try:
        row = con.execute("SELECT revoked_at FROM sessions").fetchone()
    finally:
        con.close()
    assert row["revoked_at"] is not None
    actions = [r["action"] for r in _audit_rows()]
    assert "auth.login.success" in actions and "auth.logout" in actions


def test_expired_session_is_rejected(app):
    c = _login_as(app, "eva")
    con = dbmod.connect()
    try:
        con.execute("UPDATE sessions SET expires_at = '2020-01-01T00:00:00+00:00'")
        con.commit()
    finally:
        con.close()
    assert c.get("/api/auth/me").status_code == 401


# ---------------------------------------------------------------- role ladder

def test_evaluator_may_ack_and_watchlist_but_not_users_or_tier(app):
    con = dbmod.connect()
    _seed_alert(con)
    con.close()
    c = _login_as(app, "eva")

    ack = c.post("/api/alerts/1/ack", headers=ORIGIN)
    assert ack.status_code == 200
    con = dbmod.connect()
    try:
        by = con.execute("SELECT acknowledged_by FROM alerts").fetchone()["acknowledged_by"]
    finally:
        con.close()
    assert by == "eva"  # audit actor is the username, not the role

    wl = c.post(
        "/api/watchlist",
        json={"plate": "GJ01AB1234", "category": "stolen_vehicle", "severity": "high"},
        headers=ORIGIN,
    )
    assert wl.status_code == 201

    assert c.post(
        "/api/users",
        json={"username": "newbie", "password": "some-Passw0rd", "role": "viewer"},
        headers=ORIGIN,
    ).status_code == 403
    assert c.patch(
        "/api/cameras/cam01", json={"fps_tier": "active"}, headers=ORIGIN
    ).status_code == 403


def test_viewer_gets_403_on_every_mutation(app):
    c = _login_as(app, "vic")
    mutations = [
        ("POST", "/api/cameras", {"json": {"camera_id": "cam90"}}),
        ("PATCH", "/api/cameras/cam90", {"json": {"fps_tier": "active"}}),
        ("POST", "/api/cameras/import",
         {"files": {"file": ("x.csv", io.BytesIO(b"camera_id\ncam91\n"), "text/csv")}}),
        ("POST", "/api/watchlist",
         {"json": {"plate": "GJ01AB1234", "category": "stolen_vehicle", "severity": "high"}}),
        ("DELETE", "/api/watchlist/1", {}),
        ("POST", "/api/alerts/1/ack", {}),
        ("POST", "/api/users",
         {"json": {"username": "newbie", "password": "some-Passw0rd", "role": "viewer"}}),
        ("PATCH", "/api/users/1", {"json": {"role": "admin"}}),
        ("DELETE", "/api/users/1", {}),
    ]
    for method, path, kwargs in mutations:
        r = c.request(method, path, headers=ORIGIN, **kwargs)
        assert r.status_code == 403, f"{method} {path} -> {r.status_code}"


def test_session_mutation_requires_matching_origin(app):
    c = _login_as(app, "ada")
    body = {"camera_id": "cam90", "department": "Police"}
    # no Origin header → refused
    assert c.post("/api/cameras", json=body).status_code == 403
    # foreign Origin → refused
    assert c.post(
        "/api/cameras", json=body, headers={"Origin": "https://evil.example"}
    ).status_code == 403
    # matching Origin → allowed
    assert c.post("/api/cameras", json=body, headers=ORIGIN).status_code == 201


def test_api_key_path_unchanged_for_scripts(app):
    """The S1.3a key transport, byte for byte: header everywhere, no Origin
    needed, sentinel_key cookie on GET media paths only (F23)."""
    c = _client(app)
    # admin key mutates WITHOUT an Origin header (CSRF exemption for keys)
    r = c.post("/api/cameras", json={"camera_id": "cam95"}, headers=ADMIN)
    assert r.status_code == 201
    assert c.get("/api/cameras", headers=VIEWER).status_code == 200
    # sentinel_key cookie transport (POST /api/session) still works
    assert c.post("/api/session", json={"api_key": VIEWER["X-API-Key"]}).status_code == 200
    assert "sentinel_key" in c.cookies
    assert c.get("/crops/x.jpg").status_code == 404      # cookie ok on GET media
    assert c.get("/api/cameras").status_code == 401       # not on plain API GETs
    assert c.post("/api/session", json={"api_key": "wrong"}).status_code == 401


# ------------------------------------------------------- crops via the session

def test_crops_with_session_cookie_404_without_credential_401(app):
    c = _client(app)
    assert c.get("/crops/x.jpg").status_code == 401       # no credential at all
    c2 = _login_as(app, "vic")
    assert c2.get("/crops/x.jpg").status_code == 404      # authorised; file absent


# ----------------------------------------------------------- exposure hardening

def test_docs_and_openapi_behind_the_login(app):
    c = _client(app)
    assert c.get("/docs").status_code == 401
    assert c.get("/openapi.json").status_code == 401
    c2 = _login_as(app, "vic")
    spec = c2.get("/openapi.json")
    assert spec.status_code == 200 and "paths" in spec.json()
    docs = c2.get("/docs")
    assert docs.status_code == 200 and "text/html" in docs.headers["content-type"]


def test_security_headers_on_every_response(app):
    c = _client(app)
    for r in (c.get("/api/health"), c.get("/api/cameras")):  # a 200 and a 401
        assert "default-src 'self'" in r.headers["Content-Security-Policy"]
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert r.headers["X-Frame-Options"] == "DENY"
        assert r.headers["Referrer-Policy"] == "no-referrer"
        assert "Strict-Transport-Security" not in r.headers  # no public host here


def test_public_host_enables_hsts_and_secure_cookie(tmp_path, monkeypatch):
    monkeypatch.setenv("SENTINEL_DB", str(tmp_path / "public.db"))
    monkeypatch.setenv("SENTINEL_PUBLIC_HOST", "sentinel-demo.tail1234.ts.net")
    con = dbmod.connect()
    dbmod.migrate(con)
    _seed_users(con)
    con.close()
    c = TestClient(main_mod.create_app(), base_url="https://localhost")
    r = c.post("/api/auth/login", json={"username": "eva", "password": PW})
    assert r.status_code == 200
    attrs = [p.strip().lower() for p in r.headers["set-cookie"].split(";")]
    assert "secure" in attrs  # the session cookie goes Secure (F42)
    assert r.headers["Strict-Transport-Security"].startswith("max-age=")
    # the fifth header joins the other four on the same response
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]


def test_csv_import_capped_2mb_and_5000_rows(app):
    c = _client(app)
    big = b"x" * (main_mod._MAX_CSV_BYTES + 1024)
    r = c.post(
        "/api/cameras/import",
        files={"file": ("big.csv", io.BytesIO(big), "text/csv")},
        headers=ADMIN,
    )
    assert r.status_code == 413 and "2 MB" in r.json()["detail"]

    rows = b"camera_id,department\n" + b"".join(
        b"imp%d,Police\n" % i for i in range(5_100)
    )
    r = c.post(
        "/api/cameras/import",
        files={"file": ("rows.csv", io.BytesIO(rows), "text/csv")},
        headers=ADMIN,
    )
    assert r.status_code == 413 and "5,000 rows" in r.json()["detail"]


def test_rate_limit_dependency_returns_429(app):
    """The reusable dependency (wired onto route/reports/HLS in S3.1a/b)."""
    limiter = auth.RateLimiter("test-op", limit=3, window_s=60)

    @app.get("/api/_test/limited", include_in_schema=False)
    def limited(
        request: Request,
        _: str = Depends(auth.require_auth),
        __: None = Depends(limiter),
    ):
        return {"detail": "ok"}

    c = _client(app)
    for _ in range(3):
        assert c.get("/api/_test/limited", headers=VIEWER).status_code == 200
    over = c.get("/api/_test/limited", headers=VIEWER)
    assert over.status_code == 429 and over.headers["Retry-After"] == "60"


# ------------------------------------------------------------------ users CRUD

def test_users_crud_admin_only_and_no_password_ever_returned(app):
    c = _login_as(app, "ada")
    r = c.post(
        "/api/users",
        json={"username": "newbie", "password": "brand-new-Pw1", "role": "viewer"},
        headers=ORIGIN,
    )
    assert r.status_code == 201
    assert set(r.json()) == {"user_id", "username", "role", "active", "created_at", "last_login"}
    # duplicate username → 409
    assert c.post(
        "/api/users",
        json={"username": "newbie", "password": "brand-new-Pw1", "role": "viewer"},
        headers=ORIGIN,
    ).status_code == 409

    listing = c.get("/api/users")
    assert listing.status_code == 200
    assert "newbie" in {u["username"] for u in listing.json()}
    assert "scrypt$" not in listing.text and "password" not in listing.text.lower()

    # the created account can sign in
    _login_as(app, "newbie", "brand-new-Pw1")

    uid = r.json()["user_id"]
    # disabling revokes and blocks login
    assert c.patch(f"/api/users/{uid}", json={"active": False}, headers=ORIGIN).status_code == 200
    bad = _client(app).post(
        "/api/auth/login", json={"username": "newbie", "password": "brand-new-Pw1"}
    )
    assert bad.status_code == 401
    # delete removes the account
    assert c.request("DELETE", f"/api/users/{uid}", headers=ORIGIN).status_code == 200
    assert "newbie" not in {u["username"] for u in c.get("/api/users").json()}
    # no audit row ever carries password material
    assert "scrypt$" not in json.dumps(_audit_rows())


def test_users_cli_add_passwd_disable_list(app, monkeypatch, capsys):
    import backend.tools.users as users_cli

    answers = iter(["cli-Passw0rd", "cli-Passw0rd"])
    monkeypatch.setattr(users_cli.getpass, "getpass", lambda prompt="": next(answers))
    assert users_cli.main(["add", "cliuser", "--role", "evaluator"]) == 0
    assert "scrypt$" not in capsys.readouterr().out

    c = _login_as(app, "cliuser", "cli-Passw0rd")

    answers = iter(["cli-NewPassw0rd", "cli-NewPassw0rd"])
    monkeypatch.setattr(users_cli.getpass, "getpass", lambda prompt="": next(answers))
    assert users_cli.main(["passwd", "cliuser"]) == 0
    assert c.get("/api/auth/me").status_code == 401  # open session revoked
    c = _login_as(app, "cliuser", "cli-NewPassw0rd")

    assert users_cli.main(["list"]) == 0
    out = capsys.readouterr().out
    assert "cliuser" in out and "evaluator" in out and "scrypt$" not in out

    assert users_cli.main(["disable", "cliuser"]) == 0
    assert c.get("/api/auth/me").status_code == 401
    r = _client(app).post(
        "/api/auth/login", json={"username": "cliuser", "password": "cli-NewPassw0rd"}
    )
    assert r.status_code == 401


# ------------------------------------------------------------------ route walk

OPEN_PATHS = {"/", "/api/health", "/api/auth/login"}


def _api_routes(app) -> list[APIRoute]:
    """Flatten app.routes: FastAPI 0.141 keeps included routers wrapped in
    _IncludedRouter objects whose original_router holds the APIRoutes
    (already carrying their prefix)."""
    out: list[APIRoute] = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            out.append(route)
        else:
            orig = getattr(route, "original_router", None)
            if orig is not None:
                out.extend(r for r in orig.routes if isinstance(r, APIRoute))
    return out


def test_route_walk_everything_else_rejects_unauthenticated(app):
    """docs/api.md §7: open paths are /, /assets/*, /api/health and
    /api/auth/login ONLY. Every other route answers 401 without a credential."""
    c = _client(app)
    walked: list[tuple[str, str]] = []
    for route in _api_routes(app):
        if route.path in OPEN_PATHS or route.path.startswith("/assets"):
            continue
        concrete = re.sub(r"\{[^}]+\}", "1", route.path)
        for method in sorted(set(route.methods) - {"HEAD", "OPTIONS"}):
            if route.path == "/api/session" and method == "POST":
                # its body IS the credential; an invalid one must be rejected
                r = c.post(concrete, json={"api_key": "wrong-key"})
            else:
                r = c.request(method, concrete)
            assert r.status_code == 401, f"{method} {route.path} -> {r.status_code}"
            walked.append((method, route.path))
    assert len(walked) >= 15, walked


def test_session_mutation_audit_actor_is_the_username_not_the_role(app):
    """Regression (wave-1 follow-up): AuditMiddleware wrote actor=role for
    ordinary session mutations; it must be the username the auth dependency
    resolved (request.state.actor)."""
    c = _login_as(app, "eva")
    r = c.post(
        "/api/watchlist",
        json={"plate": "GJ18ZZ0001", "category": "stolen_vehicle",
              "severity": "high", "reason": "audit actor regression"},
        headers=ORIGIN,
    )
    assert r.status_code in (200, 201), r.text
    row = [x for x in _audit_rows() if x["action"].startswith("POST /api/watchlist")][-1]
    assert row["actor"] == "eva" and row["role"] == "evaluator"


def test_evaluator_may_use_the_onboarding_form_viewer_may_not(app):
    """§7 roles: the onboarding form (POST /api/cameras) is an evaluator
    action; PATCH stays admin (asserted in the role-matrix test above)."""
    body = {"camera_id": "onb01", "department": "Police",
            "location_name": "Onboarding regression", "lat": 23.0, "lon": 72.0}
    ok = _login_as(app, "eva").post("/api/cameras", json=body, headers=ORIGIN)
    assert ok.status_code == 201, ok.text
    denied = _login_as(app, "vic").post(
        "/api/cameras", json={**body, "camera_id": "onb02"}, headers=ORIGIN)
    assert denied.status_code == 403


def test_route_report_lookup_writes_an_audit_row(app):
    """Regression (wave-2 follow-up): GET /api/reports/route/{plate} is a
    plate lookup (B12) and must be audited like /api/plates/*."""
    c = _login_as(app, "eva")
    c.get("/api/reports/route/GJ01AB1234?format=csv")
    actions = [r["action"] for r in _audit_rows()]
    assert any(a.startswith("GET /api/reports/route/GJ01AB1234") for a in actions), actions
