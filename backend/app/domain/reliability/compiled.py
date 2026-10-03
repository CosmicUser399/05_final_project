"""Compiled reliability model: frozen snapshot for simulation.

All times are in minutes. Entity order is stable so that the same
domain content always produces the same ``model_hash``.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from app.domain.equipment.entities import Criticality
from app.domain.equipment.entities import StandbyMode
from app.domain.maintenance.entities import MaintenanceEffectType
from app.domain.maintenance.entities import MaintenanceTaskType
from app.domain.maintenance.entities import MaintenanceTrigger
from app.domain.reliability.distributions import DistributionSpec
from app.domain.reliability.entities import StructureType


class CompiledModel(BaseModel):
    """Immutable reliability model ready for the RAM engine."""

    model_config = ConfigDict(frozen=True)

    version_id: UUID
    equipment: tuple[CompiledEquipment, ...] = ()
    failure_modes: tuple[CompiledFailureMode, ...] = ()
    maintenance_tasks: tuple[CompiledMaintenanceTask, ...] = ()
    diagnostic_tasks: tuple[CompiledDiagnosticTask, ...] = ()
    resources: tuple[CompiledResource, ...] = ()
    spare_parts: tuple[CompiledSparePart, ...] = ()
    production: CompiledProduction | None = None
    structures: tuple[CompiledStructure, ...] = ()
    connections: tuple[CompiledConnection, ...] = ()

    def canonical_json(self) -> str:
        """Return deterministic JSON used for hashing."""
        payload = self.model_dump(mode="json")
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def model_hash(self) -> str:
        """Return SHA-256 of the canonical JSON."""
        digest = hashlib.sha256(self.canonical_json().encode("utf-8"))
        return digest.hexdigest()


class CompiledEquipment(BaseModel):
    """Equipment row in the compiled model."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    lineage_id: UUID
    tag: str
    name: str
    parent_id: UUID | None = None
    criticality: Criticality
    standby_mode: StandbyMode
    is_repairable: bool
    quantity: int


class CompiledFailureMode(BaseModel):
    """Failure mode with distribution and PF in minutes."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    lineage_id: UUID
    equipment_id: UUID
    component_id: UUID | None = None
    name: str
    is_detectable: bool
    pf_interval_minutes: float | None = None
    distribution: DistributionSpec


class CompiledMaintenanceTask(BaseModel):
    """Maintenance task with duration in minutes."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    lineage_id: UUID
    equipment_id: UUID
    failure_mode_id: UUID | None = None
    name: str
    task_type: MaintenanceTaskType
    trigger: MaintenanceTrigger
    interval_minutes: float | None = None
    duration: DistributionSpec
    effect_type: MaintenanceEffectType = MaintenanceEffectType.RESTORE_AS_NEW
    effect_parameter: float | None = None
    effect_failure_mode_id: UUID | None = None
    resource_requirements: tuple[CompiledResourceReq, ...] = ()
    spare_requirements: tuple[CompiledSpareReq, ...] = ()
    cost: float | None = None


class CompiledDiagnosticTask(BaseModel):
    """Diagnostic task with interval in minutes."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    lineage_id: UUID
    equipment_id: UUID
    failure_mode_id: UUID
    name: str
    interval_minutes: float
    detection_probability: float
    false_positive_probability: float
    duration_minutes: float = 0.0
    cost: float | None = None


class CompiledResource(BaseModel):
    """Resource capacity."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    lineage_id: UUID
    name: str
    capacity: int
    cost_per_hour: float | None = None


class CompiledSparePart(BaseModel):
    """Spare part stock and lead time in minutes."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    lineage_id: UUID
    name: str
    stock: int
    lead_time_minutes: float | None = None
    unit_cost: float | None = None


class CompiledResourceReq(BaseModel):
    """Resource need of a maintenance task."""

    model_config = ConfigDict(frozen=True)

    resource_id: UUID
    quantity: int


class CompiledSpareReq(BaseModel):
    """Spare need of a maintenance task."""

    model_config = ConfigDict(frozen=True)

    spare_part_id: UUID
    quantity: int


class CompiledProduction(BaseModel):
    """Production function and impacts."""

    model_config = ConfigDict(frozen=True)

    nominal_rate: float
    unit: str
    impacts: tuple[CompiledProductionImpact, ...] = ()


class CompiledProductionImpact(BaseModel):
    """Loss fraction when equipment/mode is down."""

    model_config = ConfigDict(frozen=True)

    equipment_id: UUID
    failure_mode_id: UUID | None = None
    loss_fraction: float


class CompiledStructure(BaseModel):
    """Reliability structure node."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    lineage_id: UUID
    name: str
    structure_type: StructureType
    k: int | None = None
    parent_structure_id: UUID | None = None
    members: tuple[CompiledStructureMember, ...] = ()


class CompiledStructureMember(BaseModel):
    """Structure member."""

    model_config = ConfigDict(frozen=True)

    equipment_id: UUID | None = None
    child_structure_id: UUID | None = None
    position: int = 0


class CompiledConnection(BaseModel):
    """Equipment connection."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    source_id: UUID
    target_id: UUID
    connection_type: str


class ScenarioChangeType(StrEnum):
    """Kinds of scenario overlay changes."""

    CHANGE_DIAGNOSTIC_INTERVAL = "CHANGE_DIAGNOSTIC_INTERVAL"
    CHANGE_DETECTION_PROBABILITY = "CHANGE_DETECTION_PROBABILITY"
    CHANGE_PM_INTERVAL = "CHANGE_PM_INTERVAL"
    CHANGE_MAINTENANCE_DISTRIBUTION = "CHANGE_MAINTENANCE_DISTRIBUTION"
    CHANGE_RESOURCE = "CHANGE_RESOURCE"
    CHANGE_SPARE_STOCK = "CHANGE_SPARE_STOCK"
    CHANGE_FAILURE_PARAMETER = "CHANGE_FAILURE_PARAMETER"
    ENABLE_TASK = "ENABLE_TASK"
    DISABLE_TASK = "DISABLE_TASK"


class ScenarioChange(BaseModel):
    """One overlay change referenced by ``lineage_id``."""

    model_config = ConfigDict(frozen=True)

    change_type: ScenarioChangeType
    target_lineage_id: UUID
    parameters: dict[str, Any] = Field(default_factory=dict)


class ScenarioOverlay(BaseModel):
    """Set of changes applied on top of a compiled model."""

    model_config = ConfigDict(frozen=True)

    changes: tuple[ScenarioChange, ...] = ()

    def scenario_hash(self) -> str:
        """Return SHA-256 of the canonical change set."""
        payload = self.model_dump(mode="json")
        text = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
