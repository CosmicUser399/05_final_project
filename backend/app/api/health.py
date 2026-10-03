"""Health and readiness endpoints (thin: DTO -> use case -> response)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.application.health import DatabaseProbe
from app.application.health import get_health
from app.application.health import get_readiness
from app.config import Settings
from app.config import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Liveness response."""

    status: str
    version: str


class ReadyResponse(BaseModel):
    """Readiness response."""

    status: str
    checks: dict[str, bool]


def get_database_probe(request: Request) -> DatabaseProbe:
    """Return the probe stored on the application state."""
    probe: DatabaseProbe = request.app.state.database_probe
    return probe


@router.get("/health", response_model=HealthResponse)
def health(
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    """Report that the process is alive."""
    result = get_health(settings.software_version)
    return HealthResponse(status=result.status, version=result.version)


@router.get("/ready", response_model=ReadyResponse)
def ready(
    probe: Annotated[DatabaseProbe, Depends(get_database_probe)],
) -> JSONResponse:
    """Report whether required dependencies are available."""
    result = get_readiness(probe)
    body = ReadyResponse(
        status="ready" if result.ready else "not_ready",
        checks=result.checks,
    )
    return JSONResponse(
        status_code=200 if result.ready else 503,
        content=body.model_dump(),
    )
