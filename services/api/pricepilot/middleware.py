"""Request-scoped middleware: request id + structured logging context."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware

from pricepilot.logging import request_id_var

if TYPE_CHECKING:
    from starlette.requests import Request


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a request_id (respecting one supplied by a trusted proxy header)."""

    async def dispatch(self, request: Request, call_next):
        # Prefer the caller's X-Request-Id when a gateway injects one; else mint ours.
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.scope["request_id"] = rid
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-Id"] = rid
        return response