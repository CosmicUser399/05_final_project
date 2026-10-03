"""Pydantic DTOs for AI/Fabricate-generated structure.

These are untrusted inputs: they must pass schema/domain validation
before becoming a reviewable ``Proposal``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator

from app.domain.equipment.entities import ConnectionType
from app.domain.equipment.entities import Criticality
from app.domain.equipment.entities import OperatingMode
from app.domain.equipment.entities import StandbyMode
from app.domain.provenance import ValueStatus


def _strip_required(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


class GeneratedSystemBrief(BaseModel):
    """Interpretation of a free-text plant description."""

    model_config = ConfigDict(frozen=True)

    plant_type: str = Field(min_length=1, max_length=200)
    capacity_value: float | None = Field(default=None, ge=0)
    capacity_unit: str | None = Field(default=None, max_length=64)
    summary: str = Field(min_length=1, max_length=2000)
    assumptions: list[str] = Field(default_factory=list)


class GeneratedEquipment(BaseModel):
    """Proposed equipment row (structure only)."""

    model_config = ConfigDict(frozen=True)

    tag: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    parent_tag: str | None = Field(default=None, max_length=64)
    category: str | None = Field(default=None, max_length=100)
    equipment_class: str | None = Field(default=None, max_length=100)
    equipment_type: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=200)
    quantity: int = Field(default=1, ge=1, le=10_000)
    criticality: Criticality = Criticality.MEDIUM
    operating_mode: OperatingMode = OperatingMode.CONTINUOUS
    standby_mode: StandbyMode = StandbyMode.NONE
    is_repairable: bool = True
    value_status: ValueStatus = ValueStatus.ESTIMATED

    @field_validator("tag", "name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        return _strip_required(value)


class GeneratedComponent(BaseModel):
    """Proposed equipment component."""

    model_config = ConfigDict(frozen=True)

    equipment_tag: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    quantity: int = Field(default=1, ge=1, le=10_000)


class GeneratedConnection(BaseModel):
    """Proposed link between equipment tags."""

    model_config = ConfigDict(frozen=True)

    from_tag: str = Field(min_length=1, max_length=64)
    to_tag: str = Field(min_length=1, max_length=64)
    connection_type: ConnectionType = ConnectionType.PROCESS
    description: str | None = Field(default=None, max_length=2000)


class GeneratedFailureMode(BaseModel):
    """Optional draft failure mode (params stay UNKNOWN by default)."""

    model_config = ConfigDict(frozen=True)

    equipment_tag: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    is_detectable: bool = False
    value_status: ValueStatus = ValueStatus.UNKNOWN


class GeneratedMaintenanceTask(BaseModel):
    """Optional draft maintenance task without numeric params."""

    model_config = ConfigDict(frozen=True)

    equipment_tag: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    task_type: str = Field(default="PREVENTIVE", max_length=64)
    value_status: ValueStatus = ValueStatus.UNKNOWN


class EquipmentProposalPayload(BaseModel):
    """Validated payload ready to become a Proposal."""

    model_config = ConfigDict(frozen=True)

    brief: GeneratedSystemBrief | None = None
    equipment: list[GeneratedEquipment] = Field(default_factory=list)
    components: list[GeneratedComponent] = Field(default_factory=list)
    connections: list[GeneratedConnection] = Field(default_factory=list)
    failure_modes: list[GeneratedFailureMode] = Field(default_factory=list)
    maintenance_tasks: list[GeneratedMaintenanceTask] = Field(
        default_factory=list
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
