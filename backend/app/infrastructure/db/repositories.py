"""SQLAlchemy repositories for systems and versioned content."""

from __future__ import annotations

from uuid import UUID
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.diagnostics.entities import DiagnosticTask
from app.domain.equipment.entities import Equipment
from app.domain.equipment.entities import EquipmentComponent
from app.domain.equipment.entities import EquipmentConnection
from app.domain.errors import NotFoundError
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
from app.domain.system.content import SystemVersionContent
from app.domain.system.entities import System
from app.domain.system.entities import SystemVersion
from app.infrastructure.db import mappers
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
from app.infrastructure.db.types_json import JsonObject


class SystemRepository:
    """Persistence for ``System`` aggregates."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to a SQLAlchemy session."""
        self._session = session

    def add(self, system: System) -> None:
        """Insert a new system."""
        self._session.add(mappers.system_to_row(system))
        self._session.flush()

    def get(self, system_id: UUID) -> System:
        """Return a system or raise ``NotFoundError``."""
        row = self._session.get(SystemRow, system_id)
        if row is None:
            raise NotFoundError(
                f"system {system_id} not found",
                entity="System",
                entity_id=str(system_id),
            )
        return mappers.system_from_row(row)

    def list(self) -> list[System]:
        """Return all systems ordered by name."""
        stmt = select(SystemRow).order_by(SystemRow.name)
        rows = self._session.scalars(stmt).all()
        return [mappers.system_from_row(row) for row in rows]

    def update(self, system: System) -> None:
        """Update an existing system."""
        row = self._session.get(SystemRow, system.id)
        if row is None:
            raise NotFoundError(
                f"system {system.id} not found",
                entity="System",
                entity_id=str(system.id),
            )
        mappers.apply_system_row(row, system)

    def delete(self, system_id: UUID) -> None:
        """Delete a system."""
        row = self._session.get(SystemRow, system_id)
        if row is None:
            raise NotFoundError(
                f"system {system_id} not found",
                entity="System",
                entity_id=str(system_id),
            )
        self._session.delete(row)


class SystemVersionRepository:
    """Persistence for ``SystemVersion`` rows."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to a SQLAlchemy session."""
        self._session = session

    def add(self, version: SystemVersion) -> None:
        """Insert a new system version."""
        self._session.add(mappers.version_to_row(version))
        self._session.flush()

    def get(self, version_id: UUID) -> SystemVersion:
        """Return a version or raise ``NotFoundError``."""
        row = self._session.get(SystemVersionRow, version_id)
        if row is None:
            raise NotFoundError(
                f"version {version_id} not found",
                entity="SystemVersion",
                entity_id=str(version_id),
            )
        return mappers.version_from_row(row)

    def list_for_system(self, system_id: UUID) -> list[SystemVersion]:
        """Return versions of a system ordered by version number."""
        stmt = (
            select(SystemVersionRow)
            .where(SystemVersionRow.system_id == system_id)
            .order_by(SystemVersionRow.version_number)
        )
        rows = self._session.scalars(stmt).all()
        return [mappers.version_from_row(row) for row in rows]

    def update(self, version: SystemVersion) -> None:
        """Update version metadata (status, timestamps, comment)."""
        row = self._session.get(SystemVersionRow, version.id)
        if row is None:
            raise NotFoundError(
                f"version {version.id} not found",
                entity="SystemVersion",
                entity_id=str(version.id),
            )
        mappers.apply_version_row(row, version)

    @staticmethod
    def ensure_editable(version: SystemVersion) -> None:
        """Raise ``ImmutableVersionError`` if the version is frozen."""
        version.ensure_editable()


class VersionContentRepository:
    """Load and save entities owned by a ``SystemVersion``."""

    def __init__(
        self,
        session: Session,
        versions: SystemVersionRepository,
    ) -> None:
        """Bind repositories sharing one session."""
        self._session = session
        self._versions = versions

    def _ensure_editable(self, version_id: UUID) -> None:
        version = self._versions.get(version_id)
        self._versions.ensure_editable(version)

    def load_content(self, version_id: UUID) -> SystemVersionContent:
        """Load all versioned entities for ``version_id``."""
        self._versions.get(version_id)
        return SystemVersionContent(
            equipment=tuple(self.list_equipment(version_id)),
            components=tuple(self.list_components(version_id)),
            connections=tuple(self.list_connections(version_id)),
            failure_modes=tuple(self.list_failure_modes(version_id)),
            failure_distributions=tuple(
                self.list_failure_distributions(version_id)
            ),
            maintenance_tasks=tuple(self.list_maintenance_tasks(version_id)),
            maintenance_distributions=tuple(
                self.list_maintenance_distributions(version_id)
            ),
            maintenance_effects=tuple(
                self.list_maintenance_effects(version_id)
            ),
            resources=tuple(self.list_resources(version_id)),
            spare_parts=tuple(self.list_spare_parts(version_id)),
            resource_requirements=tuple(
                self.list_resource_requirements(version_id)
            ),
            spare_part_requirements=tuple(
                self.list_spare_part_requirements(version_id)
            ),
            diagnostic_tasks=tuple(self.list_diagnostic_tasks(version_id)),
            production_functions=tuple(
                self.list_production_functions(version_id)
            ),
            production_impacts=tuple(self.list_production_impacts(version_id)),
            structures=tuple(self.list_structures(version_id)),
            structure_members=tuple(self.list_structure_members(version_id)),
        )

    def save_equipment(self, equipment: Equipment) -> None:
        """Insert or update equipment in a version."""
        self._ensure_editable(equipment.version_id)
        row = self._session.get(EquipmentRow, equipment.id)
        if row is None:
            self._session.add(mappers.equipment_to_row(equipment))
            self._session.flush()
        else:
            mappers.apply_equipment_row(row, equipment)

    def save_component(self, component: EquipmentComponent) -> None:
        """Insert or update an equipment component."""
        self._ensure_editable(component.version_id)
        row = self._session.get(EquipmentComponentRow, component.id)
        if row is None:
            self._session.add(mappers.equipment_component_to_row(component))
            self._session.flush()
        else:
            mappers.apply_equipment_component_row(row, component)

    def save_connection(self, connection: EquipmentConnection) -> None:
        """Insert or update an equipment connection."""
        self._ensure_editable(connection.version_id)
        row = self._session.get(EquipmentConnectionRow, connection.id)
        if row is None:
            self._session.add(mappers.equipment_connection_to_row(connection))
            self._session.flush()
        else:
            mappers.apply_equipment_connection_row(row, connection)

    def save_failure_mode(self, failure_mode: FailureMode) -> None:
        """Insert or update a failure mode."""
        self._ensure_editable(failure_mode.version_id)
        row = self._session.get(FailureModeRow, failure_mode.id)
        if row is None:
            self._session.add(mappers.failure_mode_to_row(failure_mode))
            self._session.flush()
        else:
            mappers.apply_failure_mode_row(row, failure_mode)

    def save_failure_distribution(
        self,
        distribution: FailureDistribution,
    ) -> None:
        """Insert or update a failure distribution."""
        self._ensure_editable(distribution.version_id)
        row = self._session.get(FailureDistributionRow, distribution.id)
        if row is None:
            self._session.add(
                mappers.failure_distribution_to_row(distribution)
            )
            self._session.flush()
        else:
            mappers.apply_failure_distribution_row(row, distribution)

    def save_maintenance_task(self, task: MaintenanceTask) -> None:
        """Insert or update a maintenance task."""
        self._ensure_editable(task.version_id)
        row = self._session.get(MaintenanceTaskRow, task.id)
        if row is None:
            self._session.add(mappers.maintenance_task_to_row(task))
            self._session.flush()
        else:
            mappers.apply_maintenance_task_row(row, task)

    def save_maintenance_distribution(
        self,
        distribution: MaintenanceDistribution,
    ) -> None:
        """Insert or update a maintenance duration distribution."""
        self._ensure_editable(distribution.version_id)
        row = self._session.get(MaintenanceDistributionRow, distribution.id)
        if row is None:
            self._session.add(
                mappers.maintenance_distribution_to_row(distribution)
            )
            self._session.flush()
        else:
            mappers.apply_maintenance_distribution_row(row, distribution)

    def save_maintenance_effect(self, effect: MaintenanceEffect) -> None:
        """Insert or update a maintenance effect."""
        self._ensure_editable(effect.version_id)
        row = self._session.get(MaintenanceEffectRow, effect.id)
        if row is None:
            self._session.add(mappers.maintenance_effect_to_row(effect))
            self._session.flush()
        else:
            mappers.apply_maintenance_effect_row(row, effect)

    def save_resource(self, resource: Resource) -> None:
        """Insert or update a maintenance resource."""
        self._ensure_editable(resource.version_id)
        row = self._session.get(ResourceRow, resource.id)
        if row is None:
            self._session.add(mappers.resource_to_row(resource))
            self._session.flush()
        else:
            mappers.apply_resource_row(row, resource)

    def save_spare_part(self, spare_part: SparePart) -> None:
        """Insert or update a spare part."""
        self._ensure_editable(spare_part.version_id)
        row = self._session.get(SparePartRow, spare_part.id)
        if row is None:
            self._session.add(mappers.spare_part_to_row(spare_part))
            self._session.flush()
        else:
            mappers.apply_spare_part_row(row, spare_part)

    def save_resource_requirement(
        self,
        requirement: ResourceRequirement,
    ) -> None:
        """Insert or update a resource requirement."""
        self._ensure_editable(requirement.version_id)
        row = self._session.get(ResourceRequirementRow, requirement.id)
        if row is None:
            self._session.add(mappers.resource_requirement_to_row(requirement))
            self._session.flush()
        else:
            mappers.apply_resource_requirement_row(row, requirement)

    def save_spare_part_requirement(
        self,
        requirement: SparePartRequirement,
    ) -> None:
        """Insert or update a spare part requirement."""
        self._ensure_editable(requirement.version_id)
        row = self._session.get(SparePartRequirementRow, requirement.id)
        if row is None:
            self._session.add(
                mappers.spare_part_requirement_to_row(requirement)
            )
            self._session.flush()
        else:
            mappers.apply_spare_part_requirement_row(row, requirement)

    def save_diagnostic_task(self, task: DiagnosticTask) -> None:
        """Insert or update a diagnostic task."""
        self._ensure_editable(task.version_id)
        row = self._session.get(DiagnosticTaskRow, task.id)
        if row is None:
            self._session.add(mappers.diagnostic_task_to_row(task))
            self._session.flush()
        else:
            mappers.apply_diagnostic_task_row(row, task)

    def save_production_function(
        self,
        function: ProductionFunction,
    ) -> None:
        """Insert or update a production function."""
        self._ensure_editable(function.version_id)
        row = self._session.get(ProductionFunctionRow, function.id)
        if row is None:
            self._session.add(mappers.production_function_to_row(function))
            self._session.flush()
        else:
            mappers.apply_production_function_row(row, function)

    def save_production_impact(self, impact: ProductionImpact) -> None:
        """Insert or update a production impact."""
        self._ensure_editable(impact.version_id)
        row = self._session.get(ProductionImpactRow, impact.id)
        if row is None:
            self._session.add(mappers.production_impact_to_row(impact))
            self._session.flush()
        else:
            mappers.apply_production_impact_row(row, impact)

    def save_structure(self, structure: ReliabilityStructure) -> None:
        """Insert or update a reliability structure."""
        self._ensure_editable(structure.version_id)
        row = self._session.get(ReliabilityStructureRow, structure.id)
        if row is None:
            self._session.add(mappers.reliability_structure_to_row(structure))
            self._session.flush()
        else:
            mappers.apply_reliability_structure_row(row, structure)

    def save_structure_member(
        self,
        member: ReliabilityStructureMember,
    ) -> None:
        """Insert or update a reliability structure member."""
        self._ensure_editable(member.version_id)
        row = self._session.get(ReliabilityStructureMemberRow, member.id)
        if row is None:
            self._session.add(
                mappers.reliability_structure_member_to_row(member)
            )
            self._session.flush()
        else:
            mappers.apply_reliability_structure_member_row(row, member)

    def list_equipment(self, version_id: UUID) -> list[Equipment]:
        """List equipment rows for a version."""
        stmt = select(EquipmentRow).where(
            EquipmentRow.version_id == version_id
        )
        return [
            mappers.equipment_from_row(row)
            for row in self._session.scalars(stmt).all()
        ]

    def list_components(
        self,
        version_id: UUID,
        equipment_id: UUID | None = None,
    ) -> list[EquipmentComponent]:
        """List components, optionally filtered by equipment."""
        stmt = select(EquipmentComponentRow).where(
            EquipmentComponentRow.version_id == version_id
        )
        if equipment_id is not None:
            stmt = stmt.where(
                EquipmentComponentRow.equipment_id == equipment_id
            )
        return [
            mappers.equipment_component_from_row(row)
            for row in self._session.scalars(stmt).all()
        ]

    def list_connections(
        self,
        version_id: UUID,
        equipment_id: UUID | None = None,
    ) -> list[EquipmentConnection]:
        """List connections, optionally touching ``equipment_id``."""
        stmt = select(EquipmentConnectionRow).where(
            EquipmentConnectionRow.version_id == version_id
        )
        if equipment_id is not None:
            stmt = stmt.where(
                (EquipmentConnectionRow.source_id == equipment_id)
                | (EquipmentConnectionRow.target_id == equipment_id)
            )
        return [
            mappers.equipment_connection_from_row(row)
            for row in self._session.scalars(stmt).all()
        ]

    def list_failure_modes(
        self,
        version_id: UUID,
        equipment_id: UUID | None = None,
    ) -> list[FailureMode]:
        """List failure modes, optionally for one equipment item."""
        stmt = select(FailureModeRow).where(
            FailureModeRow.version_id == version_id
        )
        if equipment_id is not None:
            stmt = stmt.where(FailureModeRow.equipment_id == equipment_id)
        return [
            mappers.failure_mode_from_row(row)
            for row in self._session.scalars(stmt).all()
        ]

    def list_failure_distributions(
        self,
        version_id: UUID,
        equipment_id: UUID | None = None,
    ) -> list[FailureDistribution]:
        """List failure distributions for a version."""
        stmt = select(FailureDistributionRow).where(
            FailureDistributionRow.version_id == version_id
        )
        if equipment_id is not None:
            mode_ids = select(FailureModeRow.id).where(
                FailureModeRow.version_id == version_id,
                FailureModeRow.equipment_id == equipment_id,
            )
            stmt = stmt.where(
                FailureDistributionRow.failure_mode_id.in_(mode_ids)
            )
        return [
            mappers.failure_distribution_from_row(row)
            for row in self._session.scalars(stmt).all()
        ]

    def list_maintenance_tasks(
        self,
        version_id: UUID,
        equipment_id: UUID | None = None,
    ) -> list[MaintenanceTask]:
        """List maintenance tasks, optionally for one equipment item."""
        stmt = select(MaintenanceTaskRow).where(
            MaintenanceTaskRow.version_id == version_id
        )
        if equipment_id is not None:
            stmt = stmt.where(MaintenanceTaskRow.equipment_id == equipment_id)
        return [
            mappers.maintenance_task_from_row(row)
            for row in self._session.scalars(stmt).all()
        ]

    def list_maintenance_distributions(
        self,
        version_id: UUID,
        equipment_id: UUID | None = None,
    ) -> list[MaintenanceDistribution]:
        """List maintenance duration distributions."""
        stmt = select(MaintenanceDistributionRow).where(
            MaintenanceDistributionRow.version_id == version_id
        )
        if equipment_id is not None:
            task_ids = select(MaintenanceTaskRow.id).where(
                MaintenanceTaskRow.version_id == version_id,
                MaintenanceTaskRow.equipment_id == equipment_id,
            )
            stmt = stmt.where(
                MaintenanceDistributionRow.maintenance_task_id.in_(task_ids)
            )
        return [
            mappers.maintenance_distribution_from_row(row)
            for row in self._session.scalars(stmt).all()
        ]

    def list_maintenance_effects(
        self,
        version_id: UUID,
        equipment_id: UUID | None = None,
    ) -> list[MaintenanceEffect]:
        """List maintenance effects."""
        stmt = select(MaintenanceEffectRow).where(
            MaintenanceEffectRow.version_id == version_id
        )
        if equipment_id is not None:
            task_ids = select(MaintenanceTaskRow.id).where(
                MaintenanceTaskRow.version_id == version_id,
                MaintenanceTaskRow.equipment_id == equipment_id,
            )
            stmt = stmt.where(
                MaintenanceEffectRow.maintenance_task_id.in_(task_ids)
            )
        return [
            mappers.maintenance_effect_from_row(row)
            for row in self._session.scalars(stmt).all()
        ]

    def list_resources(self, version_id: UUID) -> list[Resource]:
        """List resources for a version."""
        stmt = select(ResourceRow).where(ResourceRow.version_id == version_id)
        return [
            mappers.resource_from_row(row)
            for row in self._session.scalars(stmt).all()
        ]

    def list_spare_parts(self, version_id: UUID) -> list[SparePart]:
        """List spare parts for a version."""
        stmt = select(SparePartRow).where(
            SparePartRow.version_id == version_id
        )
        return [
            mappers.spare_part_from_row(row)
            for row in self._session.scalars(stmt).all()
        ]

    def list_resource_requirements(
        self,
        version_id: UUID,
        equipment_id: UUID | None = None,
    ) -> list[ResourceRequirement]:
        """List resource requirements."""
        stmt = select(ResourceRequirementRow).where(
            ResourceRequirementRow.version_id == version_id
        )
        if equipment_id is not None:
            task_ids = select(MaintenanceTaskRow.id).where(
                MaintenanceTaskRow.version_id == version_id,
                MaintenanceTaskRow.equipment_id == equipment_id,
            )
            stmt = stmt.where(
                ResourceRequirementRow.maintenance_task_id.in_(task_ids)
            )
        return [
            mappers.resource_requirement_from_row(row)
            for row in self._session.scalars(stmt).all()
        ]

    def list_spare_part_requirements(
        self,
        version_id: UUID,
        equipment_id: UUID | None = None,
    ) -> list[SparePartRequirement]:
        """List spare part requirements."""
        stmt = select(SparePartRequirementRow).where(
            SparePartRequirementRow.version_id == version_id
        )
        if equipment_id is not None:
            task_ids = select(MaintenanceTaskRow.id).where(
                MaintenanceTaskRow.version_id == version_id,
                MaintenanceTaskRow.equipment_id == equipment_id,
            )
            stmt = stmt.where(
                SparePartRequirementRow.maintenance_task_id.in_(task_ids)
            )
        return [
            mappers.spare_part_requirement_from_row(row)
            for row in self._session.scalars(stmt).all()
        ]

    def list_diagnostic_tasks(
        self,
        version_id: UUID,
        equipment_id: UUID | None = None,
    ) -> list[DiagnosticTask]:
        """List diagnostic tasks."""
        stmt = select(DiagnosticTaskRow).where(
            DiagnosticTaskRow.version_id == version_id
        )
        if equipment_id is not None:
            stmt = stmt.where(DiagnosticTaskRow.equipment_id == equipment_id)
        return [
            mappers.diagnostic_task_from_row(row)
            for row in self._session.scalars(stmt).all()
        ]

    def list_production_functions(
        self,
        version_id: UUID,
    ) -> list[ProductionFunction]:
        """List production functions for a version."""
        stmt = select(ProductionFunctionRow).where(
            ProductionFunctionRow.version_id == version_id
        )
        return [
            mappers.production_function_from_row(row)
            for row in self._session.scalars(stmt).all()
        ]

    def list_production_impacts(
        self,
        version_id: UUID,
        equipment_id: UUID | None = None,
    ) -> list[ProductionImpact]:
        """List production impacts."""
        stmt = select(ProductionImpactRow).where(
            ProductionImpactRow.version_id == version_id
        )
        if equipment_id is not None:
            stmt = stmt.where(ProductionImpactRow.equipment_id == equipment_id)
        return [
            mappers.production_impact_from_row(row)
            for row in self._session.scalars(stmt).all()
        ]

    def list_structures(
        self,
        version_id: UUID,
    ) -> list[ReliabilityStructure]:
        """List reliability structures for a version."""
        stmt = select(ReliabilityStructureRow).where(
            ReliabilityStructureRow.version_id == version_id
        )
        return [
            mappers.reliability_structure_from_row(row)
            for row in self._session.scalars(stmt).all()
        ]

    def list_structure_members(
        self,
        version_id: UUID,
        equipment_id: UUID | None = None,
    ) -> list[ReliabilityStructureMember]:
        """List structure members."""
        stmt = select(ReliabilityStructureMemberRow).where(
            ReliabilityStructureMemberRow.version_id == version_id
        )
        if equipment_id is not None:
            stmt = stmt.where(
                ReliabilityStructureMemberRow.equipment_id == equipment_id
            )
        return [
            mappers.reliability_structure_member_from_row(row)
            for row in self._session.scalars(stmt).all()
        ]

    def get_equipment(self, equipment_id: UUID) -> Equipment:
        """Return equipment or raise ``NotFoundError``."""
        row = self._session.get(EquipmentRow, equipment_id)
        if row is None:
            raise NotFoundError(
                f"equipment {equipment_id} not found",
                entity="Equipment",
                entity_id=str(equipment_id),
            )
        return mappers.equipment_from_row(row)

    def delete_equipment(self, equipment_id: UUID) -> Equipment:
        """Delete equipment after ensuring the version is editable."""
        row = self._session.get(EquipmentRow, equipment_id)
        if row is None:
            raise NotFoundError(
                f"equipment {equipment_id} not found",
                entity="Equipment",
                entity_id=str(equipment_id),
            )
        self._ensure_editable(row.version_id)
        entity = mappers.equipment_from_row(row)
        self._session.delete(row)
        return entity

    def get_failure_mode(self, failure_mode_id: UUID) -> FailureMode:
        """Return a failure mode or raise ``NotFoundError``."""
        row = self._session.get(FailureModeRow, failure_mode_id)
        if row is None:
            raise NotFoundError(
                f"failure mode {failure_mode_id} not found",
                entity="FailureMode",
                entity_id=str(failure_mode_id),
            )
        return mappers.failure_mode_from_row(row)

    def delete_failure_mode(self, failure_mode_id: UUID) -> FailureMode:
        """Delete a failure mode after ensuring the version is editable."""
        row = self._session.get(FailureModeRow, failure_mode_id)
        if row is None:
            raise NotFoundError(
                f"failure mode {failure_mode_id} not found",
                entity="FailureMode",
                entity_id=str(failure_mode_id),
            )
        self._ensure_editable(row.version_id)
        entity = mappers.failure_mode_from_row(row)
        self._session.delete(row)
        return entity

    def get_maintenance_task(self, task_id: UUID) -> MaintenanceTask:
        """Return a maintenance task or raise ``NotFoundError``."""
        row = self._session.get(MaintenanceTaskRow, task_id)
        if row is None:
            raise NotFoundError(
                f"maintenance task {task_id} not found",
                entity="MaintenanceTask",
                entity_id=str(task_id),
            )
        return mappers.maintenance_task_from_row(row)

    def delete_maintenance_task(self, task_id: UUID) -> MaintenanceTask:
        """Delete a maintenance task after ensuring editability."""
        row = self._session.get(MaintenanceTaskRow, task_id)
        if row is None:
            raise NotFoundError(
                f"maintenance task {task_id} not found",
                entity="MaintenanceTask",
                entity_id=str(task_id),
            )
        self._ensure_editable(row.version_id)
        entity = mappers.maintenance_task_from_row(row)
        self._session.delete(row)
        return entity

    def get_diagnostic_task(self, task_id: UUID) -> DiagnosticTask:
        """Return a diagnostic task or raise ``NotFoundError``."""
        row = self._session.get(DiagnosticTaskRow, task_id)
        if row is None:
            raise NotFoundError(
                f"diagnostic task {task_id} not found",
                entity="DiagnosticTask",
                entity_id=str(task_id),
            )
        return mappers.diagnostic_task_from_row(row)

    def delete_diagnostic_task(self, task_id: UUID) -> DiagnosticTask:
        """Delete a diagnostic task after ensuring editability."""
        row = self._session.get(DiagnosticTaskRow, task_id)
        if row is None:
            raise NotFoundError(
                f"diagnostic task {task_id} not found",
                entity="DiagnosticTask",
                entity_id=str(task_id),
            )
        self._ensure_editable(row.version_id)
        entity = mappers.diagnostic_task_from_row(row)
        self._session.delete(row)
        return entity

    def get_connection(self, connection_id: UUID) -> EquipmentConnection:
        """Return a connection or raise ``NotFoundError``."""
        row = self._session.get(EquipmentConnectionRow, connection_id)
        if row is None:
            raise NotFoundError(
                f"connection {connection_id} not found",
                entity="EquipmentConnection",
                entity_id=str(connection_id),
            )
        return mappers.equipment_connection_from_row(row)

    def delete_connection(self, connection_id: UUID) -> EquipmentConnection:
        """Delete a connection after ensuring editability."""
        row = self._session.get(EquipmentConnectionRow, connection_id)
        if row is None:
            raise NotFoundError(
                f"connection {connection_id} not found",
                entity="EquipmentConnection",
                entity_id=str(connection_id),
            )
        self._ensure_editable(row.version_id)
        entity = mappers.equipment_connection_from_row(row)
        self._session.delete(row)
        return entity

    def get_resource(self, resource_id: UUID) -> Resource:
        """Return a resource or raise ``NotFoundError``."""
        row = self._session.get(ResourceRow, resource_id)
        if row is None:
            raise NotFoundError(
                f"resource {resource_id} not found",
                entity="Resource",
                entity_id=str(resource_id),
            )
        return mappers.resource_from_row(row)

    def delete_resource(self, resource_id: UUID) -> Resource:
        """Delete a resource after ensuring editability."""
        row = self._session.get(ResourceRow, resource_id)
        if row is None:
            raise NotFoundError(
                f"resource {resource_id} not found",
                entity="Resource",
                entity_id=str(resource_id),
            )
        self._ensure_editable(row.version_id)
        entity = mappers.resource_from_row(row)
        self._session.delete(row)
        return entity

    def get_spare_part(self, spare_part_id: UUID) -> SparePart:
        """Return a spare part or raise ``NotFoundError``."""
        row = self._session.get(SparePartRow, spare_part_id)
        if row is None:
            raise NotFoundError(
                f"spare part {spare_part_id} not found",
                entity="SparePart",
                entity_id=str(spare_part_id),
            )
        return mappers.spare_part_from_row(row)

    def delete_spare_part(self, spare_part_id: UUID) -> SparePart:
        """Delete a spare part after ensuring editability."""
        row = self._session.get(SparePartRow, spare_part_id)
        if row is None:
            raise NotFoundError(
                f"spare part {spare_part_id} not found",
                entity="SparePart",
                entity_id=str(spare_part_id),
            )
        self._ensure_editable(row.version_id)
        entity = mappers.spare_part_from_row(row)
        self._session.delete(row)
        return entity

    def get_production_function(
        self,
        function_id: UUID,
    ) -> ProductionFunction:
        """Return a production function or raise ``NotFoundError``."""
        row = self._session.get(ProductionFunctionRow, function_id)
        if row is None:
            raise NotFoundError(
                f"production function {function_id} not found",
                entity="ProductionFunction",
                entity_id=str(function_id),
            )
        return mappers.production_function_from_row(row)

    def delete_production_function(
        self,
        function_id: UUID,
    ) -> ProductionFunction:
        """Delete a production function after ensuring editability."""
        row = self._session.get(ProductionFunctionRow, function_id)
        if row is None:
            raise NotFoundError(
                f"production function {function_id} not found",
                entity="ProductionFunction",
                entity_id=str(function_id),
            )
        self._ensure_editable(row.version_id)
        entity = mappers.production_function_from_row(row)
        self._session.delete(row)
        return entity

    def get_production_impact(self, impact_id: UUID) -> ProductionImpact:
        """Return a production impact or raise ``NotFoundError``."""
        row = self._session.get(ProductionImpactRow, impact_id)
        if row is None:
            raise NotFoundError(
                f"production impact {impact_id} not found",
                entity="ProductionImpact",
                entity_id=str(impact_id),
            )
        return mappers.production_impact_from_row(row)

    def delete_production_impact(self, impact_id: UUID) -> ProductionImpact:
        """Delete a production impact after ensuring editability."""
        row = self._session.get(ProductionImpactRow, impact_id)
        if row is None:
            raise NotFoundError(
                f"production impact {impact_id} not found",
                entity="ProductionImpact",
                entity_id=str(impact_id),
            )
        self._ensure_editable(row.version_id)
        entity = mappers.production_impact_from_row(row)
        self._session.delete(row)
        return entity


class AuditRepository:
    """Append-only audit trail."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to a SQLAlchemy session."""
        self._session = session

    def add_event(
        self,
        *,
        version_id: UUID | None,
        entity_type: str,
        entity_id: UUID,
        action: str,
        actor_id: UUID | None = None,
        old_value: JsonObject | None = None,
        new_value: JsonObject | None = None,
        source: str | None = None,
        reason: str | None = None,
    ) -> None:
        """Record an audit event."""
        row = mappers.audit_event_to_row(
            event_id=uuid4(),
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
        self._session.add(row)
        self._session.flush()
