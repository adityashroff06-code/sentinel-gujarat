"""Append-only audit trail (docs/api.md §7; decision F23).

Middleware writes an ``audit`` row for every non-GET request and for every
``GET /api/plates/*`` and ``GET /api/sightings*`` — operator-misuse lookups
are the documented ANPR scandal pattern. Handlers supply ``before``/
``after`` (and entity naming) through ``request.state.audit``.
"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.core import db as dbmod


def _should_audit(request: Request) -> bool:
    if request.method != "GET":
        return True
    path = request.url.path
    # /api/reports/route/ is a plate lookup too (B12) — same scandal pattern.
    return (path.startswith("/api/plates/") or path.startswith("/api/sightings")
            or path.startswith("/api/reports/route/"))


def set_audit(
    request: Request,
    *,
    entity: str | None = None,
    entity_id: str | None = None,
    before: Any = None,
    after: Any = None,
) -> None:
    """Called by handlers to enrich the audit row for this request."""
    request.state.audit = {
        "entity": entity,
        "entity_id": entity_id,
        "before_json": json.dumps(before, default=str) if before is not None else None,
        "after_json": json.dumps(after, default=str) if after is not None else None,
    }


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        if _should_audit(request):
            extra = getattr(request.state, "audit", {}) or {}
            row = (
                dbmod.utcnow(),
                # Username (or "key:<role>") when the auth dependency resolved
                # one; the bare role only for paths that never authenticated.
                getattr(request.state, "actor", None)
                or getattr(request.state, "role", None),
                getattr(request.state, "role", None),
                f"{request.method} {request.url.path} -> {response.status_code}",
                extra.get("entity"),
                extra.get("entity_id"),
                extra.get("before_json"),
                extra.get("after_json"),
            )
            con = dbmod.connect()
            try:
                con.execute(
                    "INSERT INTO audit (at, actor, role, action, entity, entity_id,"
                    " before_json, after_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    row,
                )
                con.commit()
            finally:
                con.close()
        return response
