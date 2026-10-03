"""REST routes for resources and spare parts."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter
from fastapi import Response
from fastapi import status

from app.api.deps import ResourcesServiceDep
from app.api.v1.schemas import ResourceCreate
from app.api.v1.schemas import ResourceUpdate
from app.api.v1.schemas import SparePartCreate
from app.api.v1.schemas import SparePartUpdate
from app.api.v1.schemas import entity_json

router = APIRouter(tags=["resources"])


@router.get("/versions/{version_id}/resources")
def list_resources(
    version_id: UUID,
    service: ResourcesServiceDep,
) -> list[dict[str, Any]]:
    """List maintenance resources on a version."""
    return [entity_json(r) for r in service.list_resources(version_id)]


@router.post(
    "/versions/{version_id}/resources",
    status_code=status.HTTP_201_CREATED,
)
def create_resource(
    version_id: UUID,
    body: ResourceCreate,
    service: ResourcesServiceDep,
) -> dict[str, Any]:
    """Create a maintenance resource."""
    resource = service.create_resource(
        version_id,
        body.to_data(),
        actor_id=body.actor_id,
        source=body.source,
        reason=body.reason,
    )
    return entity_json(resource)


@router.get("/resources/{resource_id}")
def get_resource(
    resource_id: UUID,
    service: ResourcesServiceDep,
) -> dict[str, Any]:
    """Return one resource."""
    return entity_json(service.get_resource(resource_id))


@router.patch("/resources/{resource_id}")
def update_resource(
    resource_id: UUID,
    body: ResourceUpdate,
    service: ResourcesServiceDep,
) -> dict[str, Any]:
    """Update a maintenance resource."""
    resource = service.update_resource(
        resource_id,
        body.to_data(),
        actor_id=body.actor_id,
        source=body.source,
        reason=body.reason,
    )
    return entity_json(resource)


@router.delete(
    "/resources/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_resource(
    resource_id: UUID,
    service: ResourcesServiceDep,
) -> Response:
    """Delete a maintenance resource."""
    service.delete_resource(resource_id, source="api")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/versions/{version_id}/spares")
def list_spare_parts(
    version_id: UUID,
    service: ResourcesServiceDep,
) -> list[dict[str, Any]]:
    """List spare parts on a version."""
    return [entity_json(p) for p in service.list_spare_parts(version_id)]


@router.post(
    "/versions/{version_id}/spares",
    status_code=status.HTTP_201_CREATED,
)
def create_spare_part(
    version_id: UUID,
    body: SparePartCreate,
    service: ResourcesServiceDep,
) -> dict[str, Any]:
    """Create a spare part."""
    part = service.create_spare_part(
        version_id,
        body.to_data(),
        actor_id=body.actor_id,
        source=body.source,
        reason=body.reason,
    )
    return entity_json(part)


@router.get("/spares/{spare_part_id}")
def get_spare_part(
    spare_part_id: UUID,
    service: ResourcesServiceDep,
) -> dict[str, Any]:
    """Return one spare part."""
    return entity_json(service.get_spare_part(spare_part_id))


@router.patch("/spares/{spare_part_id}")
def update_spare_part(
    spare_part_id: UUID,
    body: SparePartUpdate,
    service: ResourcesServiceDep,
) -> dict[str, Any]:
    """Update a spare part."""
    part = service.update_spare_part(
        spare_part_id,
        body.to_data(),
        actor_id=body.actor_id,
        source=body.source,
        reason=body.reason,
    )
    return entity_json(part)


@router.delete(
    "/spares/{spare_part_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_spare_part(
    spare_part_id: UUID,
    service: ResourcesServiceDep,
) -> Response:
    """Delete a spare part."""
    service.delete_spare_part(spare_part_id, source="api")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
