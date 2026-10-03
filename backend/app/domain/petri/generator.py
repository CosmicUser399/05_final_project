"""Deterministic Petri model generation from ``CompiledModel``."""

from __future__ import annotations

from uuid import UUID

from app.domain.maintenance.entities import MaintenanceTaskType
from app.domain.petri.entities import PetriArc
from app.domain.petri.entities import PetriElementKind
from app.domain.petri.entities import PetriModel
from app.domain.petri.entities import PetriPlace
from app.domain.petri.entities import PetriSubnet
from app.domain.petri.entities import PetriTransition
from app.domain.petri.entities import PlaceRole
from app.domain.petri.entities import SourceMapping
from app.domain.petri.entities import TransitionRole
from app.domain.reliability.compiled import CompiledFailureMode
from app.domain.reliability.compiled import CompiledMaintenanceTask
from app.domain.reliability.compiled import CompiledModel


class _IdFactory:
    """Assign opaque place/transition/arc ids in stable order."""

    def __init__(self) -> None:
        self._places = 0
        self._transitions = 0
        self._arcs = 0
        self.id_map: dict[str, SourceMapping] = {}

    def place(
        self,
        role: PlaceRole,
        *,
        subnet_key: str,
        source_entity_type: str | None = None,
        source_entity_id: str | None = None,
        equipment_id: UUID | None = None,
        failure_mode_id: UUID | None = None,
        initial: int = 0,
        capacity: int | None = None,
    ) -> PetriPlace:
        self._places += 1
        opaque = f"p{self._places:04d}"
        self.id_map[opaque] = SourceMapping(
            kind=PetriElementKind.PLACE,
            role=str(role),
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
            equipment_id=None if equipment_id is None else str(equipment_id),
            failure_mode_id=(
                None if failure_mode_id is None else str(failure_mode_id)
            ),
            subnet_key=subnet_key,
        )
        return PetriPlace(
            id=opaque,
            role=role,
            initial=initial,
            capacity=capacity,
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
        )

    def transition(
        self,
        role: TransitionRole,
        *,
        subnet_key: str,
        source_entity_type: str | None = None,
        source_entity_id: str | None = None,
        equipment_id: UUID | None = None,
        failure_mode_id: UUID | None = None,
    ) -> PetriTransition:
        self._transitions += 1
        opaque = f"t{self._transitions:04d}"
        self.id_map[opaque] = SourceMapping(
            kind=PetriElementKind.TRANSITION,
            role=str(role),
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
            equipment_id=None if equipment_id is None else str(equipment_id),
            failure_mode_id=(
                None if failure_mode_id is None else str(failure_mode_id)
            ),
            subnet_key=subnet_key,
        )
        return PetriTransition(
            id=opaque,
            role=role,
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
        )

    def arc(
        self,
        source: str,
        target: str,
        *,
        subnet_key: str,
        weight: int = 1,
        arc_type: str | None = None,
    ) -> PetriArc:
        self._arcs += 1
        opaque = f"a{self._arcs:04d}"
        self.id_map[opaque] = SourceMapping(
            kind=PetriElementKind.ARC,
            role="ARC",
            subnet_key=subnet_key,
        )
        return PetriArc(
            id=opaque,
            source=source,
            target=target,
            weight=weight,
            arc_type=arc_type,
        )


class PetriModelGenerator:
    """Build hierarchical Petri nets from a compiled reliability model.

    Generation is deterministic: the same ``CompiledModel`` always
    yields the same opaque ids and topology.
    """

    def generate(
        self,
        compiled: CompiledModel,
        *,
        reliability_model_id: UUID | None = None,
    ) -> PetriModel:
        """Generate system net + per-failure-mode subnets."""
        ids = _IdFactory()
        subnets: list[PetriSubnet] = []
        modes = sorted(compiled.failure_modes, key=lambda m: str(m.id))
        tasks_by_mode = _tasks_by_failure_mode(compiled.maintenance_tasks)
        for mode in modes:
            subnets.append(
                _failure_mode_subnet(
                    ids,
                    mode,
                    tasks_by_mode.get(mode.id, ()),
                )
            )
        subnets.append(_system_subnet(ids, compiled))
        return PetriModel(
            version_id=compiled.version_id,
            reliability_model_id=reliability_model_id,
            reliability_model_hash=compiled.model_hash(),
            subnets=tuple(subnets),
            id_map=dict(ids.id_map),
        )


def _tasks_by_failure_mode(
    tasks: tuple[CompiledMaintenanceTask, ...],
) -> dict[UUID, tuple[CompiledMaintenanceTask, ...]]:
    grouped: dict[UUID, list[CompiledMaintenanceTask]] = {}
    for task in sorted(tasks, key=lambda t: str(t.id)):
        if task.failure_mode_id is None:
            continue
        grouped.setdefault(task.failure_mode_id, []).append(task)
    return {key: tuple(value) for key, value in grouped.items()}


def _failure_mode_subnet(
    ids: _IdFactory,
    mode: CompiledFailureMode,
    tasks: tuple[CompiledMaintenanceTask, ...],
) -> PetriSubnet:
    key = f"fm:{mode.id}"
    case_id = key
    entity_type = "FailureMode"
    entity_id = str(mode.id)
    places: list[PetriPlace] = []
    transitions: list[PetriTransition] = []
    arcs: list[PetriArc] = []

    def link(src: str, dst: str) -> None:
        arcs.append(ids.arc(src, dst, subnet_key=key))

    up = ids.place(
        PlaceRole.UP,
        subnet_key=key,
        source_entity_type=entity_type,
        source_entity_id=entity_id,
        equipment_id=mode.equipment_id,
        failure_mode_id=mode.id,
        initial=1,
    )
    failed = ids.place(
        PlaceRole.FAILED,
        subnet_key=key,
        source_entity_type=entity_type,
        source_entity_id=entity_id,
        equipment_id=mode.equipment_id,
        failure_mode_id=mode.id,
    )
    maint = ids.place(
        PlaceRole.MAINTENANCE,
        subnet_key=key,
        source_entity_type=entity_type,
        source_entity_id=entity_id,
        equipment_id=mode.equipment_id,
        failure_mode_id=mode.id,
    )
    places.extend((up, failed, maint))

    cm_start = ids.transition(
        TransitionRole.CM_START,
        subnet_key=key,
        source_entity_type=entity_type,
        source_entity_id=entity_id,
        equipment_id=mode.equipment_id,
        failure_mode_id=mode.id,
    )
    cm_done = ids.transition(
        TransitionRole.CM_DONE,
        subnet_key=key,
        source_entity_type=entity_type,
        source_entity_id=entity_id,
        equipment_id=mode.equipment_id,
        failure_mode_id=mode.id,
    )
    transitions.extend((cm_start, cm_done))
    link(failed.id, cm_start.id)
    link(cm_start.id, maint.id)
    link(maint.id, cm_done.id)
    link(cm_done.id, up.id)

    if mode.is_detectable and mode.pf_interval_minutes is not None:
        pf = ids.place(
            PlaceRole.POTENTIAL_FAILURE,
            subnet_key=key,
            source_entity_type=entity_type,
            source_entity_id=entity_id,
            equipment_id=mode.equipment_id,
            failure_mode_id=mode.id,
        )
        places.append(pf)
        to_pf = ids.transition(
            TransitionRole.TO_PF,
            subnet_key=key,
            source_entity_type=entity_type,
            source_entity_id=entity_id,
            equipment_id=mode.equipment_id,
            failure_mode_id=mode.id,
        )
        detect = ids.transition(
            TransitionRole.DETECT,
            subnet_key=key,
            source_entity_type=entity_type,
            source_entity_id=entity_id,
            equipment_id=mode.equipment_id,
            failure_mode_id=mode.id,
        )
        miss = ids.transition(
            TransitionRole.MISS,
            subnet_key=key,
            source_entity_type=entity_type,
            source_entity_id=entity_id,
            equipment_id=mode.equipment_id,
            failure_mode_id=mode.id,
        )
        transitions.extend((to_pf, detect, miss))
        link(up.id, to_pf.id)
        link(to_pf.id, pf.id)
        # Both detect and miss converge on FAILED so the RAM
        # sequence DETECT/MISS -> CM_START -> CM_DONE can replay.
        link(pf.id, detect.id)
        link(detect.id, failed.id)
        link(pf.id, miss.id)
        link(miss.id, failed.id)
    else:
        fail = ids.transition(
            TransitionRole.FAIL,
            subnet_key=key,
            source_entity_type=entity_type,
            source_entity_id=entity_id,
            equipment_id=mode.equipment_id,
            failure_mode_id=mode.id,
        )
        transitions.append(fail)
        link(up.id, fail.id)
        link(fail.id, failed.id)

    has_pm = any(t.task_type is MaintenanceTaskType.PREVENTIVE for t in tasks)
    if has_pm:
        pm_start = ids.transition(
            TransitionRole.PM_START,
            subnet_key=key,
            source_entity_type=entity_type,
            source_entity_id=entity_id,
            equipment_id=mode.equipment_id,
            failure_mode_id=mode.id,
        )
        pm_done = ids.transition(
            TransitionRole.PM_DONE,
            subnet_key=key,
            source_entity_type=entity_type,
            source_entity_id=entity_id,
            equipment_id=mode.equipment_id,
            failure_mode_id=mode.id,
        )
        transitions.extend((pm_start, pm_done))
        link(up.id, pm_start.id)
        link(pm_start.id, maint.id)
        # Shared MAINTENANCE place; cm_done/pm_done both restore UP.
        # Add a dedicated return only if pm_done is distinct from cm.
        link(maint.id, pm_done.id)
        link(pm_done.id, up.id)

    return PetriSubnet(
        key=key,
        name=f"fm-{mode.id}",
        case_id=case_id,
        kind="failure_mode",
        places=tuple(places),
        transitions=tuple(transitions),
        arcs=tuple(arcs),
    )


def _system_subnet(
    ids: _IdFactory,
    compiled: CompiledModel,
) -> PetriSubnet:
    """Collapsed system net: one UP/DOWN block per equipment."""
    key = "system"
    places: list[PetriPlace] = []
    transitions: list[PetriTransition] = []
    arcs: list[PetriArc] = []
    equipment = sorted(compiled.equipment, key=lambda e: str(e.id))
    for item in equipment:
        up = ids.place(
            PlaceRole.EQUIPMENT_UP,
            subnet_key=key,
            source_entity_type="Equipment",
            source_entity_id=str(item.id),
            equipment_id=item.id,
            initial=1,
        )
        down = ids.place(
            PlaceRole.EQUIPMENT_DOWN,
            subnet_key=key,
            source_entity_type="Equipment",
            source_entity_id=str(item.id),
            equipment_id=item.id,
        )
        fail = ids.transition(
            TransitionRole.EQ_FAIL,
            subnet_key=key,
            source_entity_type="Equipment",
            source_entity_id=str(item.id),
            equipment_id=item.id,
        )
        repair = ids.transition(
            TransitionRole.EQ_REPAIR,
            subnet_key=key,
            source_entity_type="Equipment",
            source_entity_id=str(item.id),
            equipment_id=item.id,
        )
        places.extend((up, down))
        transitions.extend((fail, repair))
        arcs.append(ids.arc(up.id, fail.id, subnet_key=key))
        arcs.append(ids.arc(fail.id, down.id, subnet_key=key))
        arcs.append(ids.arc(down.id, repair.id, subnet_key=key))
        arcs.append(ids.arc(repair.id, up.id, subnet_key=key))
    return PetriSubnet(
        key=key,
        name="system",
        case_id="system",
        kind="system",
        places=tuple(places),
        transitions=tuple(transitions),
        arcs=tuple(arcs),
    )
