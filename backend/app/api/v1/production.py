"""REST routes for production functions and impacts."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter
from fastapi import Response
from fastapi import status

from app.api.deps import ProductionServiceDep
from app.api.v1.schemas import ProductionFunctionCreate
from app.api.v1.schemas import ProductionFunctionUpdate
from app.api.v1.schemas import ProductionImpactCreate
from app.api.v1.schemas import ProductionImpactUpdate
from app.api.v1.schemas import entity_json

router = APIRouter(tags=["production"])


@router.get("/versions/{version_id}/production")
def list_production_functions(
    version_id: UUID,
    service: ProductionServiceDep,
) -> list[dict[str, Any]]:
    """List production functions on a version."""
    return [entity_json(f) for f in service.list_functions(version_id)]


@router.post(
    "/versions/{version_id}/production",
    status_code=status.HTTP_201_CREATED,
)
def create_production_function(
    version_id: UUID,
    body: ProductionFunctionCreate,
    service: ProductionServiceDep,
) -> dict[str, Any]:
    """Create a production function."""
    function = service.create_function(
        version_id,
        body.to_data(),
        actor_id=body.actor_id,
        source=body.source,
        reason=body.reason,
    )
    return entity_json(function)


@router.get("/production/{function_id}")
def get_production_function(
    function_id: UUID,
    service: ProductionServiceDep,
) -> dict[str, Any]:
    """Return one production function."""
    return entity_json(service.get_function(function_id))


@router.patch("/production/{function_id}")
def update_production_function(
    function_id: UUID,
    body: ProductionFunctionUpdate,
    service: ProductionServiceDep,
) -> dict[str, Any]:
    """Update a production function."""
    function = service.update_function(
        function_id,
        body.to_data(),
        actor_id=body.actor_id,
        source=body.source,
        reason=body.reason,
    )
    return entity_json(function)


@router.delete(
    "/production/{function_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_production_function(
    function_id: UUID,
    service: ProductionServiceDep,
) -> Response:
    """Delete a production function."""
    service.delete_function(function_id, source="api")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/versions/{version_id}/production-impacts")
def list_production_impacts(
    version_id: UUID,
    service: ProductionServiceDep,
) -> list[dict[str, Any]]:
    """List production impacts on a version."""
    return [entity_json(i) for i in service.list_impacts(version_id)]


@router.post(
    "/versions/{version_id}/production-impacts",
    status_code=status.HTTP_201_CREATED,
)
def create_production_impact(
    version_id: UUID,
    body: ProductionImpactCreate,
    service: ProductionServiceDep,
) -> dict[str, Any]:
    """Create a production impact."""
    impact = service.create_impact(
        version_id,
        body.to_data(),
        actor_id=body.actor_id,
        source=body.source,
        reason=body.reason,
    )
    return entity_json(impact)


@router.get("/production-impacts/{impact_id}")
def get_production_impact(
    impact_id: UUID,
    service: ProductionServiceDep,
) -> dict[str, Any]:
    """Return one production impact."""
    return entity_json(service.get_impact(impact_id))


@router.patch("/production-impacts/{impact_id}")
def update_production_impact(
    impact_id: UUID,
    body: ProductionImpactUpdate,
    service: ProductionServiceDep,
) -> dict[str, Any]:
    """Update a production impact."""
    impact = service.update_impact(
        impact_id,
        body.to_data(),
        actor_id=body.actor_id,
        source=body.source,
        reason=body.reason,
    )
    return entity_json(impact)


@router.delete(
    "/production-impacts/{impact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_production_impact(
    impact_id: UUID,
    service: ProductionServiceDep,
) -> Response:
    """Delete a production impact."""
    service.delete_impact(impact_id, source="api")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
