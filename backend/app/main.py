"""FastAPI application (docs/api.md §7, §9; backend/CLAUDE.md).

Open paths (decision F41): ``/``, ``/assets/*``, ``/api/health`` and
``/api/auth/login`` **only** — ``/docs`` and ``/openapi.json`` sit behind
the login now that the platform is published. Everything else under
``/api/*`` and ``/crops/*`` needs auth (backend/app/auth.py). The audit
middleware records every mutation and every plate/sightings query.
Hardening (docs/api.md §9): security headers on every response,
``TrustedHostMiddleware`` reads ``SENTINEL_PUBLIC_HOST``, and the CSV
import is capped at 2 MB / 5,000 rows.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.app import auth, schemas
from backend.app.audit import AuditMiddleware
from backend.app.routes_analytics import router as analytics_router
from backend.app.routes_cameras import router as cameras_router
from backend.app.routes_hls import router as hls_router
from backend.app.routes_meta import router as meta_router
from backend.app.routes_reports import router as reports_router
from backend.app.routes_users import router as users_router
from backend.core import config
from backend.services import health as health_service

FRONTEND_DIST = config.REPO_ROOT / "frontend" / "dist"
CROPS_DIR = config.REPO_ROOT / "data" / "crops"

# --- public-exposure hardening (docs/api.md §9; task S3.0) ------------------

_MAX_CSV_BYTES = 2 * 1024 * 1024
_MAX_CSV_ROWS = 5_000
# The row cap is checked on the raw multipart body; the framing adds a
# handful of lines, so allow a small slack over rows+header.
_CSV_NEWLINE_SLACK = 20

# img-src names every basemap host the frontend's TileLayers use, exactly:
# a CSP wildcard never matches the bare host, and "*.tile.openstreetmap.org"
# blocked every tile from "tile.openstreetmap.org" until 25 Sep (blank grey
# map). media-src/worker-src need blob: because hls.js attaches a
# MediaSource blob: URL to every <video> and runs its demuxer in a blob:
# worker — without them no Live Wall tile could play in a real browser.
_CSP = (
    "default-src 'self'; "
    "img-src 'self' data: blob: https://tile.openstreetmap.org "
    "https://*.basemaps.cartocdn.com https://server.arcgisonline.com; "
    "media-src 'self' blob:; "
    "worker-src 'self' blob:; "
    "style-src 'self' 'unsafe-inline'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; object-src 'none'"
)
# /docs loads Swagger UI from cdn.jsdelivr.net and boots via an inline
# script; the page is behind the login, so the relaxation is contained.
_CSP_DOCS = (
    "default-src 'self'; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "script-src 'unsafe-inline' https://cdn.jsdelivr.net; "
    "connect-src 'self'; frame-ancestors 'none'"
)


class CsvImportLimitMiddleware:
    """Cap the CSV import at 2 MB / 5,000 rows with a reason, not a stack
    trace (docs/api.md §9).

    Pure ASGI, because FastAPI parses a multipart body *before* solving
    route dependencies — a dependency reading ``request.body()`` there
    finds the stream already consumed. This buffers the body, enforces the
    caps, then replays it for the form parser. Innermost middleware, so
    the audit middleware still records the 413.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or scope.get("path") != "/api/cameras/import"
        ):
            await self.app(scope, receive, send)
            return
        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }
        declared = headers.get("content-length", "")
        if declared.isdigit() and int(declared) > _MAX_CSV_BYTES:
            await self._reject(scope, receive, send, "CSV import is limited to 2 MB")
            return
        chunks: list[bytes] = []
        total = newlines = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                return  # client disconnected mid-upload
            chunk = message.get("body", b"")
            total += len(chunk)
            newlines += chunk.count(b"\n")
            if total > _MAX_CSV_BYTES:
                await self._reject(scope, receive, send, "CSV import is limited to 2 MB")
                return
            if newlines > _MAX_CSV_ROWS + _CSV_NEWLINE_SLACK:
                await self._reject(scope, receive, send, "CSV import is limited to 5,000 rows")
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    @staticmethod
    async def _reject(scope, receive, send, reason: str) -> None:
        await JSONResponse({"detail": reason}, status_code=413)(scope, receive, send)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Run the camera health checker while the API is up (S3.1b, F31):
    a daemon thread on SENTINEL_HEALTH_INTERVAL_S (0 = off), stopped on
    shutdown. It waits one interval before its first pass, so short-lived
    test apps never fire one."""
    stop = health_service.start_background()
    try:
        yield
    finally:
        if stop is not None:
            stop.set()


def create_app() -> FastAPI:
    auth.assert_keys_configured()
    app = FastAPI(
        lifespan=_lifespan,
        title="Sentinel — Integrated Video Management & Analytics Platform",
        version="2.0",
        description="Camera registry, ANPR sightings, watchlist alerts and "
        "route reconstruction over the sandbox camera grid.",
        # F41: /docs and /openapi.json sit behind the login (added below).
        docs_url=None, redoc_url=None, openapi_url=None,
    )
    # Added first, so it sits innermost and the audit middleware still
    # records a capped import's 413.
    app.add_middleware(CsvImportLimitMiddleware)
    app.add_middleware(AuditMiddleware)
    allowed_hosts = ["localhost", "127.0.0.1"]
    if config.public_host():
        allowed_hosts.append(config.public_host())
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["X-API-Key", "Content-Type", "Last-Event-ID"],
    )

    # Security headers on every response (docs/api.md §9). Registered last,
    # so it is the outermost middleware and even TrustedHost rejections and
    # 401s carry the headers.
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        csp = _CSP_DOCS if request.url.path == "/docs" else _CSP
        response.headers.setdefault("Content-Security-Policy", csp)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if config.public_host():
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response

    app.include_router(meta_router)
    app.include_router(cameras_router)
    app.include_router(analytics_router)
    app.include_router(reports_router)
    app.include_router(hls_router)
    app.include_router(auth.router)
    app.include_router(users_router)

    @app.get("/openapi.json", include_in_schema=False)
    def openapi_spec(_: str = Depends(auth.require_auth)) -> JSONResponse:
        """The OpenAPI document — behind the login (F41); the committed
        deliverables/registry-api.json remains the public deliverable."""
        return JSONResponse(app.openapi())

    @app.get("/docs", include_in_schema=False)
    def swagger_docs(_: str = Depends(auth.require_auth)):
        """Interactive API docs — behind the login (F41)."""
        return get_swagger_ui_html(openapi_url="/openapi.json", title=f"{app.title} — docs")

    @app.post("/api/session", response_model=schemas.SessionOut, tags=["auth"])
    def open_session(body: schemas.SessionIn, response: Response):
        """Validate an API key and set the sentinel_key cookie (GET-only transport for crops, HLS and the alert stream)."""
        role = auth.role_for_key(body.api_key)
        if role is None:
            raise HTTPException(status_code=401, detail="invalid API key")
        response.set_cookie(
            auth.COOKIE_NAME, body.api_key,
            httponly=True, samesite="strict", path="/",
        )
        return {"role": role}

    @app.delete("/api/session", response_model=schemas.MessageOut, tags=["auth"])
    def close_session(response: Response, _: str = Depends(auth.require_auth)):
        """Clear the sentinel_key cookie (authenticated — F41 leaves only /,
        /assets/*, /api/health and /api/auth/login open)."""
        response.delete_cookie(auth.COOKIE_NAME, path="/")
        return {"detail": "session cleared"}

    @app.get(
        "/crops/{crop_path:path}",
        tags=["crops"],
        responses={200: {"description": "The crop image", "content": {"image/jpeg": {"schema": {"type": "string", "format": "binary"}}}}},
    )
    def crop(crop_path: str, _: str = Depends(auth.require_auth)):
        """Serve a plate/vehicle crop (auth: header, or the session cookie on GET)."""
        # camera_id-derived names only; refuse traversal outside the folder.
        target = (CROPS_DIR / crop_path).resolve()
        if not str(target).startswith(str(CROPS_DIR.resolve())):
            raise HTTPException(status_code=404, detail="not found")
        if not target.is_file():
            raise HTTPException(status_code=404, detail="crop not found")
        return FileResponse(target)

    if FRONTEND_DIST.is_dir():  # pragma: no cover — dist is not built in tests
        # Serve the built SPA (task S3.2): /assets/* as static files, and
        # index.html for every non-API path so client-side routes like
        # /map deep-link straight into the app. Open by design — F41's
        # open paths are exactly `/`, `/assets/*` (+ /api/health and
        # /api/auth/login); the app itself renders nothing without a
        # session. API routes are registered before this catch-all, so
        # they always win; unknown /api/ or /crops/ paths stay JSON 404s.
        app.mount(
            "/assets",
            StaticFiles(directory=FRONTEND_DIST / "assets"),
            name="frontend-assets",
        )

        @app.get("/{spa_path:path}", include_in_schema=False)
        def spa(spa_path: str):
            if spa_path.split("/", 1)[0] in ("api", "crops"):
                raise HTTPException(status_code=404, detail="not found")
            if spa_path:
                target = (FRONTEND_DIST / spa_path).resolve()
                if str(target).startswith(str(FRONTEND_DIST.resolve())) and target.is_file():
                    return FileResponse(target)
            return FileResponse(FRONTEND_DIST / "index.html")
    else:
        @app.get("/", include_in_schema=False)
        def root():
            return {"service": "sentinel-api", "docs": "/docs", "health": "/api/health"}

    return app


app = create_app()
