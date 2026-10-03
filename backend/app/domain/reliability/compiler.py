"""Compile ``SystemVersionContent`` into a ``CompiledModel``."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from app.domain.errors import ModelGenerationError
from app.domain.maintenance.entities import MaintenanceEffect
from app.domain.maintenance.entities import MaintenanceEffectType
from app.domain.maintenance.entities import MaintenanceTask
from app.domain.reliability.compiled import CompiledConnection
from app.domain.reliability.compiled import CompiledDiagnosticTask
from app.domain.reliability.compiled import CompiledEquipment
from app.domain.reliability.compiled import CompiledFailureMode
from app.domain.reliability.compiled import CompiledMaintenanceTask
from app.domain.reliability.compiled import CompiledModel
from app.domain.reliability.compiled import CompiledProduction
from app.domain.reliability.compiled import CompiledProductionImpact
from app.domain.reliability.compiled import CompiledResource
from app.domain.reliability.compiled import CompiledResourceReq
from app.domain.reliability.compiled import CompiledSparePart
from app.domain.reliability.compiled import CompiledSpareReq
from app.domain.reliability.compiled import CompiledStructure
from app.domain.reliability.compiled import CompiledStructureMember
from app.domain.reliability.distributions import DistributionSpec
from app.domain.reliability.model_validation import validate_for_compile
from app.domain.system.content import SystemVersionContent


class ReliabilityCompiler:
    """Build a deterministic compiled model from domain content."""

    def compile(
        self,
        version_id: UUID,
        content: SystemVersionContent,
        *,
        strict: bool = True,
    ) -> CompiledModel:
        """Compile content; raise if validation fails when ``strict``."""
        report = validate_for_compile(content)
        if strict:
            report.raise_if_invalid()
        elif not report.is_valid:
            raise ModelGenerationError(
                "cannot compile invalid model",
                entity="SystemVersion",
                entity_id=str(version_id),
            )

        dist_by_mode = {
            d.failure_mode_id: cast(
                DistributionSpec,
                d.distribution.to_minutes(),
            )
            for d in content.failure_distributions
        }
        dur_by_task = {
            d.maintenance_task_id: cast(
                DistributionSpec,
                d.distribution.to_minutes(),
            )
            for d in content.maintenance_distributions
        }
        effect_by_task = {
            e.maintenance_task_id: e for e in content.maintenance_effects
        }
        res_req = _group_resource_reqs(content)
        spare_req = _group_spare_reqs(content)
        members_by_struct = _group_members(content)

        equipment = tuple(
            sorted(
                (
                    CompiledEquipment(
                        id=e.id,
                        lineage_id=e.lineage_id,
                        tag=e.tag,
                        name=e.name,
                        parent_id=e.parent_id,
                        criticality=e.criticality,
                        standby_mode=e.standby_mode,
                        is_repairable=e.is_repairable,
                        quantity=e.quantity,
                    )
                    for e in content.equipment
                ),
                key=lambda x: (x.tag, str(x.id)),
            )
        )
        failure_modes = tuple(
            sorted(
                (
                    CompiledFailureMode(
                        id=m.id,
                        lineage_id=m.lineage_id,
                        equipment_id=m.equipment_id,
                        component_id=m.component_id,
                        name=m.name,
                        is_detectable=m.is_detectable,
                        pf_interval_minutes=(
                            m.pf_interval.to_minutes()
                            if m.pf_interval is not None
                            else None
                        ),
                        distribution=dist_by_mode[m.id],
                    )
                    for m in content.failure_modes
                    if m.id in dist_by_mode
                ),
                key=lambda x: (str(x.equipment_id), x.name, str(x.id)),
            )
        )
        maintenance = tuple(
            sorted(
                (
                    _compile_task(
                        task,
                        dur_by_task[task.id],
                        effect_by_task.get(task.id),
                        res_req.get(task.id, ()),
                        spare_req.get(task.id, ()),
                    )
                    for task in content.maintenance_tasks
                    if task.id in dur_by_task
                ),
                key=lambda x: (str(x.equipment_id), x.name, str(x.id)),
            )
        )
        diagnostics = tuple(
            sorted(
                (
                    CompiledDiagnosticTask(
                        id=d.id,
                        lineage_id=d.lineage_id,
                        equipment_id=d.equipment_id,
                        failure_mode_id=d.failure_mode_id,
                        name=d.name,
                        interval_minutes=d.interval.to_minutes(),
                        detection_probability=d.detection_probability,
                        false_positive_probability=(
                            d.false_positive_probability
                        ),
                        duration_minutes=(
                            d.duration.to_minutes()
                            if d.duration is not None
                            else 0.0
                        ),
                        cost=d.cost,
                    )
                    for d in content.diagnostic_tasks
                ),
                key=lambda x: (str(x.equipment_id), x.name, str(x.id)),
            )
        )
        resources = tuple(
            sorted(
                (
                    CompiledResource(
                        id=r.id,
                        lineage_id=r.lineage_id,
                        name=r.name,
                        capacity=r.capacity,
                        cost_per_hour=r.cost_per_hour,
                    )
                    for r in content.resources
                ),
                key=lambda x: (x.name, str(x.id)),
            )
        )
        spares = tuple(
            sorted(
                (
                    CompiledSparePart(
                        id=s.id,
                        lineage_id=s.lineage_id,
                        name=s.name,
                        stock=s.stock,
                        lead_time_minutes=(
                            s.lead_time.to_minutes()
                            if s.lead_time is not None
                            else None
                        ),
                        unit_cost=s.unit_cost,
                    )
                    for s in content.spare_parts
                ),
                key=lambda x: (x.name, str(x.id)),
            )
        )
        production = _compile_production(content)
        structures = tuple(
            sorted(
                (
                    CompiledStructure(
                        id=s.id,
                        lineage_id=s.lineage_id,
                        name=s.name,
                        structure_type=s.structure_type,
                        k=s.k,
                        parent_structure_id=s.parent_structure_id,
                        members=members_by_struct.get(s.id, ()),
                    )
                    for s in content.structures
                ),
                key=lambda x: (x.name, str(x.id)),
            )
        )
        connections = tuple(
            sorted(
                (
                    CompiledConnection(
                        id=c.id,
                        source_id=c.source_id,
                        target_id=c.target_id,
                        connection_type=str(c.connection_type),
                    )
                    for c in content.connections
                ),
                key=lambda x: (
                    str(x.source_id),
                    str(x.target_id),
                    x.connection_type,
                ),
            )
        )
        return CompiledModel(
            version_id=version_id,
            equipment=equipment,
            failure_modes=failure_modes,
            maintenance_tasks=maintenance,
            diagnostic_tasks=diagnostics,
            resources=resources,
            spare_parts=spares,
            production=production,
            structures=structures,
            connections=connections,
        )


def _compile_task(
    task: MaintenanceTask,
    duration: DistributionSpec,
    effect: MaintenanceEffect | None,
    resources: tuple[CompiledResourceReq, ...],
    spares: tuple[CompiledSpareReq, ...],
) -> CompiledMaintenanceTask:
    effect_type = MaintenanceEffectType.RESTORE_AS_NEW
    effect_parameter = None
    effect_fm = None
    if effect is not None:
        effect_type = effect.effect_type
        effect_parameter = effect.parameter
        effect_fm = effect.failure_mode_id
    return CompiledMaintenanceTask(
        id=task.id,
        lineage_id=task.lineage_id,
        equipment_id=task.equipment_id,
        failure_mode_id=task.failure_mode_id,
        name=task.name,
        task_type=task.task_type,
        trigger=task.trigger,
        interval_minutes=(
            task.interval.to_minutes() if task.interval is not None else None
        ),
        duration=duration,
        effect_type=effect_type,
        effect_parameter=effect_parameter,
        effect_failure_mode_id=effect_fm,
        resource_requirements=resources,
        spare_requirements=spares,
        cost=task.cost,
    )


def _group_resource_reqs(
    content: SystemVersionContent,
) -> dict[UUID, tuple[CompiledResourceReq, ...]]:
    groups: dict[UUID, list[CompiledResourceReq]] = {}
    for req in content.resource_requirements:
        groups.setdefault(req.maintenance_task_id, []).append(
            CompiledResourceReq(
                resource_id=req.resource_id,
                quantity=req.quantity,
            )
        )
    return {
        key: tuple(sorted(items, key=lambda r: str(r.resource_id)))
        for key, items in groups.items()
    }


def _group_spare_reqs(
    content: SystemVersionContent,
) -> dict[UUID, tuple[CompiledSpareReq, ...]]:
    groups: dict[UUID, list[CompiledSpareReq]] = {}
    for req in content.spare_part_requirements:
        groups.setdefault(req.maintenance_task_id, []).append(
            CompiledSpareReq(
                spare_part_id=req.spare_part_id,
                quantity=req.quantity,
            )
        )
    return {
        key: tuple(sorted(items, key=lambda r: str(r.spare_part_id)))
        for key, items in groups.items()
    }


def _group_members(
    content: SystemVersionContent,
) -> dict[UUID, tuple[CompiledStructureMember, ...]]:
    groups: dict[UUID, list[CompiledStructureMember]] = {}
    for member in content.structure_members:
        groups.setdefault(member.structure_id, []).append(
            CompiledStructureMember(
                equipment_id=member.equipment_id,
                child_structure_id=member.child_structure_id,
                position=member.position,
            )
        )
    return {
        key: tuple(sorted(items, key=lambda m: (m.position, str(m))))
        for key, items in groups.items()
    }


def _compile_production(
    content: SystemVersionContent,
) -> CompiledProduction | None:
    if not content.production_functions and not content.production_impacts:
        return None
    pf = (
        content.production_functions[0]
        if content.production_functions
        else None
    )
    impacts = tuple(
        sorted(
            (
                CompiledProductionImpact(
                    equipment_id=i.equipment_id,
                    failure_mode_id=i.failure_mode_id,
                    loss_fraction=i.loss_fraction,
                )
                for i in content.production_impacts
            ),
            key=lambda x: (str(x.equipment_id), str(x.failure_mode_id)),
        )
    )
    if pf is None:
        return CompiledProduction(
            nominal_rate=1.0,
            unit="kg/min",
            impacts=impacts,
        )
    return CompiledProduction(
        nominal_rate=pf.nominal_rate.to_kg_per_minute(),
        unit="kg/min",
        impacts=impacts,
    )
