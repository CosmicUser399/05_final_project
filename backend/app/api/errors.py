"""Unified API error format and exception handlers."""

from __future__ import annotations

import logging
from typing import cast

from fastapi import FastAPI
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def error_body(
    code: str,
    message: str,
    entity: str | None = None,
    entity_id: str | None = None,
) -> dict[str, dict[str, str | None]]:
    """Build ``{"error": {code, message, entity, entity_id}}``."""
    return {
        "error": {
            "code": code,
            "message": message,
            "entity": entity,
            "entity_id": entity_id,
        }
    }


async def _http_error_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    http_exc = cast(StarletteHTTPException, exc)
    return JSONResponse(
        status_code=http_exc.status_code,
        content=error_body(
            f"HTTP_{http_exc.status_code}", str(http_exc.detail)
        ),
    )


async def _validation_error_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_body("VALIDATION_ERROR", "Invalid request"),
    )


async def _unhandled_error_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.error(
        "unhandled error on %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content=error_body("INTERNAL_ERROR", "Internal server error"),
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register handlers that never leak stack traces or secrets."""
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(
        RequestValidationError, _validation_error_handler
    )
    app.add_exception_handler(Exception, _unhandled_error_handler)
