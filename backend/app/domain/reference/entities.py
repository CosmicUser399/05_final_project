"""Reference parameters loaded from OREDA / ISO extracts."""

from enum import StrEnum
from uuid import UUID

from pydantic import Field
from pydantic import field_validator

from app.domain.base import Entity
from app.domain.provenance import Confidence
from app.domain.provenance import SourceType


class ParameterKind(StrEnum):
    """Kind of numeric reliability parameter in a reference row."""

    FAILURE_RATE = "FAILURE_RATE"
    MTTF = "MTTF"
    MTTR = "MTTR"
    REPAIR_TIME = "REPAIR_TIME"
    DISTRIBUTION = "DISTRIBUTION"
    OTHER = "OTHER"


class ReferenceParameter(Entity):
    """One curated reliability parameter with full provenance.

    Values are never hard-coded in business logic; they come from
    ingested CSV/JSON extracts reviewed by an engineer.
    """

    source_id: UUID
    equipment_class: str = Field(min_length=1, max_length=200)
    equipment_class_code: str | None = Field(
        default=None,
        max_length=100,
    )
    failure_mode_code: str | None = Field(default=None, max_length=100)
    failure_mode_name: str | None = Field(default=None, max_length=200)
    parameter_name: str = Field(min_length=1, max_length=200)
    parameter_kind: ParameterKind
    value: float = Field(allow_inf_nan=False)
    unit: str = Field(min_length=1, max_length=64)
    distribution_type: str | None = Field(default=None, max_length=64)
    distribution_params_json: dict[str, float] | None = None
    source_type: SourceType
    source_document: str = Field(min_length=1, max_length=300)
    source_reference: str = Field(min_length=1, max_length=500)
    confidence: Confidence = Confidence.MEDIUM
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("equipment_class", "parameter_name", "unit")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped
