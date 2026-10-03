"""Diagnostic (condition monitoring) tasks."""

from uuid import UUID

from pydantic import Field
from pydantic import field_validator

from app.domain.base import VersionedEntity
from app.domain.provenance import Provenance
from app.domain.units import TimeValue


class DiagnosticTask(VersionedEntity):
    """Periodic check that may detect a potential failure.

    A check made at time ``t`` inside ``[T_f - PF, T_f)`` detects the
    potential failure with ``detection_probability``. A healthy item
    triggers a false alarm with ``false_positive_probability``.
    """

    equipment_id: UUID
    failure_mode_id: UUID
    name: str = Field(min_length=1, max_length=200)
    method: str | None = Field(default=None, max_length=200)
    interval: TimeValue
    detection_probability: float = Field(ge=0.0, le=1.0)
    false_positive_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    duration: TimeValue | None = None
    cost: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    provenance: Provenance | None = None

    @field_validator("interval")
    @classmethod
    def _interval_positive(cls, value: TimeValue) -> TimeValue:
        if value.value <= 0:
            raise ValueError("interval must be > 0")
        return value
