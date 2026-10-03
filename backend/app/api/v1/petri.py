"""REST routes for Petri model generate/validate/analyze."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter
from fastapi import status

from app.api.deps import PetriServiceDep
from app.api.deps import SimulationServiceDep
from app.api.v1.schemas import PetriAnalyzeRequest
from app.api.v1.schemas import PetriCanonicalRequest
from app.api.v1.schemas import PetriConformanceRequest
from app.api.v1.schemas import PetriDiffRequest
from app.api.v1.schemas import PetriGenerateRequest
from app.api.v1.schemas import PetriModelResponse
from app.api.v1.schemas import PetriVerifyRequest
from app.domain.errors import NotFoundError

router = APIRouter(tags=["petri"])


@router.post(
    "/versions/{version_id}/petri/generate",
    status_code=status.HTTP_201_CREATED,
)
def generate_petri_model(
    version_id: UUID,
    service: PetriServiceDep,
    body: PetriGenerateRequest | None = None,
) -> PetriModelResponse:
    """Generate a Petri model from the compiled reliability model."""
    notes = None if body is None else body.notes
    row = service.generate(version_id, notes=notes)
    return PetriModelResponse.from_row(row)


@router.get("/versions/{version_id}/petri")
def get_latest_petri_model(
    version_id: UUID,
    service: PetriServiceDep,
) -> PetriModelResponse:
    """Return the newest Petri model for a version."""
    row = service.get_latest(version_id)
    if row is None:
        raise NotFoundError(
            "petri model not found for version",
            entity="PetriModel",
            entity_id=str(version_id),
        )
    return PetriModelResponse.from_row(row)


@router.get("/petri/{petri_id}")
def get_petri_model(
    petri_id: UUID,
    service: PetriServiceDep,
) -> PetriModelResponse:
    """Return one Petri model by id."""
    return PetriModelResponse.from_row(service.get(petri_id))


@router.post("/petri/{petri_id}/validate")
def validate_petri_model(
    petri_id: UUID,
    service: PetriServiceDep,
) -> dict[str, Any]:
    """Validate structure locally and via Petri-Pilot."""
    return service.validate(petri_id)


@router.post("/petri/{petri_id}/analyze")
def analyze_petri_model(
    petri_id: UUID,
    service: PetriServiceDep,
    body: PetriAnalyzeRequest | None = None,
) -> dict[str, Any]:
    """Analyze reachability/deadlock/liveness via Petri-Pilot."""
    full = False if body is None else body.full
    subnet_key = None if body is None else body.subnet_key
    return service.analyze(petri_id, full=full, subnet_key=subnet_key)


@router.post("/petri/{petri_id}/verify")
def verify_petri_model(
    petri_id: UUID,
    service: PetriServiceDep,
    body: PetriVerifyRequest | None = None,
) -> dict[str, Any]:
    """Verify formal properties on Petri subnets."""
    properties = None if body is None else body.properties
    subnet_key = None if body is None else body.subnet_key
    return service.verify(
        petri_id,
        properties,
        subnet_key=subnet_key,
    )


@router.post("/petri/{petri_id}/conformance")
def conformance_petri_model(
    petri_id: UUID,
    service: PetriServiceDep,
    simulations: SimulationServiceDep,
    body: PetriConformanceRequest,
) -> dict[str, Any]:
    """Cross-check a RAM event log against Petri subnets."""
    page = simulations.get_events(
        body.simulation_run_id,
        offset=0,
        limit=1000,
    )
    events = [
        _EventView(item)
        for item in page["items"]
        if body.trial_run_id is None
        or item.get("trial_run_id") == body.trial_run_id
    ]
    return service.conformance(
        petri_id,
        events,
        subnet_key=body.subnet_key,
    )


@router.post("/petri/{petri_id}/diff")
def diff_petri_models(
    petri_id: UUID,
    service: PetriServiceDep,
    body: PetriDiffRequest,
) -> dict[str, Any]:
    """Compare two Petri models (system subnets)."""
    return service.diff(petri_id, body.other_petri_model_id)


@router.post("/petri/{petri_id}/canonical")
def canonical_petri_model(
    petri_id: UUID,
    service: PetriServiceDep,
    body: PetriCanonicalRequest | None = None,
) -> dict[str, Any]:
    """Return isomorphism-invariant canonical ids for subnets."""
    subnet_key = None if body is None else body.subnet_key
    return service.canonical(petri_id, subnet_key=subnet_key)


class _EventView:
    """Adapt API/DB event dicts to the conformance protocol."""

    def __init__(self, row: dict[str, Any]) -> None:
        self.time_minutes = float(row.get("time_minutes") or 0.0)
        self.event_type = str(row.get("event_type") or "")
        equipment = row.get("equipment_id")
        failure = row.get("failure_mode_id")
        self.equipment_id = None if equipment is None else UUID(str(equipment))
        self.failure_mode_id = None if failure is None else UUID(str(failure))
