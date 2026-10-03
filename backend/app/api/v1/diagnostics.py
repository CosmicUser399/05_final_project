"""REST routes for diagnostic tasks."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter
from fastapi import Response
from fastapi import status

from app.api.deps import DiagnosticsServiceDep
from app.api.v1.schemas import DiagnosticTaskCreate
from app.api.v1.schemas import DiagnosticTaskUpdate
from app.api.v1.schemas import entity_json

router = APIRouter(tags=["diagnostics"])


@router.get("/equipment/{equipment_id}/diagnostics")
def list_diagnostic_tasks(
    equipment_id: UUID,
    service: DiagnosticsServiceDep,
) -> list[dict[str, Any]]:
    """List diagnostic tasks for equipment."""
    return [entity_json(t) for t in service.list_for_equipment(equipment_id)]


@router.post(
    "/equipment/{equipment_id}/diagnostics",
    status_code=status.HTTP_201_CREATED,
)
def create_diagnostic_task(
    equipment_id: UUID,
    body: DiagnosticTaskCreate,
    service: DiagnosticsServiceDep,
) -> dict[str, Any]:
    """Create a diagnostic task."""
    task = service.create(
        equipment_id,
        body.to_data(),
        actor_id=body.actor_id,
        source=body.source,
        reason=body.reason,
    )
    return entity_json(task)


@router.get("/diagnostics/{task_id}")
def get_diagnostic_task(
    task_id: UUID,
    service: DiagnosticsServiceDep,
) -> dict[str, Any]:
    """Return one diagnostic task."""
    return entity_json(service.get(task_id))


@router.patch("/diagnostics/{task_id}")
def update_diagnostic_task(
    task_id: UUID,
    body: DiagnosticTaskUpdate,
    service: DiagnosticsServiceDep,
) -> dict[str, Any]:
    """Update a diagnostic task."""
    task = service.update(
        task_id,
        body.to_data(),
        actor_id=body.actor_id,
        source=body.source,
        reason=body.reason,
    )
    return entity_json(task)


@router.delete(
    "/diagnostics/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_diagnostic_task(
    task_id: UUID,
    service: DiagnosticsServiceDep,
) -> Response:
    """Delete a diagnostic task."""
    service.delete(task_id, source="api")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
