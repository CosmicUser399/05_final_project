"""Collect state intervals and compute run-level RAM metrics."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from uuid import UUID

from app.domain.simulation.results import EquipmentRunMetrics
from app.domain.simulation.results import LoggedEvent
from app.domain.simulation.results import SystemRunMetrics
from app.domain.simulation.states import DOWN_STATES
from app.domain.simulation.states import PRODUCING_STATES
from app.domain.simulation.states import EquipmentState
from app.simulation.events.types import EventType
from app.simulation.events.types import SimulationEvent


@dataclass(slots=True)
class _EquipAcc:
    equipment_id: UUID
    state: EquipmentState
    state_since: float
    uptime: float = 0.0
    downtime: float = 0.0
    failure_count: int = 0
    cm_count: int = 0
    pm_count: int = 0
    detection_count: int = 0
    missed_detection_count: int = 0
    cm_duration: float = 0.0
    cm_open_at: float | None = None
    mdt_duration: float = 0.0
    maint_events: int = 0


@dataclass(slots=True)
class MetricsCollector:
    """Accumulate intervals and event counts for one run."""

    warmup: float
    horizon: float
    equipment: dict[UUID, _EquipAcc] = field(default_factory=dict)
    events: list[LoggedEvent] = field(default_factory=list)
    collect_events: bool = True
    event_limit: int | None = None
    production_loss: float = 0.0
    false_positive_count: int = 0
    _capacity: float = 1.0
    _nominal: float = 0.0
    _last_time: float = 0.0
    _collect_loss: bool = True

    def register(
        self,
        equipment_id: UUID,
        state: EquipmentState,
        now: float = 0.0,
    ) -> None:
        """Register an equipment unit at its initial state."""
        self.equipment[equipment_id] = _EquipAcc(
            equipment_id=equipment_id,
            state=state,
            state_since=now,
        )

    def set_production(self, nominal: float, capacity: float) -> None:
        """Initialise production tracking."""
        self._nominal = nominal
        self._capacity = capacity

    def set_capacity(self, capacity: float) -> None:
        """Update capacity for the next interval (no integration)."""
        self._capacity = capacity

    def advance_production(self, now: float, capacity: float) -> None:
        """Integrate production loss from ``_last_time`` to ``now``."""
        if self._collect_loss and self._nominal > 0:
            delta = now - self._last_time
            if delta > 0 and now > self.warmup:
                start = max(self._last_time, self.warmup)
                effective = now - start
                if effective > 0:
                    loss_rate = self._nominal * max(0.0, 1.0 - self._capacity)
                    self.production_loss += loss_rate * effective
        self._capacity = capacity
        self._last_time = now

    def on_state_change(
        self,
        equipment_id: UUID,
        new_state: EquipmentState,
        now: float,
    ) -> None:
        """Close the previous state interval and open a new one."""
        acc = self.equipment[equipment_id]
        self._close_interval(acc, now)
        # CM / MDT bookkeeping.
        if new_state is EquipmentState.FAILED and acc.cm_open_at is None:
            acc.failure_count += 1
            acc.cm_open_at = now
        if acc.cm_open_at is not None and new_state is EquipmentState.UP:
            if now > self.warmup:
                start = max(acc.cm_open_at, self.warmup)
                acc.cm_duration += max(0.0, now - start)
                acc.mdt_duration += max(0.0, now - start)
            acc.cm_count += 1
            acc.maint_events += 1
            acc.cm_open_at = None
        acc.state = new_state
        acc.state_since = now

    def on_pm_complete(self, equipment_id: UUID, now: float) -> None:
        """Record a completed preventive maintenance."""
        acc = self.equipment[equipment_id]
        acc.pm_count += 1
        acc.maint_events += 1
        if acc.cm_open_at is None and now > self.warmup:
            # PM downtime already in state intervals; MDT for Ao uses
            # down intervals separately via downtime.
            pass

    def on_detection(self, equipment_id: UUID, detected: bool) -> None:
        """Record a detection or miss for one PF window."""
        acc = self.equipment[equipment_id]
        if detected:
            acc.detection_count += 1
        else:
            acc.missed_detection_count += 1

    def log_event(self, event: SimulationEvent) -> None:
        """Optionally append an event to the run log."""
        if not self.collect_events:
            return
        if (
            self.event_limit is not None
            and len(self.events) >= self.event_limit
        ):
            return
        if event.event_type is EventType.END:
            return
        self.events.append(
            LoggedEvent(
                time_minutes=event.time,
                event_type=event.event_type.value,
                equipment_id=event.equipment_id,
                failure_mode_id=event.failure_mode_id,
                task_id=event.task_id,
                resource_id=event.resource_id,
                spare_part_id=event.spare_part_id,
                details=dict(event.details),
            )
        )

    def finalize(self, now: float) -> None:
        """Close open intervals at the horizon."""
        for acc in self.equipment.values():
            self._close_interval(acc, now)
            if acc.cm_open_at is not None and now > self.warmup:
                start = max(acc.cm_open_at, self.warmup)
                acc.mdt_duration += max(0.0, now - start)
        self.advance_production(now, self._capacity)

    def system_metrics(self) -> SystemRunMetrics:
        """Build system-level metrics after :meth:`finalize`."""
        uptime = sum(a.uptime for a in self.equipment.values())
        downtime = sum(a.downtime for a in self.equipment.values())
        failures = sum(a.failure_count for a in self.equipment.values())
        cm = sum(a.cm_count for a in self.equipment.values())
        pm = sum(a.pm_count for a in self.equipment.values())
        detections = sum(a.detection_count for a in self.equipment.values())
        misses = sum(a.missed_detection_count for a in self.equipment.values())
        cm_time = sum(a.cm_duration for a in self.equipment.values())
        mdt = sum(a.mdt_duration for a in self.equipment.values())
        # Prefer equipment-local uptime for single-asset models.
        if len(self.equipment) == 1:
            only = next(iter(self.equipment.values()))
            uptime = only.uptime
            downtime = only.downtime
            mdt = only.downtime
            cm_time = only.cm_duration
        mtbf = uptime / failures if failures > 0 else None
        mttr = cm_time / cm if cm > 0 else None
        maint = cm + pm
        mtbm = uptime / maint if maint > 0 else None
        mdt_mean = mdt / maint if maint > 0 else None
        ai = None
        if mtbf is not None and mttr is not None and (mtbf + mttr) > 0:
            ai = mtbf / (mtbf + mttr)
        ao = None
        if mtbm is not None and mdt_mean is not None and (mtbm + mdt_mean) > 0:
            ao = mtbm / (mtbm + mdt_mean)
        prod_avail = None
        measured = max(0.0, self.horizon - self.warmup)
        if self._nominal > 0 and measured > 0:
            max_prod = self._nominal * measured
            produced = max_prod - self.production_loss
            prod_avail = produced / max_prod if max_prod > 0 else None
        return SystemRunMetrics(
            uptime_minutes=uptime,
            downtime_minutes=downtime,
            failure_count=failures,
            cm_count=cm,
            pm_count=pm,
            detection_count=detections,
            missed_detection_count=misses,
            false_positive_count=self.false_positive_count,
            mtbf_minutes=mtbf,
            mttr_minutes=mttr,
            mtbm_minutes=mtbm,
            mdt_minutes=mdt_mean,
            ai=ai,
            ao=ao,
            production_loss=self.production_loss,
            production_availability=prod_avail,
        )

    def equipment_metrics(self) -> tuple[EquipmentRunMetrics, ...]:
        """Build per-equipment metrics."""
        rows: list[EquipmentRunMetrics] = []
        for acc in sorted(
            self.equipment.values(), key=lambda a: str(a.equipment_id)
        ):
            mtbf = (
                acc.uptime / acc.failure_count
                if acc.failure_count > 0
                else None
            )
            mttr = acc.cm_duration / acc.cm_count if acc.cm_count > 0 else None
            ai = None
            if mtbf is not None and mttr is not None and (mtbf + mttr) > 0:
                ai = mtbf / (mtbf + mttr)
            rows.append(
                EquipmentRunMetrics(
                    equipment_id=acc.equipment_id,
                    uptime_minutes=acc.uptime,
                    downtime_minutes=acc.downtime,
                    failure_count=acc.failure_count,
                    cm_count=acc.cm_count,
                    pm_count=acc.pm_count,
                    detection_count=acc.detection_count,
                    missed_detection_count=acc.missed_detection_count,
                    mtbf_minutes=mtbf,
                    mttr_minutes=mttr,
                    ai=ai,
                )
            )
        return tuple(rows)

    def _close_interval(self, acc: _EquipAcc, now: float) -> None:
        if now <= acc.state_since:
            return
        start = acc.state_since
        end = now
        if end <= self.warmup:
            return
        start = max(start, self.warmup)
        duration = end - start
        if duration <= 0:
            return
        if acc.state in PRODUCING_STATES:
            acc.uptime += duration
        elif acc.state in DOWN_STATES:
            acc.downtime += duration
