"""FastAPI application (docs/api.md §7; backend/CLAUDE.md).

Open paths: ``/``, ``/assets/*``, ``/docs``, ``/openapi.json``,
``/api/health``. Everything else under ``/api/*`` and ``/crops/*`` needs
auth (backend/app/auth.py). The audit middleware records every mutation
and every plate/sightings query.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.app import auth, schemas
from backend.app.audit import AuditMiddleware
from backend.app.routes_cameras import router as cameras_router
from backend.app.routes_meta import router as meta_router
from backend.core import config

FRONTEND_DIST = config.REPO_ROOT / "frontend" / "dist"
CROPS_DIR = config.REPO_ROOT / "data" / "crops"


def create_app() -> FastAPI:
    auth.assert_keys_configured()
    app = FastAPI(
        title="Sentinel — Integrated Video Management & Analytics Platform",
        version="2.0",
        description="Camera registry, ANPR sightings, watchlist alerts and "
        "route reconstruction over the sandbox camera grid.",
    )
    app.add_middleware(AuditMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["X-API-Key", "Content-Type", "Last-Event-ID"],
    )

    app.include_router(meta_router)
    app.include_router(cameras_router)

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
    def close_session(response: Response):
        """Clear the sentinel_key cookie."""
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
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
    else:
        @app.get("/", include_in_schema=False)
        def root():
            return {"service": "sentinel-api", "docs": "/docs", "health": "/api/health"}

    return app


app = create_app()
