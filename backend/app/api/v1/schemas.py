"""Shared API DTOs and domain serialization helpers."""

# ruff: noqa: D101, D102

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from app.domain.equipment.entities import ConnectionType
from app.domain.equipment.entities import Criticality
from app.domain.equipment.entities import Equipment
from app.domain.equipment.entities import OperatingMode
from app.domain.equipment.entities import StandbyMode
from app.domain.maintenance.entities import MaintenanceTaskType
from app.domain.maintenance.entities import MaintenanceTrigger
from app.domain.provenance import Confidence
from app.domain.provenance import Provenance
from app.domain.provenance import SourceType
from app.domain.reliability.distributions import parse_distribution
from app.domain.reliability.pf import PFInterval
from app.domain.system.content import SystemVersionContent
from app.domain.system.entities import System
from app.domain.system.entities import SystemVersion
from app.domain.system.entities import VersionStatus
from app.domain.units import MassRate
from app.domain.units import MassUnit
from app.domain.units import TimeUnit
from app.domain.units import TimeValue


class AuditFields(BaseModel):
    """Optional audit metadata on write requests."""

    actor_id: UUID | None = None
    source: str | None = None
    reason: str | None = None


class TimeValueDto(BaseModel):
    """Duration as ``{value, unit}``."""

    value: float = Field(ge=0)
    unit: TimeUnit

    def to_domain(self) -> TimeValue:
        return TimeValue(value=self.value, unit=self.unit)


class PFIntervalDto(BaseModel):
    """PF interval as ``{value, unit}``."""

    value: float = Field(gt=0)
    unit: TimeUnit

    def to_domain(self) -> PFInterval:
        return PFInterval(value=self.value, unit=self.unit)


class MassRateDto(BaseModel):
    """Mass flow rate."""

    value: float = Field(ge=0)
    mass_unit: MassUnit
    time_unit: TimeUnit

    def to_domain(self) -> MassRate:
        return MassRate(
            value=self.value,
            mass_unit=self.mass_unit,
            time_unit=self.time_unit,
        )


class ProvenanceDto(BaseModel):
    """Provenance of an engineering parameter."""

    source_type: SourceType
    source_reference: str | None = None
    confidence: Confidence = Confidence.LOW
    generated_by: str | None = None
    generated_at: datetime | None = None

    def to_domain(self) -> Provenance:
        return Provenance(
            source_type=self.source_type,
            source_reference=self.source_reference,
            confidence=self.confidence,
            generated_by=self.generated_by,
            generated_at=self.generated_at,
        )


def entity_json(model: BaseModel) -> dict[str, Any]:
    """Serialize a domain entity for JSON responses."""
    return model.model_dump(mode="json")


class SystemCreate(BaseModel):
    name: str
    description: str | None = None
    created_by: UUID | None = None


class SystemUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class SystemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    created_at: datetime
    created_by: UUID | None

    @classmethod
    def from_domain(cls, system: System) -> SystemResponse:
        return cls.model_validate(system)


class VersionCreate(BaseModel):
    clone_from: UUID | None = None
    comment: str | None = None
    created_by: UUID | None = None


class VersionTransition(BaseModel):
    status: VersionStatus


class ReliabilityGenerateRequest(BaseModel):
    notes: str | None = None


class ValidationIssueResponse(BaseModel):
    code: str
    message: str
    level: str
    severity: str
    entity: str | None = None
    entity_id: str | None = None


class ValidationReportResponse(BaseModel):
    is_valid: bool
    issues: list[ValidationIssueResponse]

    @classmethod
    def from_report(
        cls,
        report: Any,
    ) -> ValidationReportResponse:
        return cls(
            is_valid=report.is_valid,
            issues=[
                ValidationIssueResponse(
                    code=i.code,
                    message=i.message,
                    level=str(i.level),
                    severity=str(i.severity),
                    entity=i.entity,
                    entity_id=i.entity_id,
                )
                for i in report.issues
            ],
        )


class ReliabilityModelResponse(BaseModel):
    id: UUID
    version_id: UUID
    model_hash: str
    validation_status: str
    generated_at: datetime
    notes: str | None = None
    snapshot: dict[str, Any] | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> ReliabilityModelResponse:
        return cls.model_validate(row)


class VersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    system_id: UUID
    lineage_id: UUID
    version_number: int
    status: VersionStatus
    parent_version_id: UUID | None
    comment: str | None
    created_at: datetime
    created_by: UUID | None
    validated_at: datetime | None
    released_at: datetime | None

    @classmethod
    def from_domain(cls, version: SystemVersion) -> VersionResponse:
        return cls.model_validate(version)


class VersionModelResponse(BaseModel):
    version: VersionResponse
    content: dict[str, list[dict[str, Any]]]

    @classmethod
    def from_domain(
        cls,
        version: SystemVersion,
        content: SystemVersionContent,
    ) -> VersionModelResponse:
        payload = {
            "equipment": [entity_json(e) for e in content.equipment],
            "components": [entity_json(c) for c in content.components],
            "connections": [entity_json(c) for c in content.connections],
            "failure_modes": [entity_json(m) for m in content.failure_modes],
            "failure_distributions": [
                entity_json(d) for d in content.failure_distributions
            ],
            "maintenance_tasks": [
                entity_json(t) for t in content.maintenance_tasks
            ],
            "maintenance_distributions": [
                entity_json(d) for d in content.maintenance_distributions
            ],
            "maintenance_effects": [
                entity_json(e) for e in content.maintenance_effects
            ],
            "resources": [entity_json(r) for r in content.resources],
            "spare_parts": [entity_json(p) for p in content.spare_parts],
            "resource_requirements": [
                entity_json(r) for r in content.resource_requirements
            ],
            "spare_part_requirements": [
                entity_json(r) for r in content.spare_part_requirements
            ],
            "diagnostic_tasks": [
                entity_json(t) for t in content.diagnostic_tasks
            ],
            "production_functions": [
                entity_json(f) for f in content.production_functions
            ],
            "production_impacts": [
                entity_json(i) for i in content.production_impacts
            ],
            "structures": [entity_json(s) for s in content.structures],
            "structure_members": [
                entity_json(m) for m in content.structure_members
            ],
        }
        return cls(
            version=VersionResponse.from_domain(version),
            content=payload,
        )


class EquipmentCreate(AuditFields):
    tag: str
    name: str
    description: str | None = None
    parent_id: UUID | None = None
    taxonomy_node_id: UUID | None = None
    category: str | None = None
    equipment_class: str | None = None
    equipment_type: str | None = None
    location: str | None = None
    quantity: int = 1
    criticality: Criticality = Criticality.MEDIUM
    operating_mode: OperatingMode = OperatingMode.CONTINUOUS
    standby_mode: StandbyMode = StandbyMode.NONE
    is_repairable: bool = True

    def to_data(self) -> dict[str, Any]:
        return self.model_dump(
            exclude={"actor_id", "source", "reason"},
            exclude_none=True,
        )


class EquipmentUpdate(AuditFields):
    tag: str | None = None
    name: str | None = None
    description: str | None = None
    parent_id: UUID | None = None
    taxonomy_node_id: UUID | None = None
    category: str | None = None
    equipment_class: str | None = None
    equipment_type: str | None = None
    location: str | None = None
    quantity: int | None = None
    criticality: Criticality | None = None
    operating_mode: OperatingMode | None = None
    standby_mode: StandbyMode | None = None
    is_repairable: bool | None = None

    def to_data(self) -> dict[str, Any]:
        return self.model_dump(
            exclude={"actor_id", "source", "reason"},
            exclude_unset=True,
        )


class EquipmentResponse(BaseModel):
    @classmethod
    def from_domain(cls, equipment: Equipment) -> dict[str, Any]:
        return entity_json(equipment)


class FailureDistributionCreate(BaseModel):
    distribution: dict[str, Any]
    provenance: ProvenanceDto

    def to_data(self) -> dict[str, Any]:
        return {
            "distribution": parse_distribution(self.distribution),
            "provenance": self.provenance.to_domain(),
        }


class FailureModeCreate(AuditFields):
    name: str
    description: str | None = None
    component_id: UUID | None = None
    is_detectable: bool = False
    pf_interval: PFIntervalDto | None = None
    distribution: FailureDistributionCreate | None = None

    def to_mode_data(self) -> dict[str, Any]:
        data = self.model_dump(
            exclude={
                "actor_id",
                "source",
                "reason",
                "distribution",
                "pf_interval",
            },
            exclude_none=True,
        )
        if self.pf_interval is not None:
            data["pf_interval"] = self.pf_interval.to_domain()
        return data

    def distribution_data(self) -> dict[str, Any] | None:
        if self.distribution is None:
            return None
        return self.distribution.to_data()


class FailureModeUpdate(AuditFields):
    name: str | None = None
    description: str | None = None
    component_id: UUID | None = None
    is_detectable: bool | None = None
    pf_interval: PFIntervalDto | None = None

    def to_data(self) -> dict[str, Any]:
        raw = self.model_dump(
            exclude={"actor_id", "source", "reason", "pf_interval"},
            exclude_unset=True,
        )
        if self.pf_interval is not None:
            raw["pf_interval"] = self.pf_interval.to_domain()
        return raw


class MaintenanceDurationCreate(BaseModel):
    distribution: dict[str, Any]
    provenance: ProvenanceDto

    def to_data(self) -> dict[str, Any]:
        return {
            "distribution": parse_distribution(self.distribution),
            "provenance": self.provenance.to_domain(),
        }


class MaintenanceTaskCreate(AuditFields):
    name: str
    task_type: MaintenanceTaskType
    trigger: MaintenanceTrigger
    failure_mode_id: UUID | None = None
    interval: TimeValueDto | None = None
    cost: float | None = None
    duration: MaintenanceDurationCreate | None = None

    def to_data(self) -> dict[str, Any]:
        data = self.model_dump(
            exclude={
                "actor_id",
                "source",
                "reason",
                "interval",
                "duration",
            },
            exclude_none=True,
        )
        if self.interval is not None:
            data["interval"] = self.interval.to_domain()
        return data

    def duration_data(self) -> dict[str, Any] | None:
        if self.duration is None:
            return None
        return self.duration.to_data()


class MaintenanceTaskUpdate(AuditFields):
    name: str | None = None
    task_type: MaintenanceTaskType | None = None
    trigger: MaintenanceTrigger | None = None
    failure_mode_id: UUID | None = None
    interval: TimeValueDto | None = None
    cost: float | None = None

    def to_data(self) -> dict[str, Any]:
        data = self.model_dump(
            exclude={"actor_id", "source", "reason", "interval"},
            exclude_unset=True,
        )
        if "interval" in self.model_fields_set and self.interval is not None:
            data["interval"] = self.interval.to_domain()
        elif "interval" in self.model_fields_set:
            data["interval"] = None
        return data


class DiagnosticTaskCreate(AuditFields):
    name: str
    failure_mode_id: UUID
    method: str | None = None
    interval: TimeValueDto
    detection_probability: float = Field(ge=0.0, le=1.0)
    false_positive_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    duration: TimeValueDto | None = None
    cost: float | None = None
    provenance: ProvenanceDto | None = None

    def to_data(self) -> dict[str, Any]:
        data = self.model_dump(
            exclude={
                "actor_id",
                "source",
                "reason",
                "interval",
                "duration",
                "provenance",
            },
            exclude_none=True,
        )
        data["interval"] = self.interval.to_domain()
        if self.duration is not None:
            data["duration"] = self.duration.to_domain()
        if self.provenance is not None:
            data["provenance"] = self.provenance.to_domain()
        return data


class DiagnosticTaskUpdate(AuditFields):
    name: str | None = None
    failure_mode_id: UUID | None = None
    method: str | None = None
    interval: TimeValueDto | None = None
    detection_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    false_positive_probability: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    duration: TimeValueDto | None = None
    cost: float | None = None
    provenance: ProvenanceDto | None = None

    def to_data(self) -> dict[str, Any]:
        data = self.model_dump(
            exclude={
                "actor_id",
                "source",
                "reason",
                "interval",
                "duration",
                "provenance",
            },
            exclude_unset=True,
        )
        if "interval" in self.model_fields_set and self.interval is not None:
            data["interval"] = self.interval.to_domain()
        if "duration" in self.model_fields_set:
            data["duration"] = (
                self.duration.to_domain() if self.duration else None
            )
        if "provenance" in self.model_fields_set and self.provenance:
            data["provenance"] = self.provenance.to_domain()
        return data


class ConnectionCreate(AuditFields):
    source_id: UUID
    target_id: UUID
    connection_type: ConnectionType = ConnectionType.PROCESS
    description: str | None = None

    def to_data(self) -> dict[str, Any]:
        return self.model_dump(
            exclude={"actor_id", "source", "reason"},
            exclude_none=True,
        )


class ResourceCreate(AuditFields):
    name: str
    resource_type: str | None = None
    capacity: int = 1
    cost_per_hour: float | None = None

    def to_data(self) -> dict[str, Any]:
        return self.model_dump(
            exclude={"actor_id", "source", "reason"},
            exclude_none=True,
        )


class ResourceUpdate(AuditFields):
    name: str | None = None
    resource_type: str | None = None
    capacity: int | None = None
    cost_per_hour: float | None = None

    def to_data(self) -> dict[str, Any]:
        return self.model_dump(
            exclude={"actor_id", "source", "reason"},
            exclude_unset=True,
        )


class SparePartCreate(AuditFields):
    name: str
    stock: int = 0
    lead_time: TimeValueDto | None = None
    unit_cost: float | None = None

    def to_data(self) -> dict[str, Any]:
        data = self.model_dump(
            exclude={"actor_id", "source", "reason", "lead_time"},
            exclude_none=True,
        )
        if self.lead_time is not None:
            data["lead_time"] = self.lead_time.to_domain()
        return data


class SparePartUpdate(AuditFields):
    name: str | None = None
    stock: int | None = None
    lead_time: TimeValueDto | None = None
    unit_cost: float | None = None

    def to_data(self) -> dict[str, Any]:
        data = self.model_dump(
            exclude={"actor_id", "source", "reason", "lead_time"},
            exclude_unset=True,
        )
        if "lead_time" in self.model_fields_set:
            data["lead_time"] = (
                self.lead_time.to_domain() if self.lead_time else None
            )
        return data


class ProductionFunctionCreate(AuditFields):
    product: str
    nominal_rate: MassRateDto

    def to_data(self) -> dict[str, Any]:
        return {
            "product": self.product,
            "nominal_rate": self.nominal_rate.to_domain(),
        }


class ProductionFunctionUpdate(AuditFields):
    product: str | None = None
    nominal_rate: MassRateDto | None = None

    def to_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if self.product is not None:
            data["product"] = self.product
        if self.nominal_rate is not None:
            data["nominal_rate"] = self.nominal_rate.to_domain()
        return data


class ProductionImpactCreate(AuditFields):
    equipment_id: UUID
    failure_mode_id: UUID | None = None
    loss_fraction: float = Field(ge=0.0, le=1.0)

    def to_data(self) -> dict[str, Any]:
        return self.model_dump(
            exclude={"actor_id", "source", "reason"},
            exclude_none=True,
        )


class ProductionImpactUpdate(AuditFields):
    equipment_id: UUID | None = None
    failure_mode_id: UUID | None = None
    loss_fraction: float | None = Field(default=None, ge=0.0, le=1.0)

    def to_data(self) -> dict[str, Any]:
        return self.model_dump(
            exclude={"actor_id", "source", "reason"},
            exclude_unset=True,
        )


def json_equipment_list(items: list[Equipment]) -> list[dict[str, Any]]:
    """Serialize equipment entities for JSON responses."""
    return [entity_json(e) for e in items]
