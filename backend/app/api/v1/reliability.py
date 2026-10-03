"""REST routes for reliability model validate/generate."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from fastapi import status

from app.api.deps import ReliabilityServiceDep
from app.api.v1.schemas import ReliabilityGenerateRequest
from app.api.v1.schemas import ReliabilityModelResponse
from app.api.v1.schemas import ValidationReportResponse
from app.domain.errors import NotFoundError

router = APIRouter(tags=["reliability"])


@router.post("/versions/{version_id}/validate")
def validate_version(
    version_id: UUID,
    service: ReliabilityServiceDep,
) -> ValidationReportResponse:
    """Run validation levels 2-5 for a system version."""
    report = service.validate(version_id)
    return ValidationReportResponse.from_report(report)


@router.post(
    "/versions/{version_id}/reliability/generate",
    status_code=status.HTTP_201_CREATED,
)
def generate_reliability_model(
    version_id: UUID,
    service: ReliabilityServiceDep,
    body: ReliabilityGenerateRequest | None = None,
) -> ReliabilityModelResponse:
    """Compile and persist a reliability model snapshot."""
    notes = None if body is None else body.notes
    row = service.generate(version_id, notes=notes)
    return ReliabilityModelResponse.from_row(row)


@router.get("/versions/{version_id}/reliability")
def get_latest_reliability_model(
    version_id: UUID,
    service: ReliabilityServiceDep,
) -> ReliabilityModelResponse:
    """Return the newest compiled model for a version."""
    row = service.get_latest(version_id)
    if row is None:
        raise NotFoundError(
            "reliability model not found for version",
            entity="ReliabilityModel",
            entity_id=str(version_id),
        )
    return ReliabilityModelResponse.from_row(row)


@router.get("/reliability-models/{model_id}")
def get_reliability_model(
    model_id: UUID,
    service: ReliabilityServiceDep,
) -> ReliabilityModelResponse:
    """Return one compiled reliability model by id."""
    return ReliabilityModelResponse.from_row(service.get(model_id))
