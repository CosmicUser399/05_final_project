"""REST routes for maintenance tasks."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter
from fastapi import Response
from fastapi import status

from app.api.deps import MaintenanceServiceDep
from app.api.v1.schemas import MaintenanceTaskCreate
from app.api.v1.schemas import MaintenanceTaskUpdate
from app.api.v1.schemas import entity_json

router = APIRouter(tags=["maintenance"])


@router.get("/equipment/{equipment_id}/maintenance")
def list_maintenance_tasks(
    equipment_id: UUID,
    service: MaintenanceServiceDep,
) -> list[dict[str, Any]]:
    """List maintenance tasks for equipment."""
    return [entity_json(t) for t in service.list_for_equipment(equipment_id)]


@router.post(
    "/equipment/{equipment_id}/maintenance",
    status_code=status.HTTP_201_CREATED,
)
def create_maintenance_task(
    equipment_id: UUID,
    body: MaintenanceTaskCreate,
    service: MaintenanceServiceDep,
) -> dict[str, Any]:
    """Create a maintenance task."""
    task = service.create(
        equipment_id,
        body.to_data(),
        duration=body.duration_data(),
        actor_id=body.actor_id,
        source=body.source,
        reason=body.reason,
    )
    return entity_json(task)


@router.get("/maintenance/{task_id}")
def get_maintenance_task(
    task_id: UUID,
    service: MaintenanceServiceDep,
) -> dict[str, Any]:
    """Return one maintenance task."""
    return entity_json(service.get(task_id))


@router.patch("/maintenance/{task_id}")
def update_maintenance_task(
    task_id: UUID,
    body: MaintenanceTaskUpdate,
    service: MaintenanceServiceDep,
) -> dict[str, Any]:
    """Update a maintenance task."""
    task = service.update(
        task_id,
        body.to_data(),
        actor_id=body.actor_id,
        source=body.source,
        reason=body.reason,
    )
    return entity_json(task)


@router.delete(
    "/maintenance/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_maintenance_task(
    task_id: UUID,
    service: MaintenanceServiceDep,
) -> Response:
    """Delete a maintenance task."""
    service.delete(task_id, source="api")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
