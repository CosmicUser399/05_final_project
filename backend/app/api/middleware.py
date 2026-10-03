"""HTTP middleware: request id propagation."""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable
from collections.abc import Callable

import structlog
from fastapi import FastAPI
from fastapi import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _resolve_request_id(request: Request) -> str:
    incoming = request.headers.get(REQUEST_ID_HEADER, "")
    if _VALID_REQUEST_ID.match(incoming):
        return incoming
    return uuid.uuid4().hex


def register_middleware(app: FastAPI) -> None:
    """Attach the request-id middleware to the application."""

    @app.middleware("http")
    async def request_id_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = _resolve_request_id(request)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
