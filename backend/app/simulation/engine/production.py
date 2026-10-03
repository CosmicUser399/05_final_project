"""Production capacity and loss integration."""

from __future__ import annotations

from uuid import UUID

from app.domain.reliability.compiled import CompiledModel
from app.domain.reliability.compiled import CompiledProductionImpact
from app.domain.reliability.compiled import CompiledStructure
from app.domain.reliability.entities import StructureType
from app.domain.simulation.states import PRODUCING_STATES
from app.domain.simulation.states import EquipmentState


class ProductionImpactEngine:
    """Evaluate system capacity from equipment states and structures."""

    def __init__(self, model: CompiledModel) -> None:
        """Bind impacts and reliability structures from ``model``."""
        self._nominal = (
            model.production.nominal_rate if model.production else 0.0
        )
        self._impacts: tuple[CompiledProductionImpact, ...] = (
            model.production.impacts if model.production else ()
        )
        self._structures = model.structures
        self._equipment_ids = [e.id for e in model.equipment]
        by_parent: dict[UUID | None, list[CompiledStructure]] = {}
        for structure in self._structures:
            by_parent.setdefault(structure.parent_structure_id, []).append(
                structure
            )
        self._roots = sorted(
            by_parent.get(None, []),
            key=lambda s: str(s.id),
        )
        self._children = {
            key: sorted(value, key=lambda s: str(s.id))
            for key, value in by_parent.items()
            if key is not None
        }

    @property
    def nominal_rate(self) -> float:
        """Return the nominal production rate."""
        return self._nominal

    def leaf_capacity(
        self,
        equipment_id: UUID,
        state: EquipmentState,
        active_failure_mode_id: UUID | None,
    ) -> float:
        """Return capacity factor in ``[0, 1]`` for one asset."""
        if state is EquipmentState.STANDBY:
            return 0.0
        if state in PRODUCING_STATES:
            return 1.0
        loss = 0.0
        for impact in self._impacts:
            if impact.equipment_id != equipment_id:
                continue
            if (
                impact.failure_mode_id is not None
                and active_failure_mode_id is not None
                and impact.failure_mode_id != active_failure_mode_id
            ):
                continue
            loss = max(loss, impact.loss_fraction)
        if not self._impacts:
            # No impacts declared: any downtime removes full capacity.
            loss = 1.0
        elif loss == 0.0:
            # Equipment is down but no matching impact: treat as full loss
            # when any equipment-level impact exists, else full loss.
            for impact in self._impacts:
                if (
                    impact.equipment_id == equipment_id
                    and impact.failure_mode_id is None
                ):
                    loss = impact.loss_fraction
                    break
            else:
                loss = 1.0
        return max(0.0, min(1.0, 1.0 - loss))

    def system_capacity(
        self,
        states: dict[UUID, EquipmentState],
        active_modes: dict[UUID, UUID | None],
    ) -> float:
        """Return the root capacity factor in ``[0, 1]``."""
        if self._roots:
            values = [
                self._eval_structure(root, states, active_modes)
                for root in self._roots
            ]
            return min(values) if values else 1.0
        # Default: series of all equipment.
        if not self._equipment_ids:
            return 1.0
        return min(
            self.leaf_capacity(eq_id, states[eq_id], active_modes.get(eq_id))
            for eq_id in self._equipment_ids
        )

    def loss_rate(self, capacity: float) -> float:
        """Return production loss rate at the given capacity."""
        if self._nominal <= 0:
            return 0.0
        return self._nominal * max(0.0, 1.0 - capacity)

    def _eval_structure(
        self,
        structure: CompiledStructure,
        states: dict[UUID, EquipmentState],
        active_modes: dict[UUID, UUID | None],
    ) -> float:
        member_caps: list[float] = []
        ordered = sorted(structure.members, key=lambda m: m.position)
        for member in ordered:
            if member.equipment_id is not None:
                eq_id = member.equipment_id
                member_caps.append(
                    self.leaf_capacity(
                        eq_id,
                        states[eq_id],
                        active_modes.get(eq_id),
                    )
                )
            elif member.child_structure_id is not None:
                child = self._find(member.child_structure_id)
                member_caps.append(
                    self._eval_structure(child, states, active_modes)
                )
        if not member_caps:
            return 1.0
        kind = structure.structure_type
        if kind is StructureType.SERIES:
            return min(member_caps)
        if kind is StructureType.PARALLEL:
            return min(1.0, sum(member_caps))
        if kind is StructureType.K_OF_N:
            k = structure.k or 1
            working = sum(1 for c in member_caps if c > 0.0)
            if working < k:
                return 0.0
            # Capacity scales with available working fraction of k.
            return min(1.0, working / k)
        if kind is StructureType.STANDBY:
            # Primary first; first positive capacity wins.
            for cap in member_caps:
                if cap > 0.0:
                    return cap
            return 0.0
        return min(member_caps)

    def _find(self, structure_id: UUID) -> CompiledStructure:
        for structure in self._structures:
            if structure.id == structure_id:
                return structure
        raise KeyError(structure_id)
