"""REST routes for equipment."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter
from fastapi import Response
from fastapi import status

from app.api.deps import EquipmentServiceDep
from app.api.v1.schemas import EquipmentCreate
from app.api.v1.schemas import EquipmentUpdate
from app.api.v1.schemas import entity_json
from app.api.v1.schemas import json_equipment_list

router = APIRouter(tags=["equipment"])


@router.get("/versions/{version_id}/equipment")
def list_version_equipment(
    version_id: UUID,
    service: EquipmentServiceDep,
) -> list[dict[str, Any]]:
    """List equipment on a version."""
    return json_equipment_list(service.list_for_version(version_id))


@router.post(
    "/versions/{version_id}/equipment",
    status_code=status.HTTP_201_CREATED,
)
def create_equipment(
    version_id: UUID,
    body: EquipmentCreate,
    service: EquipmentServiceDep,
) -> dict[str, Any]:
    """Create equipment on a DRAFT version."""
    equipment = service.create(
        version_id,
        body.to_data(),
        actor_id=body.actor_id,
        source=body.source,
        reason=body.reason,
    )
    return entity_json(equipment)


@router.get("/equipment/{equipment_id}")
def get_equipment(
    equipment_id: UUID,
    service: EquipmentServiceDep,
) -> dict[str, Any]:
    """Return one equipment item."""
    return entity_json(service.get(equipment_id))


@router.patch("/equipment/{equipment_id}")
def update_equipment(
    equipment_id: UUID,
    body: EquipmentUpdate,
    service: EquipmentServiceDep,
) -> dict[str, Any]:
    """Update equipment on a DRAFT version."""
    equipment = service.update(
        equipment_id,
        body.to_data(),
        actor_id=body.actor_id,
        source=body.source,
        reason=body.reason,
    )
    return entity_json(equipment)


@router.delete(
    "/equipment/{equipment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_equipment(
    equipment_id: UUID,
    service: EquipmentServiceDep,
) -> Response:
    """Delete equipment from a DRAFT version."""
    service.delete(equipment_id, source="api")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
