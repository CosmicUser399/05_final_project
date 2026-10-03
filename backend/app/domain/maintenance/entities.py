"""Maintenance tasks, durations and effects."""

from enum import StrEnum
from uuid import UUID

from pydantic import Field
from pydantic import model_validator

from app.domain.base import VersionedEntity
from app.domain.provenance import Provenance
from app.domain.reliability.distributions import DistributionSpec
from app.domain.units import TimeValue


class MaintenanceTaskType(StrEnum):
    """Kind of maintenance task."""

    INSPECTION = "INSPECTION"
    PREVENTIVE = "PREVENTIVE"
    CORRECTIVE = "CORRECTIVE"


class MaintenanceTrigger(StrEnum):
    """What starts a maintenance task."""

    CALENDAR = "CALENDAR"
    RUNNING_TIME = "RUNNING_TIME"
    CONDITION_BASED = "CONDITION_BASED"
    ON_FAILURE = "ON_FAILURE"


class MaintenanceEffectType(StrEnum):
    """Effect of a task on the equipment state."""

    RESTORE_AS_NEW = "RESTORE_AS_NEW"
    RESTORE_AS_OLD = "RESTORE_AS_OLD"
    PARTIAL_RESTORATION = "PARTIAL_RESTORATION"
    CHANGE_FAILURE_RATE_MULTIPLIER = "CHANGE_FAILURE_RATE_MULTIPLIER"
    RESET_FAILURE_AGE = "RESET_FAILURE_AGE"
    REDUCE_REMAINING_LIFE = "REDUCE_REMAINING_LIFE"
    ELIMINATE_FAILURE_MODE = "ELIMINATE_FAILURE_MODE"
    NONE = "NONE"


class MaintenanceTask(VersionedEntity):
    """A maintenance task. Inspections use ``DiagnosticTask`` data."""

    equipment_id: UUID
    failure_mode_id: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    task_type: MaintenanceTaskType
    trigger: MaintenanceTrigger
    interval: TimeValue | None = None
    cost: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def _check_interval(self) -> "MaintenanceTask":
        periodic = (
            MaintenanceTrigger.CALENDAR,
            MaintenanceTrigger.RUNNING_TIME,
        )
        if self.trigger in periodic:
            if self.interval is None or self.interval.value <= 0:
                raise ValueError(
                    f"interval > 0 is required for {self.trigger}"
                )
        elif self.interval is not None:
            raise ValueError(f"interval is not used for {self.trigger}")
        if (
            self.task_type is MaintenanceTaskType.CORRECTIVE
            and self.trigger is not MaintenanceTrigger.ON_FAILURE
        ):
            raise ValueError("CORRECTIVE task must trigger ON_FAILURE")
        return self


class MaintenanceDistribution(VersionedEntity):
    """Duration law of a maintenance task, with provenance."""

    maintenance_task_id: UUID
    distribution: DistributionSpec
    provenance: Provenance


class MaintenanceEffect(VersionedEntity):
    """Effect of a maintenance task on a failure mode or equipment.

    ``parameter`` meaning depends on ``effect_type``:
    ``PARTIAL_RESTORATION`` and ``REDUCE_REMAINING_LIFE`` - fraction
    in [0, 1]; ``CHANGE_FAILURE_RATE_MULTIPLIER`` - multiplier > 0.
    """

    maintenance_task_id: UUID
    effect_type: MaintenanceEffectType
    failure_mode_id: UUID | None = None
    parameter: float | None = Field(default=None, allow_inf_nan=False)

    @model_validator(mode="after")
    def _check_parameter(self) -> "MaintenanceEffect":
        kind = self.effect_type
        value = self.parameter
        fraction = (
            MaintenanceEffectType.PARTIAL_RESTORATION,
            MaintenanceEffectType.REDUCE_REMAINING_LIFE,
        )
        if kind in fraction:
            if value is None or not 0.0 <= value <= 1.0:
                raise ValueError(f"{kind} needs parameter in [0, 1]")
        elif kind is MaintenanceEffectType.CHANGE_FAILURE_RATE_MULTIPLIER:
            if value is None or value <= 0.0:
                raise ValueError(f"{kind} needs parameter > 0")
        elif value is not None:
            raise ValueError(f"{kind} does not take a parameter")
        if (
            kind is MaintenanceEffectType.ELIMINATE_FAILURE_MODE
            and self.failure_mode_id is None
        ):
            raise ValueError("ELIMINATE_FAILURE_MODE needs failure_mode_id")
        return self
