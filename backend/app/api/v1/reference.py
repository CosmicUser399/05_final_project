"""REST routes for OREDA / ISO 14224 reference data."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter
from fastapi import Query
from fastapi import status
from pydantic import BaseModel
from pydantic import Field

from app.api.deps import ReferenceDataServiceDep

router = APIRouter(prefix="/reference", tags=["reference"])


class IngestRequest(BaseModel):
    """Body for demo seed ingestion."""

    replace: bool = False


class LinkEquipmentRequest(BaseModel):
    """Attach a taxonomy node to equipment."""

    taxonomy_node_id: UUID
    actor_id: UUID | None = None
    reason: str | None = Field(default=None, max_length=2000)


class ApplyParameterRequest(BaseModel):
    """Apply a reference parameter to a failure mode."""

    failure_mode_id: UUID
    actor_id: UUID | None = None
    reason: str | None = Field(default=None, max_length=2000)


@router.get("/status")
def reference_status(service: ReferenceDataServiceDep) -> dict[str, Any]:
    """Return whether reference data is loaded."""
    return service.status()


@router.post("/ingest", status_code=status.HTTP_200_OK)
def ingest_demo(
    body: IngestRequest,
    service: ReferenceDataServiceDep,
) -> dict[str, Any]:
    """Load curated demo OREDA/ISO extracts into Domain DB."""
    return service.ingest_demo(replace=body.replace)


@router.get("/parameters")
def search_parameters(
    service: ReferenceDataServiceDep,
    query: str | None = Query(default=None),
    equipment_class: str | None = Query(default=None),
    equipment_class_code: str | None = Query(default=None),
    parameter_kind: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """Search curated OREDA-style parameters."""
    return service.search_parameters(
        query=query,
        equipment_class=equipment_class,
        equipment_class_code=equipment_class_code,
        parameter_kind=parameter_kind,
        limit=limit,
    )


@router.get("/parameters/{parameter_id}")
def get_parameter(
    parameter_id: UUID,
    service: ReferenceDataServiceDep,
) -> dict[str, Any]:
    """Return one reference parameter with provenance fields."""
    return service.get_parameter(parameter_id)


@router.get("/taxonomy")
def search_taxonomy(
    service: ReferenceDataServiceDep,
    query: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """Search ISO 14224 taxonomy nodes."""
    return service.search_taxonomy(query=query, limit=limit)


@router.get("/suggest")
def suggest_for_class(
    service: ReferenceDataServiceDep,
    equipment_class: str = Query(min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """Suggest ISO node + OREDA parameters for an equipment class."""
    items = service.suggest_for_class(equipment_class, limit=limit)
    return {
        "equipment_class": equipment_class,
        "count": len(items),
        "items": items,
    }


@router.post("/equipment/{equipment_id}/link")
def link_equipment(
    equipment_id: UUID,
    body: LinkEquipmentRequest,
    service: ReferenceDataServiceDep,
) -> dict[str, Any]:
    """Link equipment to an ISO 14224 taxonomy node."""
    return service.link_equipment(
        equipment_id,
        body.taxonomy_node_id,
        actor_id=body.actor_id,
        reason=body.reason,
    )


@router.post("/equipment/{equipment_id}/auto-link")
def auto_link_equipment(
    equipment_id: UUID,
    service: ReferenceDataServiceDep,
) -> dict[str, Any]:
    """Auto-map equipment class to ISO taxonomy when possible."""
    result = service.auto_link_equipment(equipment_id)
    if result is None:
        return {
            "linked": False,
            "equipment_id": str(equipment_id),
            "message": "no ISO taxonomy match for equipment class",
        }
    return {"linked": True, "equipment": result}


@router.post("/parameters/{parameter_id}/apply")
def apply_parameter(
    parameter_id: UUID,
    body: ApplyParameterRequest,
    service: ReferenceDataServiceDep,
) -> dict[str, Any]:
    """Apply OREDA parameter to a failure mode distribution."""
    return service.apply_to_failure_mode(
        parameter_id,
        body.failure_mode_id,
        actor_id=body.actor_id,
        reason=body.reason,
    )
