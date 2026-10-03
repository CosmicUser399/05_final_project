"""REST routes for systems."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from fastapi import Response
from fastapi import status

from app.api.deps import SystemServiceDep
from app.api.deps import VersionServiceDep
from app.api.v1.schemas import SystemCreate
from app.api.v1.schemas import SystemResponse
from app.api.v1.schemas import SystemUpdate
from app.api.v1.schemas import VersionCreate
from app.api.v1.schemas import VersionResponse

router = APIRouter(prefix="/systems", tags=["systems"])


@router.get("")
def list_systems(service: SystemServiceDep) -> list[SystemResponse]:
    """Return all systems."""
    return [SystemResponse.from_domain(s) for s in service.list()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_system(
    body: SystemCreate,
    service: SystemServiceDep,
) -> SystemResponse:
    """Create a system with an initial DRAFT version."""
    system = service.create(
        body.name,
        description=body.description,
        created_by=body.created_by,
    )
    return SystemResponse.from_domain(system)


@router.get("/{system_id}")
def get_system(
    system_id: UUID,
    service: SystemServiceDep,
) -> SystemResponse:
    """Return one system by id."""
    return SystemResponse.from_domain(service.get(system_id))


@router.patch("/{system_id}")
def update_system(
    system_id: UUID,
    body: SystemUpdate,
    service: SystemServiceDep,
) -> SystemResponse:
    """Update system metadata."""
    system = service.update(
        system_id,
        name=body.name,
        description=body.description,
    )
    return SystemResponse.from_domain(system)


@router.delete("/{system_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_system(system_id: UUID, service: SystemServiceDep) -> Response:
    """Delete a system."""
    service.delete(system_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{system_id}/versions")
def list_system_versions(
    system_id: UUID,
    service: VersionServiceDep,
) -> list[VersionResponse]:
    """List versions belonging to a system."""
    versions = service.list_for_system(system_id)
    return [VersionResponse.from_domain(v) for v in versions]


@router.post("/{system_id}/versions", status_code=status.HTTP_201_CREATED)
def create_system_version(
    system_id: UUID,
    body: VersionCreate,
    service: VersionServiceDep,
) -> VersionResponse:
    """Create an empty DRAFT or clone an existing version."""
    version = service.create(
        system_id,
        clone_from=body.clone_from,
        comment=body.comment,
        created_by=body.created_by,
    )
    return VersionResponse.from_domain(version)
