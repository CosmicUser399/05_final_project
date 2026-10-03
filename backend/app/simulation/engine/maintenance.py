"""Maintenance task selection and renewal effects."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import numpy as np

from app.domain.maintenance.entities import MaintenanceEffectType
from app.domain.maintenance.entities import MaintenanceTaskType
from app.domain.maintenance.entities import MaintenanceTrigger
from app.domain.reliability.compiled import CompiledMaintenanceTask


@dataclass(slots=True)
class RenewalState:
    """Age / rate state that survives across repairs."""

    virtual_age: float = 0.0
    rate_multiplier: float = 1.0
    eliminated: set[UUID] | None = None
    last_renewal_time: float = 0.0
    operating_time: float = 0.0

    def __post_init__(self) -> None:
        """Ensure ``eliminated`` is a mutable set."""
        if self.eliminated is None:
            self.eliminated = set()


class MaintenanceEngine:
    """Select CM/PM tasks and apply restoration effects."""

    def corrective_task(
        self,
        tasks: list[CompiledMaintenanceTask],
        equipment_id: UUID,
        failure_mode_id: UUID | None,
    ) -> CompiledMaintenanceTask | None:
        """Return the best matching corrective task."""
        candidates = [
            t
            for t in tasks
            if t.equipment_id == equipment_id
            and t.task_type is MaintenanceTaskType.CORRECTIVE
        ]
        if not candidates:
            return None
        # Prefer a task bound to the active failure mode.
        if failure_mode_id is not None:
            matched = [
                t for t in candidates if t.failure_mode_id == failure_mode_id
            ]
            if matched:
                return sorted(matched, key=lambda t: str(t.id))[0]
        unbound = [t for t in candidates if t.failure_mode_id is None]
        pool = unbound or candidates
        return sorted(pool, key=lambda t: str(t.id))[0]

    def preventive_tasks(
        self,
        tasks: list[CompiledMaintenanceTask],
        equipment_id: UUID,
    ) -> list[CompiledMaintenanceTask]:
        """Return calendar / running-time PM tasks for equipment."""
        result = [
            t
            for t in tasks
            if t.equipment_id == equipment_id
            and t.task_type is MaintenanceTaskType.PREVENTIVE
            and t.trigger
            in (
                MaintenanceTrigger.CALENDAR,
                MaintenanceTrigger.RUNNING_TIME,
            )
            and t.interval_minutes is not None
            and t.interval_minutes > 0
        ]
        return sorted(result, key=lambda t: str(t.id))

    def condition_task(
        self,
        tasks: list[CompiledMaintenanceTask],
        equipment_id: UUID,
        failure_mode_id: UUID | None,
    ) -> CompiledMaintenanceTask | None:
        """Return a condition-based task after detection."""
        candidates = [
            t
            for t in tasks
            if t.equipment_id == equipment_id
            and t.trigger is MaintenanceTrigger.CONDITION_BASED
        ]
        if not candidates:
            # Fall back to corrective task as the repair action.
            return self.corrective_task(tasks, equipment_id, failure_mode_id)
        if failure_mode_id is not None:
            matched = [
                t for t in candidates if t.failure_mode_id == failure_mode_id
            ]
            if matched:
                return sorted(matched, key=lambda t: str(t.id))[0]
        return sorted(candidates, key=lambda t: str(t.id))[0]

    def sample_duration(
        self,
        task: CompiledMaintenanceTask,
        rng: np.random.Generator,
    ) -> float:
        """Sample maintenance duration in minutes."""
        return float(task.duration.to_minutes().sample(rng))

    def apply_effect(
        self,
        task: CompiledMaintenanceTask,
        renewal: RenewalState,
        now: float,
        *,
        operating_delta: float = 0.0,
    ) -> RenewalState:
        """Return an updated renewal state after task completion."""
        renewal.operating_time += operating_delta
        kind = task.effect_type
        if kind is MaintenanceEffectType.RESTORE_AS_NEW:
            renewal.virtual_age = 0.0
            renewal.last_renewal_time = now
            return renewal
        if kind is MaintenanceEffectType.RESTORE_AS_OLD:
            renewal.last_renewal_time = now
            return renewal
        if kind is MaintenanceEffectType.PARTIAL_RESTORATION:
            fraction = task.effect_parameter or 0.0
            renewal.virtual_age *= max(0.0, 1.0 - fraction)
            renewal.last_renewal_time = now
            return renewal
        if kind is MaintenanceEffectType.RESET_FAILURE_AGE:
            renewal.virtual_age = 0.0
            renewal.last_renewal_time = now
            return renewal
        if kind is MaintenanceEffectType.CHANGE_FAILURE_RATE_MULTIPLIER:
            mult = task.effect_parameter or 1.0
            renewal.rate_multiplier *= mult
            renewal.last_renewal_time = now
            return renewal
        if kind is MaintenanceEffectType.REDUCE_REMAINING_LIFE:
            fraction = task.effect_parameter or 0.0
            # Increase virtual age toward a notional life of current age
            # + residual; here we age the unit by fraction of age.
            renewal.virtual_age *= 1.0 + max(0.0, fraction)
            renewal.last_renewal_time = now
            return renewal
        if kind is MaintenanceEffectType.ELIMINATE_FAILURE_MODE:
            if task.effect_failure_mode_id is not None:
                if renewal.eliminated is None:
                    renewal.eliminated = set()
                renewal.eliminated.add(task.effect_failure_mode_id)
            renewal.virtual_age = 0.0
            renewal.last_renewal_time = now
            return renewal
        # NONE
        renewal.last_renewal_time = now
        return renewal

    def next_pm_time(
        self,
        task: CompiledMaintenanceTask,
        renewal: RenewalState,
        now: float,
    ) -> float | None:
        """Return the next absolute PM time for a periodic task."""
        interval = task.interval_minutes
        if interval is None or interval <= 0:
            return None
        if task.trigger is MaintenanceTrigger.CALENDAR:
            # Next multiple of interval strictly after ``now``.
            k = int(now // interval) + 1
            return k * interval
        if task.trigger is MaintenanceTrigger.RUNNING_TIME:
            remaining = interval - (renewal.operating_time % interval)
            if remaining <= 0:
                remaining = interval
            return now + remaining
        return None
