"""REST routes for failure modes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter
from fastapi import Response
from fastapi import status

from app.api.deps import FailureModeServiceDep
from app.api.v1.schemas import FailureModeCreate
from app.api.v1.schemas import FailureModeUpdate
from app.api.v1.schemas import entity_json

router = APIRouter(tags=["failure-modes"])


@router.get("/equipment/{equipment_id}/failure-modes")
def list_failure_modes(
    equipment_id: UUID,
    service: FailureModeServiceDep,
) -> list[dict[str, Any]]:
    """List failure modes for equipment."""
    return [entity_json(m) for m in service.list_for_equipment(equipment_id)]


@router.post(
    "/equipment/{equipment_id}/failure-modes",
    status_code=status.HTTP_201_CREATED,
)
def create_failure_mode(
    equipment_id: UUID,
    body: FailureModeCreate,
    service: FailureModeServiceDep,
) -> dict[str, Any]:
    """Create a failure mode, optionally with a distribution."""
    mode = service.create(
        equipment_id,
        body.to_mode_data(),
        distribution=body.distribution_data(),
        actor_id=body.actor_id,
        source=body.source,
        reason=body.reason,
    )
    return entity_json(mode)


@router.get("/failure-modes/{failure_mode_id}")
def get_failure_mode(
    failure_mode_id: UUID,
    service: FailureModeServiceDep,
) -> dict[str, Any]:
    """Return one failure mode."""
    return entity_json(service.get(failure_mode_id))


@router.patch("/failure-modes/{failure_mode_id}")
def update_failure_mode(
    failure_mode_id: UUID,
    body: FailureModeUpdate,
    service: FailureModeServiceDep,
) -> dict[str, Any]:
    """Update a failure mode."""
    mode = service.update(
        failure_mode_id,
        body.to_data(),
        actor_id=body.actor_id,
        source=body.source,
        reason=body.reason,
    )
    return entity_json(mode)


@router.delete(
    "/failure-modes/{failure_mode_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_failure_mode(
    failure_mode_id: UUID,
    service: FailureModeServiceDep,
) -> Response:
    """Delete a failure mode."""
    service.delete(failure_mode_id, source="api")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
