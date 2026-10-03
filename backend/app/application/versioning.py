"""System version lifecycle use cases."""

from __future__ import annotations

from uuid import UUID

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
from app.domain.system.content import SystemVersionContent
from app.domain.system.entities import SystemVersion
from app.infrastructure.db.repositories import VersionContentRepository
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


def _map_id(
    mapping: dict[UUID, UUID],
    value: UUID | None,
) -> UUID | None:
    if value is None:
        return None
    return mapping[value]


def _remap_content(
    new_version_id: UUID,
    content: SystemVersionContent,
) -> SystemVersionContent:
    """Clone entities into ``new_version_id`` with fresh IDs."""
    equipment_map: dict[UUID, UUID] = {}
    equipment: list[Equipment] = []
    for src_eq in content.equipment:
        new_eq: Equipment = src_eq.clone_for_version(new_version_id)
        equipment_map[src_eq.id] = new_eq.id
        equipment.append(new_eq)
    for index, src_eq in enumerate(content.equipment):
        parent = src_eq.parent_id
        if parent is not None:
            equipment[index] = equipment[index].model_copy(
                update={"parent_id": equipment_map[parent]},
            )

    component_map: dict[UUID, UUID] = {}
    components: list[EquipmentComponent] = []
    for src_comp in content.components:
        new_comp: EquipmentComponent = src_comp.clone_for_version(
            new_version_id
        )
        component_map[src_comp.id] = new_comp.id
        components.append(
            new_comp.model_copy(
                update={
                    "equipment_id": equipment_map[src_comp.equipment_id],
                },
            ),
        )

    connections: list[EquipmentConnection] = []
    for src_conn in content.connections:
        new_conn: EquipmentConnection = src_conn.clone_for_version(
            new_version_id
        )
        connections.append(
            new_conn.model_copy(
                update={
                    "source_id": equipment_map[src_conn.source_id],
                    "target_id": equipment_map[src_conn.target_id],
                },
            ),
        )

    failure_mode_map: dict[UUID, UUID] = {}
    failure_modes: list[FailureMode] = []
    for src_mode in content.failure_modes:
        new_mode: FailureMode = src_mode.clone_for_version(new_version_id)
        failure_mode_map[src_mode.id] = new_mode.id
        failure_modes.append(
            new_mode.model_copy(
                update={
                    "equipment_id": equipment_map[src_mode.equipment_id],
                    "component_id": _map_id(
                        component_map,
                        src_mode.component_id,
                    ),
                },
            ),
        )

    failure_distributions: list[FailureDistribution] = []
    for src_fdist in content.failure_distributions:
        new_dist: FailureDistribution = src_fdist.clone_for_version(
            new_version_id
        )
        failure_distributions.append(
            new_dist.model_copy(
                update={
                    "failure_mode_id": failure_mode_map[
                        src_fdist.failure_mode_id
                    ],
                },
            ),
        )

    resource_map: dict[UUID, UUID] = {}
    resources: list[Resource] = []
    for src_res in content.resources:
        new_resource: Resource = src_res.clone_for_version(new_version_id)
        resource_map[src_res.id] = new_resource.id
        resources.append(new_resource)

    spare_part_map: dict[UUID, UUID] = {}
    spare_parts: list[SparePart] = []
    for src_part in content.spare_parts:
        new_part: SparePart = src_part.clone_for_version(new_version_id)
        spare_part_map[src_part.id] = new_part.id
        spare_parts.append(new_part)

    maintenance_task_map: dict[UUID, UUID] = {}
    maintenance_tasks: list[MaintenanceTask] = []
    for src_task in content.maintenance_tasks:
        new_task: MaintenanceTask = src_task.clone_for_version(new_version_id)
        maintenance_task_map[src_task.id] = new_task.id
        maintenance_tasks.append(
            new_task.model_copy(
                update={
                    "equipment_id": equipment_map[src_task.equipment_id],
                    "failure_mode_id": _map_id(
                        failure_mode_map,
                        src_task.failure_mode_id,
                    ),
                },
            ),
        )

    maintenance_distributions: list[MaintenanceDistribution] = []
    for src_mdist in content.maintenance_distributions:
        new_mdist: MaintenanceDistribution = src_mdist.clone_for_version(
            new_version_id
        )
        maintenance_distributions.append(
            new_mdist.model_copy(
                update={
                    "maintenance_task_id": maintenance_task_map[
                        src_mdist.maintenance_task_id
                    ],
                },
            ),
        )

    maintenance_effects: list[MaintenanceEffect] = []
    for src_effect in content.maintenance_effects:
        new_effect: MaintenanceEffect = src_effect.clone_for_version(
            new_version_id
        )
        maintenance_effects.append(
            new_effect.model_copy(
                update={
                    "maintenance_task_id": maintenance_task_map[
                        src_effect.maintenance_task_id
                    ],
                    "failure_mode_id": _map_id(
                        failure_mode_map,
                        src_effect.failure_mode_id,
                    ),
                },
            ),
        )

    resource_requirements: list[ResourceRequirement] = []
    for src_res_req in content.resource_requirements:
        new_res_req: ResourceRequirement = src_res_req.clone_for_version(
            new_version_id
        )
        resource_requirements.append(
            new_res_req.model_copy(
                update={
                    "maintenance_task_id": maintenance_task_map[
                        src_res_req.maintenance_task_id
                    ],
                    "resource_id": resource_map[src_res_req.resource_id],
                },
            ),
        )

    spare_part_requirements: list[SparePartRequirement] = []
    for src_part_req in content.spare_part_requirements:
        new_part_req: SparePartRequirement = src_part_req.clone_for_version(
            new_version_id
        )
        spare_part_requirements.append(
            new_part_req.model_copy(
                update={
                    "maintenance_task_id": maintenance_task_map[
                        src_part_req.maintenance_task_id
                    ],
                    "spare_part_id": spare_part_map[
                        src_part_req.spare_part_id
                    ],
                },
            ),
        )

    diagnostic_tasks: list[DiagnosticTask] = []
    for src_diag in content.diagnostic_tasks:
        new_diag: DiagnosticTask = src_diag.clone_for_version(new_version_id)
        diagnostic_tasks.append(
            new_diag.model_copy(
                update={
                    "equipment_id": equipment_map[src_diag.equipment_id],
                    "failure_mode_id": failure_mode_map[
                        src_diag.failure_mode_id
                    ],
                },
            ),
        )

    production_functions: list[ProductionFunction] = []
    for src_fn in content.production_functions:
        new_fn: ProductionFunction = src_fn.clone_for_version(new_version_id)
        production_functions.append(new_fn)

    production_impacts: list[ProductionImpact] = []
    for src_impact in content.production_impacts:
        new_impact: ProductionImpact = src_impact.clone_for_version(
            new_version_id
        )
        production_impacts.append(
            new_impact.model_copy(
                update={
                    "equipment_id": equipment_map[src_impact.equipment_id],
                    "failure_mode_id": _map_id(
                        failure_mode_map,
                        src_impact.failure_mode_id,
                    ),
                },
            ),
        )

    structure_map: dict[UUID, UUID] = {}
    structures: list[ReliabilityStructure] = []
    for src_struct in content.structures:
        new_struct: ReliabilityStructure = src_struct.clone_for_version(
            new_version_id
        )
        structure_map[src_struct.id] = new_struct.id
        structures.append(new_struct)
    for index, src_struct in enumerate(content.structures):
        parent = src_struct.parent_structure_id
        if parent is not None:
            structures[index] = structures[index].model_copy(
                update={
                    "parent_structure_id": structure_map[parent],
                },
            )

    structure_members: list[ReliabilityStructureMember] = []
    for src_member in content.structure_members:
        new_member: ReliabilityStructureMember = src_member.clone_for_version(
            new_version_id
        )
        structure_members.append(
            new_member.model_copy(
                update={
                    "structure_id": structure_map[src_member.structure_id],
                    "equipment_id": _map_id(
                        equipment_map,
                        src_member.equipment_id,
                    ),
                    "child_structure_id": _map_id(
                        structure_map,
                        src_member.child_structure_id,
                    ),
                },
            ),
        )

    return SystemVersionContent(
        equipment=tuple(equipment),
        components=tuple(components),
        connections=tuple(connections),
        failure_modes=tuple(failure_modes),
        failure_distributions=tuple(failure_distributions),
        maintenance_tasks=tuple(maintenance_tasks),
        maintenance_distributions=tuple(maintenance_distributions),
        maintenance_effects=tuple(maintenance_effects),
        resources=tuple(resources),
        spare_parts=tuple(spare_parts),
        resource_requirements=tuple(resource_requirements),
        spare_part_requirements=tuple(spare_part_requirements),
        diagnostic_tasks=tuple(diagnostic_tasks),
        production_functions=tuple(production_functions),
        production_impacts=tuple(production_impacts),
        structures=tuple(structures),
        structure_members=tuple(structure_members),
    )


def _persist_cloned_content(
    content_repo: VersionContentRepository,
    content: SystemVersionContent,
) -> None:
    """Save cloned entities in FK-safe order."""
    for eq in content.equipment:
        content_repo.save_equipment(eq)
    for comp in content.components:
        content_repo.save_component(comp)
    for conn in content.connections:
        content_repo.save_connection(conn)
    for mode in content.failure_modes:
        content_repo.save_failure_mode(mode)
    for dist in content.failure_distributions:
        content_repo.save_failure_distribution(dist)
    for res in content.resources:
        content_repo.save_resource(res)
    for part in content.spare_parts:
        content_repo.save_spare_part(part)
    for task in content.maintenance_tasks:
        content_repo.save_maintenance_task(task)
    for mdist in content.maintenance_distributions:
        content_repo.save_maintenance_distribution(mdist)
    for effect in content.maintenance_effects:
        content_repo.save_maintenance_effect(effect)
    for res_req in content.resource_requirements:
        content_repo.save_resource_requirement(res_req)
    for part_req in content.spare_part_requirements:
        content_repo.save_spare_part_requirement(part_req)
    for diag in content.diagnostic_tasks:
        content_repo.save_diagnostic_task(diag)
    for fn in content.production_functions:
        content_repo.save_production_function(fn)
    for impact in content.production_impacts:
        content_repo.save_production_impact(impact)
    for struct in content.structures:
        content_repo.save_structure(struct)
    for member in content.structure_members:
        content_repo.save_structure_member(member)


def clone_version(
    uow: SqlAlchemyUnitOfWork,
    source_version_id: UUID,
    created_by: UUID | None = None,
) -> SystemVersion:
    """Clone a version into a new DRAFT with remapped entity IDs."""
    source = uow.versions.get(source_version_id)
    new_version = source.create_draft_clone(created_by=created_by)
    content = uow.content.load_content(source_version_id)
    cloned = _remap_content(new_version.id, content)

    uow.versions.add(new_version)
    _persist_cloned_content(uow.content, cloned)

    uow.audit.add_event(
        version_id=new_version.id,
        entity_type="SystemVersion",
        entity_id=new_version.id,
        action="CLONE",
        actor_id=created_by,
        new_value={
            "source_version_id": str(source_version_id),
            "lineage_id": str(new_version.lineage_id),
            "version_number": new_version.version_number,
        },
        source="versioning.clone_version",
    )
    return new_version
