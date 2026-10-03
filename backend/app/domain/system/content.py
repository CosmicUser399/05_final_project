"""Container with all entities of one system version."""

from dataclasses import dataclass

from app.domain.diagnostics.entities import DiagnosticTask
from app.domain.equipment.entities import Equipment
from app.domain.equipment.entities import EquipmentComponent
from app.domain.equipment.entities import EquipmentConnection
from app.domain.maintenance.entities import MaintenanceDistribution
from app.domain.maintenance.entities import MaintenanceEffect
from app.domain.maintenance.entities import MaintenanceTask
from app.domain.production.entities import ProductionFunction
from app.domain.production.entities import ProductionImpact
from app.domain.reliability.entities import FailureDistribution
from app.domain.reliability.entities import FailureMode
from app.domain.reliability.entities import ReliabilityStructure
from app.domain.reliability.entities import ReliabilityStructureMember
from app.domain.resources.entities import Resource
from app.domain.resources.entities import ResourceRequirement
from app.domain.resources.entities import SparePart
from app.domain.resources.entities import SparePartRequirement


@dataclass(frozen=True)
class SystemVersionContent:
    """Read-only view of everything inside a ``SystemVersion``."""

    equipment: tuple[Equipment, ...] = ()
    components: tuple[EquipmentComponent, ...] = ()
    connections: tuple[EquipmentConnection, ...] = ()
    failure_modes: tuple[FailureMode, ...] = ()
    failure_distributions: tuple[FailureDistribution, ...] = ()
    maintenance_tasks: tuple[MaintenanceTask, ...] = ()
    maintenance_distributions: tuple[MaintenanceDistribution, ...] = ()
    maintenance_effects: tuple[MaintenanceEffect, ...] = ()
    resources: tuple[Resource, ...] = ()
    spare_parts: tuple[SparePart, ...] = ()
    resource_requirements: tuple[ResourceRequirement, ...] = ()
    spare_part_requirements: tuple[SparePartRequirement, ...] = ()
    diagnostic_tasks: tuple[DiagnosticTask, ...] = ()
    production_functions: tuple[ProductionFunction, ...] = ()
    production_impacts: tuple[ProductionImpact, ...] = ()
    structures: tuple[ReliabilityStructure, ...] = ()
    structure_members: tuple[ReliabilityStructureMember, ...] = ()
