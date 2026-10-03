"""Bidirectional mappers between domain entities and ORM rows."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from app.domain.diagnostics.entities import DiagnosticTask
from app.domain.equipment.entities import ConnectionType
from app.domain.equipment.entities import Criticality
from app.domain.equipment.entities import Equipment
from app.domain.equipment.entities import EquipmentComponent
from app.domain.equipment.entities import EquipmentConnection
from app.domain.equipment.entities import OperatingMode
from app.domain.equipment.entities import StandbyMode
from app.domain.maintenance.entities import MaintenanceDistribution
from app.domain.maintenance.entities import MaintenanceEffect
from app.domain.maintenance.entities import MaintenanceEffectType
from app.domain.maintenance.entities import MaintenanceTask
from app.domain.maintenance.entities import MaintenanceTaskType
from app.domain.maintenance.entities import MaintenanceTrigger
from app.domain.production.entities import ProductionFunction
from app.domain.production.entities import ProductionImpact
from app.domain.provenance import Provenance
from app.domain.reliability.distributions import DistributionSpec
from app.domain.reliability.distributions import parse_distribution
from app.domain.reliability.entities import FailureDistribution
from app.domain.reliability.entities import FailureMode
from app.domain.reliability.entities import ReliabilityStructure
from app.domain.reliability.entities import ReliabilityStructureMember
from app.domain.reliability.entities import StructureType
from app.domain.reliability.pf import PFInterval
from app.domain.resources.entities import Resource
from app.domain.resources.entities import ResourceRequirement
from app.domain.resources.entities import SparePart
from app.domain.resources.entities import SparePartRequirement
from app.domain.system.entities import System
from app.domain.system.entities import SystemVersion
from app.domain.system.entities import VersionStatus
from app.domain.units import MassRate
from app.domain.units import MassUnit
from app.domain.units import TimeUnit
from app.domain.units import TimeValue
from app.infrastructure.db.models import AuditEventRow
from app.infrastructure.db.models import DiagnosticTaskRow
from app.infrastructure.db.models import EquipmentComponentRow
from app.infrastructure.db.models import EquipmentConnectionRow
from app.infrastructure.db.models import EquipmentRow
from app.infrastructure.db.models import FailureDistributionRow
from app.infrastructure.db.models import FailureModeRow
from app.infrastructure.db.models import MaintenanceDistributionRow
from app.infrastructure.db.models import MaintenanceEffectRow
from app.infrastructure.db.models import MaintenanceTaskRow
from app.infrastructure.db.models import ProductionFunctionRow
from app.infrastructure.db.models import ProductionImpactRow
from app.infrastructure.db.models import ReliabilityStructureMemberRow
from app.infrastructure.db.models import ReliabilityStructureRow
from app.infrastructure.db.models import ResourceRequirementRow
from app.infrastructure.db.models import ResourceRow
from app.infrastructure.db.models import SparePartRequirementRow
from app.infrastructure.db.models import SparePartRow
from app.infrastructure.db.models import SystemRow
from app.infrastructure.db.models import SystemVersionRow
from app.infrastructure.db.types_json import DistributionJson
from app.infrastructure.db.types_json import JsonObject
from app.infrastructure.db.types_json import ProvenanceJson


def _time_columns(
    value: TimeValue | None,
) -> tuple[float | None, str | None]:
    if value is None:
        return None, None
    return value.value, value.unit.value


def _time_from_columns(
    value: float | None,
    unit: str | None,
) -> TimeValue | None:
    if value is None or unit is None:
        return None
    return TimeValue(value=value, unit=TimeUnit(unit))


def _pf_columns(
    interval: PFInterval | None,
) -> tuple[float | None, str | None]:
    if interval is None:
        return None, None
    return interval.value, interval.unit.value


def _pf_from_columns(
    value: float | None,
    unit: str | None,
) -> PFInterval | None:
    if value is None or unit is None:
        return None
    return PFInterval(value=value, unit=TimeUnit(unit))


def _mass_rate_columns(
    rate: MassRate,
) -> tuple[float, str, str]:
    return rate.value, rate.mass_unit.value, rate.time_unit.value


def _mass_rate_from_columns(
    value: float,
    mass_unit: str,
    time_unit: str,
) -> MassRate:
    return MassRate(
        value=value,
        mass_unit=MassUnit(mass_unit),
        time_unit=TimeUnit(time_unit),
    )


def _distribution_to_json(spec: DistributionSpec) -> DistributionJson:
    return spec.model_dump(mode="json")


def _distribution_from_json(data: DistributionJson) -> DistributionSpec:
    return cast(DistributionSpec, parse_distribution(data))


def _provenance_to_json(provenance: Provenance) -> ProvenanceJson:
    return provenance.model_dump(mode="json")


def _provenance_from_json(data: ProvenanceJson) -> Provenance:
    return Provenance.model_validate(data)


def _optional_provenance_from_json(
    data: ProvenanceJson | None,
) -> Provenance | None:
    if data is None:
        return None
    return _provenance_from_json(data)


def system_to_row(system: System) -> SystemRow:
    """Map a ``System`` domain entity to an ORM row."""
    return SystemRow(
        id=system.id,
        name=system.name,
        description=system.description,
        created_by=system.created_by,
        created_at=system.created_at,
        updated_at=system.created_at,
    )


def system_from_row(row: SystemRow) -> System:
    """Map a ``SystemRow`` to a domain ``System``."""
    return System(
        id=row.id,
        name=row.name,
        description=row.description,
        created_at=row.created_at,
        created_by=row.created_by,
    )


def apply_system_row(row: SystemRow, system: System) -> None:
    """Copy ``System`` fields onto an existing row."""
    row.name = system.name
    row.description = system.description
    row.created_by = system.created_by


def version_to_row(version: SystemVersion) -> SystemVersionRow:
    """Map a ``SystemVersion`` to an ORM row."""
    return SystemVersionRow(
        id=version.id,
        system_id=version.system_id,
        lineage_id=version.lineage_id,
        version_number=version.version_number,
        status=version.status.value,
        parent_version_id=version.parent_version_id,
        comment=version.comment,
        created_at=version.created_at,
        created_by=version.created_by,
        validated_at=version.validated_at,
        released_at=version.released_at,
        updated_at=version.created_at,
    )


def version_from_row(row: SystemVersionRow) -> SystemVersion:
    """Map a ``SystemVersionRow`` to a domain entity."""
    return SystemVersion(
        id=row.id,
        system_id=row.system_id,
        lineage_id=row.lineage_id,
        version_number=row.version_number,
        status=VersionStatus(row.status),
        parent_version_id=row.parent_version_id,
        comment=row.comment,
        created_at=row.created_at,
        created_by=row.created_by,
        validated_at=row.validated_at,
        released_at=row.released_at,
    )


def apply_version_row(row: SystemVersionRow, version: SystemVersion) -> None:
    """Copy ``SystemVersion`` fields onto an existing row."""
    row.system_id = version.system_id
    row.lineage_id = version.lineage_id
    row.version_number = version.version_number
    row.status = version.status.value
    row.parent_version_id = version.parent_version_id
    row.comment = version.comment
    row.created_by = version.created_by
    row.validated_at = version.validated_at
    row.released_at = version.released_at


def equipment_to_row(equipment: Equipment) -> EquipmentRow:
    """Map ``Equipment`` to an ORM row."""
    return EquipmentRow(
        id=equipment.id,
        version_id=equipment.version_id,
        lineage_id=equipment.lineage_id,
        tag=equipment.tag,
        name=equipment.name,
        description=equipment.description,
        parent_id=equipment.parent_id,
        taxonomy_node_id=equipment.taxonomy_node_id,
        category=equipment.category,
        equipment_class=equipment.equipment_class,
        equipment_type=equipment.equipment_type,
        location=equipment.location,
        quantity=equipment.quantity,
        criticality=equipment.criticality.value,
        operating_mode=equipment.operating_mode.value,
        standby_mode=equipment.standby_mode.value,
        is_repairable=equipment.is_repairable,
    )


def equipment_from_row(row: EquipmentRow) -> Equipment:
    """Map an equipment row to the domain entity."""
    return Equipment(
        id=row.id,
        version_id=row.version_id,
        lineage_id=row.lineage_id,
        tag=row.tag,
        name=row.name,
        description=row.description,
        parent_id=row.parent_id,
        taxonomy_node_id=row.taxonomy_node_id,
        category=row.category,
        equipment_class=row.equipment_class,
        equipment_type=row.equipment_type,
        location=row.location,
        quantity=row.quantity,
        criticality=Criticality(row.criticality),
        operating_mode=OperatingMode(row.operating_mode),
        standby_mode=StandbyMode(row.standby_mode),
        is_repairable=row.is_repairable,
    )


def apply_equipment_row(row: EquipmentRow, equipment: Equipment) -> None:
    """Update an equipment row from a domain entity."""
    row.version_id = equipment.version_id
    row.lineage_id = equipment.lineage_id
    row.tag = equipment.tag
    row.name = equipment.name
    row.description = equipment.description
    row.parent_id = equipment.parent_id
    row.taxonomy_node_id = equipment.taxonomy_node_id
    row.category = equipment.category
    row.equipment_class = equipment.equipment_class
    row.equipment_type = equipment.equipment_type
    row.location = equipment.location
    row.quantity = equipment.quantity
    row.criticality = equipment.criticality.value
    row.operating_mode = equipment.operating_mode.value
    row.standby_mode = equipment.standby_mode.value
    row.is_repairable = equipment.is_repairable


def equipment_component_to_row(
    component: EquipmentComponent,
) -> EquipmentComponentRow:
    """Map ``EquipmentComponent`` to an ORM row."""
    return EquipmentComponentRow(
        id=component.id,
        version_id=component.version_id,
        lineage_id=component.lineage_id,
        equipment_id=component.equipment_id,
        tag=component.tag,
        name=component.name,
        description=component.description,
        quantity=component.quantity,
    )


def equipment_component_from_row(
    row: EquipmentComponentRow,
) -> EquipmentComponent:
    """Map a component row to the domain entity."""
    return EquipmentComponent(
        id=row.id,
        version_id=row.version_id,
        lineage_id=row.lineage_id,
        equipment_id=row.equipment_id,
        tag=row.tag,
        name=row.name,
        description=row.description,
        quantity=row.quantity,
    )


def apply_equipment_component_row(
    row: EquipmentComponentRow,
    component: EquipmentComponent,
) -> None:
    """Update a component row from a domain entity."""
    row.version_id = component.version_id
    row.lineage_id = component.lineage_id
    row.equipment_id = component.equipment_id
    row.tag = component.tag
    row.name = component.name
    row.description = component.description
    row.quantity = component.quantity


def equipment_connection_to_row(
    connection: EquipmentConnection,
) -> EquipmentConnectionRow:
    """Map ``EquipmentConnection`` to an ORM row."""
    return EquipmentConnectionRow(
        id=connection.id,
        version_id=connection.version_id,
        lineage_id=connection.lineage_id,
        source_id=connection.source_id,
        target_id=connection.target_id,
        connection_type=connection.connection_type.value,
        description=connection.description,
    )


def equipment_connection_from_row(
    row: EquipmentConnectionRow,
) -> EquipmentConnection:
    """Map a connection row to the domain entity."""
    return EquipmentConnection(
        id=row.id,
        version_id=row.version_id,
        lineage_id=row.lineage_id,
        source_id=row.source_id,
        target_id=row.target_id,
        connection_type=ConnectionType(row.connection_type),
        description=row.description,
    )


def apply_equipment_connection_row(
    row: EquipmentConnectionRow,
    connection: EquipmentConnection,
) -> None:
    """Update a connection row from a domain entity."""
    row.version_id = connection.version_id
    row.lineage_id = connection.lineage_id
    row.source_id = connection.source_id
    row.target_id = connection.target_id
    row.connection_type = connection.connection_type.value
    row.description = connection.description


def failure_mode_to_row(failure_mode: FailureMode) -> FailureModeRow:
    """Map ``FailureMode`` to an ORM row."""
    pf_value, pf_unit = _pf_columns(failure_mode.pf_interval)
    return FailureModeRow(
        id=failure_mode.id,
        version_id=failure_mode.version_id,
        lineage_id=failure_mode.lineage_id,
        equipment_id=failure_mode.equipment_id,
        component_id=failure_mode.component_id,
        name=failure_mode.name,
        description=failure_mode.description,
        is_detectable=failure_mode.is_detectable,
        pf_interval_value=pf_value,
        pf_interval_unit=pf_unit,
    )


def failure_mode_from_row(row: FailureModeRow) -> FailureMode:
    """Map a failure mode row to the domain entity."""
    return FailureMode(
        id=row.id,
        version_id=row.version_id,
        lineage_id=row.lineage_id,
        equipment_id=row.equipment_id,
        component_id=row.component_id,
        name=row.name,
        description=row.description,
        is_detectable=row.is_detectable,
        pf_interval=_pf_from_columns(
            row.pf_interval_value,
            row.pf_interval_unit,
        ),
    )


def apply_failure_mode_row(
    row: FailureModeRow,
    failure_mode: FailureMode,
) -> None:
    """Update a failure mode row from a domain entity."""
    pf_value, pf_unit = _pf_columns(failure_mode.pf_interval)
    row.version_id = failure_mode.version_id
    row.lineage_id = failure_mode.lineage_id
    row.equipment_id = failure_mode.equipment_id
    row.component_id = failure_mode.component_id
    row.name = failure_mode.name
    row.description = failure_mode.description
    row.is_detectable = failure_mode.is_detectable
    row.pf_interval_value = pf_value
    row.pf_interval_unit = pf_unit


def failure_distribution_to_row(
    distribution: FailureDistribution,
) -> FailureDistributionRow:
    """Map ``FailureDistribution`` to an ORM row."""
    return FailureDistributionRow(
        id=distribution.id,
        version_id=distribution.version_id,
        lineage_id=distribution.lineage_id,
        failure_mode_id=distribution.failure_mode_id,
        distribution=_distribution_to_json(distribution.distribution),
        provenance=_provenance_to_json(distribution.provenance),
    )


def failure_distribution_from_row(
    row: FailureDistributionRow,
) -> FailureDistribution:
    """Map a failure distribution row to the domain entity."""
    return FailureDistribution(
        id=row.id,
        version_id=row.version_id,
        lineage_id=row.lineage_id,
        failure_mode_id=row.failure_mode_id,
        distribution=_distribution_from_json(row.distribution),
        provenance=_provenance_from_json(row.provenance),
    )


def apply_failure_distribution_row(
    row: FailureDistributionRow,
    distribution: FailureDistribution,
) -> None:
    """Update a failure distribution row from a domain entity."""
    row.version_id = distribution.version_id
    row.lineage_id = distribution.lineage_id
    row.failure_mode_id = distribution.failure_mode_id
    row.distribution = _distribution_to_json(distribution.distribution)
    row.provenance = _provenance_to_json(distribution.provenance)


def maintenance_task_to_row(task: MaintenanceTask) -> MaintenanceTaskRow:
    """Map ``MaintenanceTask`` to an ORM row."""
    interval_value, interval_unit = _time_columns(task.interval)
    return MaintenanceTaskRow(
        id=task.id,
        version_id=task.version_id,
        lineage_id=task.lineage_id,
        equipment_id=task.equipment_id,
        failure_mode_id=task.failure_mode_id,
        name=task.name,
        task_type=task.task_type.value,
        trigger=task.trigger.value,
        interval_value=interval_value,
        interval_unit=interval_unit,
        cost=task.cost,
    )


def maintenance_task_from_row(row: MaintenanceTaskRow) -> MaintenanceTask:
    """Map a maintenance task row to the domain entity."""
    return MaintenanceTask(
        id=row.id,
        version_id=row.version_id,
        lineage_id=row.lineage_id,
        equipment_id=row.equipment_id,
        failure_mode_id=row.failure_mode_id,
        name=row.name,
        task_type=MaintenanceTaskType(row.task_type),
        trigger=MaintenanceTrigger(row.trigger),
        interval=_time_from_columns(row.interval_value, row.interval_unit),
        cost=row.cost,
    )


def apply_maintenance_task_row(
    row: MaintenanceTaskRow,
    task: MaintenanceTask,
) -> None:
    """Update a maintenance task row from a domain entity."""
    interval_value, interval_unit = _time_columns(task.interval)
    row.version_id = task.version_id
    row.lineage_id = task.lineage_id
    row.equipment_id = task.equipment_id
    row.failure_mode_id = task.failure_mode_id
    row.name = task.name
    row.task_type = task.task_type.value
    row.trigger = task.trigger.value
    row.interval_value = interval_value
    row.interval_unit = interval_unit
    row.cost = task.cost


def maintenance_distribution_to_row(
    distribution: MaintenanceDistribution,
) -> MaintenanceDistributionRow:
    """Map ``MaintenanceDistribution`` to an ORM row."""
    return MaintenanceDistributionRow(
        id=distribution.id,
        version_id=distribution.version_id,
        lineage_id=distribution.lineage_id,
        maintenance_task_id=distribution.maintenance_task_id,
        distribution=_distribution_to_json(distribution.distribution),
        provenance=_provenance_to_json(distribution.provenance),
    )


def maintenance_distribution_from_row(
    row: MaintenanceDistributionRow,
) -> MaintenanceDistribution:
    """Map a maintenance distribution row to the domain entity."""
    return MaintenanceDistribution(
        id=row.id,
        version_id=row.version_id,
        lineage_id=row.lineage_id,
        maintenance_task_id=row.maintenance_task_id,
        distribution=_distribution_from_json(row.distribution),
        provenance=_provenance_from_json(row.provenance),
    )


def apply_maintenance_distribution_row(
    row: MaintenanceDistributionRow,
    distribution: MaintenanceDistribution,
) -> None:
    """Update a maintenance distribution row from a domain entity."""
    row.version_id = distribution.version_id
    row.lineage_id = distribution.lineage_id
    row.maintenance_task_id = distribution.maintenance_task_id
    row.distribution = _distribution_to_json(distribution.distribution)
    row.provenance = _provenance_to_json(distribution.provenance)


def maintenance_effect_to_row(
    effect: MaintenanceEffect,
) -> MaintenanceEffectRow:
    """Map ``MaintenanceEffect`` to an ORM row."""
    return MaintenanceEffectRow(
        id=effect.id,
        version_id=effect.version_id,
        lineage_id=effect.lineage_id,
        maintenance_task_id=effect.maintenance_task_id,
        effect_type=effect.effect_type.value,
        failure_mode_id=effect.failure_mode_id,
        parameter=effect.parameter,
    )


def maintenance_effect_from_row(
    row: MaintenanceEffectRow,
) -> MaintenanceEffect:
    """Map a maintenance effect row to the domain entity."""
    return MaintenanceEffect(
        id=row.id,
        version_id=row.version_id,
        lineage_id=row.lineage_id,
        maintenance_task_id=row.maintenance_task_id,
        effect_type=MaintenanceEffectType(row.effect_type),
        failure_mode_id=row.failure_mode_id,
        parameter=row.parameter,
    )


def apply_maintenance_effect_row(
    row: MaintenanceEffectRow,
    effect: MaintenanceEffect,
) -> None:
    """Update a maintenance effect row from a domain entity."""
    row.version_id = effect.version_id
    row.lineage_id = effect.lineage_id
    row.maintenance_task_id = effect.maintenance_task_id
    row.effect_type = effect.effect_type.value
    row.failure_mode_id = effect.failure_mode_id
    row.parameter = effect.parameter


def resource_to_row(resource: Resource) -> ResourceRow:
    """Map ``Resource`` to an ORM row."""
    return ResourceRow(
        id=resource.id,
        version_id=resource.version_id,
        lineage_id=resource.lineage_id,
        name=resource.name,
        resource_type=resource.resource_type,
        capacity=resource.capacity,
        cost_per_hour=resource.cost_per_hour,
    )


def resource_from_row(row: ResourceRow) -> Resource:
    """Map a resource row to the domain entity."""
    return Resource(
        id=row.id,
        version_id=row.version_id,
        lineage_id=row.lineage_id,
        name=row.name,
        resource_type=row.resource_type,
        capacity=row.capacity,
        cost_per_hour=row.cost_per_hour,
    )


def apply_resource_row(row: ResourceRow, resource: Resource) -> None:
    """Update a resource row from a domain entity."""
    row.version_id = resource.version_id
    row.lineage_id = resource.lineage_id
    row.name = resource.name
    row.resource_type = resource.resource_type
    row.capacity = resource.capacity
    row.cost_per_hour = resource.cost_per_hour


def spare_part_to_row(spare_part: SparePart) -> SparePartRow:
    """Map ``SparePart`` to an ORM row."""
    lead_value, lead_unit = _time_columns(spare_part.lead_time)
    return SparePartRow(
        id=spare_part.id,
        version_id=spare_part.version_id,
        lineage_id=spare_part.lineage_id,
        name=spare_part.name,
        stock=spare_part.stock,
        lead_time_value=lead_value,
        lead_time_unit=lead_unit,
        unit_cost=spare_part.unit_cost,
    )


def spare_part_from_row(row: SparePartRow) -> SparePart:
    """Map a spare part row to the domain entity."""
    return SparePart(
        id=row.id,
        version_id=row.version_id,
        lineage_id=row.lineage_id,
        name=row.name,
        stock=row.stock,
        lead_time=_time_from_columns(
            row.lead_time_value,
            row.lead_time_unit,
        ),
        unit_cost=row.unit_cost,
    )


def apply_spare_part_row(row: SparePartRow, spare_part: SparePart) -> None:
    """Update a spare part row from a domain entity."""
    lead_value, lead_unit = _time_columns(spare_part.lead_time)
    row.version_id = spare_part.version_id
    row.lineage_id = spare_part.lineage_id
    row.name = spare_part.name
    row.stock = spare_part.stock
    row.lead_time_value = lead_value
    row.lead_time_unit = lead_unit
    row.unit_cost = spare_part.unit_cost


def resource_requirement_to_row(
    requirement: ResourceRequirement,
) -> ResourceRequirementRow:
    """Map ``ResourceRequirement`` to an ORM row."""
    return ResourceRequirementRow(
        id=requirement.id,
        version_id=requirement.version_id,
        lineage_id=requirement.lineage_id,
        maintenance_task_id=requirement.maintenance_task_id,
        resource_id=requirement.resource_id,
        quantity=requirement.quantity,
    )


def resource_requirement_from_row(
    row: ResourceRequirementRow,
) -> ResourceRequirement:
    """Map a resource requirement row to the domain entity."""
    return ResourceRequirement(
        id=row.id,
        version_id=row.version_id,
        lineage_id=row.lineage_id,
        maintenance_task_id=row.maintenance_task_id,
        resource_id=row.resource_id,
        quantity=row.quantity,
    )


def apply_resource_requirement_row(
    row: ResourceRequirementRow,
    requirement: ResourceRequirement,
) -> None:
    """Update a resource requirement row from a domain entity."""
    row.version_id = requirement.version_id
    row.lineage_id = requirement.lineage_id
    row.maintenance_task_id = requirement.maintenance_task_id
    row.resource_id = requirement.resource_id
    row.quantity = requirement.quantity


def spare_part_requirement_to_row(
    requirement: SparePartRequirement,
) -> SparePartRequirementRow:
    """Map ``SparePartRequirement`` to an ORM row."""
    return SparePartRequirementRow(
        id=requirement.id,
        version_id=requirement.version_id,
        lineage_id=requirement.lineage_id,
        maintenance_task_id=requirement.maintenance_task_id,
        spare_part_id=requirement.spare_part_id,
        quantity=requirement.quantity,
    )


def spare_part_requirement_from_row(
    row: SparePartRequirementRow,
) -> SparePartRequirement:
    """Map a spare part requirement row to the domain entity."""
    return SparePartRequirement(
        id=row.id,
        version_id=row.version_id,
        lineage_id=row.lineage_id,
        maintenance_task_id=row.maintenance_task_id,
        spare_part_id=row.spare_part_id,
        quantity=row.quantity,
    )


def apply_spare_part_requirement_row(
    row: SparePartRequirementRow,
    requirement: SparePartRequirement,
) -> None:
    """Update a spare part requirement row from a domain entity."""
    row.version_id = requirement.version_id
    row.lineage_id = requirement.lineage_id
    row.maintenance_task_id = requirement.maintenance_task_id
    row.spare_part_id = requirement.spare_part_id
    row.quantity = requirement.quantity


def diagnostic_task_to_row(task: DiagnosticTask) -> DiagnosticTaskRow:
    """Map ``DiagnosticTask`` to an ORM row."""
    interval_value, interval_unit = _time_columns(task.interval)
    duration_value, duration_unit = _time_columns(task.duration)
    provenance: ProvenanceJson | None = None
    if task.provenance is not None:
        provenance = _provenance_to_json(task.provenance)
    return DiagnosticTaskRow(
        id=task.id,
        version_id=task.version_id,
        lineage_id=task.lineage_id,
        equipment_id=task.equipment_id,
        failure_mode_id=task.failure_mode_id,
        name=task.name,
        method=task.method,
        interval_value=interval_value or 0.0,
        interval_unit=interval_unit or TimeUnit.DAYS.value,
        detection_probability=task.detection_probability,
        false_positive_probability=task.false_positive_probability,
        duration_value=duration_value,
        duration_unit=duration_unit,
        cost=task.cost,
        provenance=provenance,
    )


def diagnostic_task_from_row(row: DiagnosticTaskRow) -> DiagnosticTask:
    """Map a diagnostic task row to the domain entity."""
    return DiagnosticTask(
        id=row.id,
        version_id=row.version_id,
        lineage_id=row.lineage_id,
        equipment_id=row.equipment_id,
        failure_mode_id=row.failure_mode_id,
        name=row.name,
        method=row.method,
        interval=TimeValue(
            value=row.interval_value,
            unit=TimeUnit(row.interval_unit),
        ),
        detection_probability=row.detection_probability,
        false_positive_probability=row.false_positive_probability,
        duration=_time_from_columns(row.duration_value, row.duration_unit),
        cost=row.cost,
        provenance=_optional_provenance_from_json(row.provenance),
    )


def apply_diagnostic_task_row(
    row: DiagnosticTaskRow,
    task: DiagnosticTask,
) -> None:
    """Update a diagnostic task row from a domain entity."""
    interval_value, interval_unit = _time_columns(task.interval)
    duration_value, duration_unit = _time_columns(task.duration)
    provenance: ProvenanceJson | None = None
    if task.provenance is not None:
        provenance = _provenance_to_json(task.provenance)
    row.version_id = task.version_id
    row.lineage_id = task.lineage_id
    row.equipment_id = task.equipment_id
    row.failure_mode_id = task.failure_mode_id
    row.name = task.name
    row.method = task.method
    row.interval_value = interval_value or 0.0
    row.interval_unit = interval_unit or TimeUnit.DAYS.value
    row.detection_probability = task.detection_probability
    row.false_positive_probability = task.false_positive_probability
    row.duration_value = duration_value
    row.duration_unit = duration_unit
    row.cost = task.cost
    row.provenance = provenance


def production_function_to_row(
    function: ProductionFunction,
) -> ProductionFunctionRow:
    """Map ``ProductionFunction`` to an ORM row."""
    rate_value, mass_unit, time_unit = _mass_rate_columns(
        function.nominal_rate,
    )
    return ProductionFunctionRow(
        id=function.id,
        version_id=function.version_id,
        lineage_id=function.lineage_id,
        product=function.product,
        rate_value=rate_value,
        mass_unit=mass_unit,
        time_unit=time_unit,
    )


def production_function_from_row(
    row: ProductionFunctionRow,
) -> ProductionFunction:
    """Map a production function row to the domain entity."""
    return ProductionFunction(
        id=row.id,
        version_id=row.version_id,
        lineage_id=row.lineage_id,
        product=row.product,
        nominal_rate=_mass_rate_from_columns(
            row.rate_value,
            row.mass_unit,
            row.time_unit,
        ),
    )


def apply_production_function_row(
    row: ProductionFunctionRow,
    function: ProductionFunction,
) -> None:
    """Update a production function row from a domain entity."""
    rate_value, mass_unit, time_unit = _mass_rate_columns(
        function.nominal_rate,
    )
    row.version_id = function.version_id
    row.lineage_id = function.lineage_id
    row.product = function.product
    row.rate_value = rate_value
    row.mass_unit = mass_unit
    row.time_unit = time_unit


def production_impact_to_row(impact: ProductionImpact) -> ProductionImpactRow:
    """Map ``ProductionImpact`` to an ORM row."""
    return ProductionImpactRow(
        id=impact.id,
        version_id=impact.version_id,
        lineage_id=impact.lineage_id,
        equipment_id=impact.equipment_id,
        failure_mode_id=impact.failure_mode_id,
        loss_fraction=impact.loss_fraction,
    )


def production_impact_from_row(
    row: ProductionImpactRow,
) -> ProductionImpact:
    """Map a production impact row to the domain entity."""
    return ProductionImpact(
        id=row.id,
        version_id=row.version_id,
        lineage_id=row.lineage_id,
        equipment_id=row.equipment_id,
        failure_mode_id=row.failure_mode_id,
        loss_fraction=row.loss_fraction,
    )


def apply_production_impact_row(
    row: ProductionImpactRow,
    impact: ProductionImpact,
) -> None:
    """Update a production impact row from a domain entity."""
    row.version_id = impact.version_id
    row.lineage_id = impact.lineage_id
    row.equipment_id = impact.equipment_id
    row.failure_mode_id = impact.failure_mode_id
    row.loss_fraction = impact.loss_fraction


def reliability_structure_to_row(
    structure: ReliabilityStructure,
) -> ReliabilityStructureRow:
    """Map ``ReliabilityStructure`` to an ORM row."""
    return ReliabilityStructureRow(
        id=structure.id,
        version_id=structure.version_id,
        lineage_id=structure.lineage_id,
        name=structure.name,
        structure_type=structure.structure_type.value,
        k=structure.k,
        parent_structure_id=structure.parent_structure_id,
    )


def reliability_structure_from_row(
    row: ReliabilityStructureRow,
) -> ReliabilityStructure:
    """Map a reliability structure row to the domain entity."""
    return ReliabilityStructure(
        id=row.id,
        version_id=row.version_id,
        lineage_id=row.lineage_id,
        name=row.name,
        structure_type=StructureType(row.structure_type),
        k=row.k,
        parent_structure_id=row.parent_structure_id,
    )


def apply_reliability_structure_row(
    row: ReliabilityStructureRow,
    structure: ReliabilityStructure,
) -> None:
    """Update a reliability structure row from a domain entity."""
    row.version_id = structure.version_id
    row.lineage_id = structure.lineage_id
    row.name = structure.name
    row.structure_type = structure.structure_type.value
    row.k = structure.k
    row.parent_structure_id = structure.parent_structure_id


def reliability_structure_member_to_row(
    member: ReliabilityStructureMember,
) -> ReliabilityStructureMemberRow:
    """Map ``ReliabilityStructureMember`` to an ORM row."""
    return ReliabilityStructureMemberRow(
        id=member.id,
        version_id=member.version_id,
        lineage_id=member.lineage_id,
        structure_id=member.structure_id,
        equipment_id=member.equipment_id,
        child_structure_id=member.child_structure_id,
        position=member.position,
    )


def reliability_structure_member_from_row(
    row: ReliabilityStructureMemberRow,
) -> ReliabilityStructureMember:
    """Map a structure member row to the domain entity."""
    return ReliabilityStructureMember(
        id=row.id,
        version_id=row.version_id,
        lineage_id=row.lineage_id,
        structure_id=row.structure_id,
        equipment_id=row.equipment_id,
        child_structure_id=row.child_structure_id,
        position=row.position,
    )


def apply_reliability_structure_member_row(
    row: ReliabilityStructureMemberRow,
    member: ReliabilityStructureMember,
) -> None:
    """Update a structure member row from a domain entity."""
    row.version_id = member.version_id
    row.lineage_id = member.lineage_id
    row.structure_id = member.structure_id
    row.equipment_id = member.equipment_id
    row.child_structure_id = member.child_structure_id
    row.position = member.position


def audit_event_to_row(
    *,
    event_id: UUID,
    version_id: UUID | None,
    entity_type: str,
    entity_id: UUID,
    action: str,
    actor_id: UUID | None = None,
    old_value: JsonObject | None = None,
    new_value: JsonObject | None = None,
    source: str | None = None,
    reason: str | None = None,
) -> AuditEventRow:
    """Build an audit event ORM row."""
    return AuditEventRow(
        id=event_id,
        version_id=version_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor_id,
        old_value=old_value,
        new_value=new_value,
        source=source,
        reason=reason,
    )
