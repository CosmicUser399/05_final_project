"""REST routes for equipment connections."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter
from fastapi import Response
from fastapi import status

from app.api.deps import ConnectionsServiceDep
from app.api.v1.schemas import ConnectionCreate
from app.api.v1.schemas import entity_json

router = APIRouter(tags=["connections"])


@router.get("/versions/{version_id}/connections")
def list_connections(
    version_id: UUID,
    service: ConnectionsServiceDep,
) -> list[dict[str, Any]]:
    """List equipment connections on a version."""
    return [entity_json(c) for c in service.list_for_version(version_id)]


@router.post(
    "/versions/{version_id}/connections",
    status_code=status.HTTP_201_CREATED,
)
def create_connection(
    version_id: UUID,
    body: ConnectionCreate,
    service: ConnectionsServiceDep,
) -> dict[str, Any]:
    """Create a connection between equipment."""
    connection = service.create(
        version_id,
        body.to_data(),
        actor_id=body.actor_id,
        source=body.source,
        reason=body.reason,
    )
    return entity_json(connection)


@router.delete(
    "/connections/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_connection(
    connection_id: UUID,
    service: ConnectionsServiceDep,
) -> Response:
    """Delete an equipment connection."""
    service.delete(connection_id, source="api")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
