"""Simulation event types and the event record."""

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class EventType(StrEnum):
    """Kinds of discrete events processed by the RAM engine."""

    FAILURE = "FAILURE"
    POTENTIAL_FAILURE = "POTENTIAL_FAILURE"
    DIAGNOSTIC = "DIAGNOSTIC"
    DETECTION = "DETECTION"
    PM_START = "PM_START"
    PM_COMPLETE = "PM_COMPLETE"
    CM_START = "CM_START"
    CM_COMPLETE = "CM_COMPLETE"
    SPARE_REQUEST = "SPARE_REQUEST"
    SPARE_AVAILABLE = "SPARE_AVAILABLE"
    RESOURCE_BUSY = "RESOURCE_BUSY"
    RESOURCE_AVAILABLE = "RESOURCE_AVAILABLE"
    PRODUCTION_CHANGE = "PRODUCTION_CHANGE"
    END = "END"


class SimulationEvent(BaseModel):
    """One scheduled or recorded discrete event.

    ``seq`` is assigned by the queue and used for a deterministic
    tie-break when several events share the same time.
    """

    model_config = ConfigDict(frozen=True)

    time: float = Field(ge=0, allow_inf_nan=False)
    event_type: EventType
    seq: int = 0
    equipment_id: UUID | None = None
    failure_mode_id: UUID | None = None
    task_id: UUID | None = None
    resource_id: UUID | None = None
    spare_part_id: UUID | None = None
    details: dict[str, Any] = Field(default_factory=dict)
