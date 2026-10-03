"""REST routes for system versions."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from fastapi import status

from app.api.deps import VersionServiceDep
from app.api.v1.schemas import VersionModelResponse
from app.api.v1.schemas import VersionResponse
from app.api.v1.schemas import VersionTransition

router = APIRouter(prefix="/versions", tags=["versions"])


@router.get("/{version_id}")
def get_version(
    version_id: UUID,
    service: VersionServiceDep,
) -> VersionResponse:
    """Return version metadata."""
    return VersionResponse.from_domain(service.get(version_id))


@router.post("/{version_id}/clone", status_code=status.HTTP_201_CREATED)
def clone_version_route(
    version_id: UUID,
    service: VersionServiceDep,
) -> VersionResponse:
    """Clone a version into a new DRAFT."""
    version = service.clone(version_id)
    return VersionResponse.from_domain(version)


@router.post("/{version_id}/transition")
def transition_version(
    version_id: UUID,
    body: VersionTransition,
    service: VersionServiceDep,
) -> VersionResponse:
    """Change version lifecycle status."""
    version = service.transition(version_id, body.status)
    return VersionResponse.from_domain(version)


@router.get("/{version_id}/model")
def get_version_model(
    version_id: UUID,
    service: VersionServiceDep,
) -> VersionModelResponse:
    """Return full version content."""
    version, content = service.get_model(version_id)
    return VersionModelResponse.from_domain(version, content)
