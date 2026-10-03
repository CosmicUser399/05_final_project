"""Event-driven RAM SimulationEngine (single Monte Carlo trial)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from uuid import NAMESPACE_URL
from uuid import UUID
from uuid import uuid5

from app.domain.equipment.entities import StandbyMode
from app.domain.errors import SimulationError
from app.domain.reliability.compiled import CompiledDiagnosticTask
from app.domain.reliability.compiled import CompiledFailureMode
from app.domain.reliability.compiled import CompiledMaintenanceTask
from app.domain.reliability.compiled import CompiledModel
from app.domain.reliability.compiled import ScenarioOverlay
from app.domain.reliability.scenario_overlay import apply_scenario_overlay
from app.domain.simulation.config import SimulationConfiguration
from app.domain.simulation.results import SimulationRunResult
from app.domain.simulation.states import EquipmentState
from app.simulation.engine.diagnostic import DiagnosticEngine
from app.simulation.engine.failure import CompetingRiskModel
from app.simulation.engine.failure import FailureGenerator
from app.simulation.engine.failure import SampledFailure
from app.simulation.engine.maintenance import MaintenanceEngine
from app.simulation.engine.maintenance import RenewalState
from app.simulation.engine.metrics import MetricsCollector
from app.simulation.engine.pf_scheduler import PFIntervalScheduler
from app.simulation.engine.production import ProductionImpactEngine
from app.simulation.engine.resources import ResourceManager
from app.simulation.engine.spares import SparePartManager
from app.simulation.engine.state_machine import EquipmentStateMachine
from app.simulation.events.clock import SimulationClock
from app.simulation.events.queue import EventQueue
from app.simulation.events.types import EventType
from app.simulation.events.types import SimulationEvent
from app.simulation.random.provider import RandomProvider


@dataclass(slots=True)
class _PendingFailure:
    """Scheduled competing-risk failure with optional detection."""

    sample: SampledFailure
    generation: int
    t_potential: float | None = None
    detection_time: float | None = None
    detected: bool = False
    cancelled: bool = False


@dataclass(slots=True)
class _MaintJob:
    """In-flight corrective or preventive maintenance job."""

    job_id: UUID
    equipment_id: UUID
    task: CompiledMaintenanceTask
    failure_mode_id: UUID | None
    is_corrective: bool
    generation: int
    duration: float = 0.0
    phase: str = "start"
    cancelled: bool = False


@dataclass(slots=True)
class _EquipRuntime:
    """Mutable per-equipment simulation state."""

    equipment_id: UUID
    machine: EquipmentStateMachine
    renewal: RenewalState
    modes: list[CompiledFailureMode]
    pending: _PendingFailure | None = None
    generation: int = 0
    active_failure_mode_id: UUID | None = None
    job: _MaintJob | None = None
    is_standby_unit: bool = False


@dataclass(slots=True)
class _SimContext:
    """Shared mutable context for one engine run."""

    model: CompiledModel
    horizon: float
    rng: RandomProvider
    clock: SimulationClock
    queue: EventQueue
    metrics: MetricsCollector
    resources: ResourceManager
    spares: SparePartManager
    production: ProductionImpactEngine
    failure_gen: FailureGenerator
    competing: CompetingRiskModel
    pf: PFIntervalScheduler
    diagnostics: DiagnosticEngine
    maintenance: MaintenanceEngine
    equipment: dict[UUID, _EquipRuntime] = field(default_factory=dict)
    jobs: dict[UUID, _MaintJob] = field(default_factory=dict)
    mode_index: dict[UUID, int] = field(default_factory=dict)
    pf_windows: list[tuple[float, float]] = field(default_factory=list)
    tasks_by_eq: dict[UUID, list[CompiledMaintenanceTask]] = field(
        default_factory=dict
    )
    diag_by_eq: dict[UUID, list[CompiledDiagnosticTask]] = field(
        default_factory=dict
    )
    task_index: dict[UUID, int] = field(default_factory=dict)
    job_seq: int = 0


class SimulationEngine:
    """Run one event-driven RAM trial.

    The engine does not touch the database or UI. Input is a compiled
    reliability model (optionally overlaid by a scenario), a
    configuration and an explicit seed.
    """

    def run(
        self,
        model: CompiledModel,
        scenario: ScenarioOverlay | None,
        configuration: SimulationConfiguration,
        seed: int | None = None,
    ) -> SimulationRunResult:
        """Execute a single Monte Carlo trial and return metrics."""
        overlay = scenario or ScenarioOverlay()
        effective = apply_scenario_overlay(model, overlay)
        master_seed = configuration.random_seed if seed is None else int(seed)
        horizon = configuration.horizon_minutes()
        warmup = configuration.warmup_minutes()
        if warmup >= horizon:
            raise SimulationError(
                "warmup_period must be < horizon",
                code="INVALID_WARMUP",
            )
        ctx = self._build_context(
            effective, configuration, master_seed, horizon, warmup
        )
        self._initialize(ctx)
        while ctx.queue:
            nxt = ctx.queue.peek()
            if nxt is None or nxt.time > horizon:
                break
            event = ctx.queue.pop()
            if event.time < ctx.clock.time:
                continue
            ctx.clock.advance_to(event.time)
            # Integrate the previous capacity up to now, then apply the
            # event and refresh capacity for the next interval.
            self._sync_production(ctx)
            applied = self._dispatch(ctx, event)
            ctx.metrics.set_capacity(self._capacity(ctx))
            if applied:
                ctx.metrics.log_event(event)
        ctx.clock.advance_to(horizon)
        self._sync_production(ctx)
        self._finalize(ctx)
        metrics = ctx.metrics.system_metrics()
        eq_metrics = (
            ctx.metrics.equipment_metrics()
            if configuration.collect_equipment_metrics
            else ()
        )
        events = (
            tuple(ctx.metrics.events)
            if configuration.collect_event_log
            else ()
        )
        return SimulationRunResult(
            seed=master_seed,
            run_id=configuration.run_id,
            horizon_minutes=horizon,
            warmup_minutes=warmup,
            model_hash=effective.model_hash(),
            scenario_hash=overlay.scenario_hash(),
            metrics=metrics,
            equipment_metrics=eq_metrics,
            events=events,
            resource_wait_minutes=ctx.resources.total_wait_minutes,
            spare_wait_minutes=ctx.spares.total_wait_minutes,
        )

    def _build_context(
        self,
        model: CompiledModel,
        configuration: SimulationConfiguration,
        seed: int,
        horizon: float,
        warmup: float,
    ) -> _SimContext:
        rng = RandomProvider(seed=seed, run_id=configuration.run_id)
        modes = list(model.failure_modes)
        mode_index = {mode.id: index for index, mode in enumerate(modes)}
        tasks_by_eq: dict[UUID, list[CompiledMaintenanceTask]] = {}
        for task in model.maintenance_tasks:
            tasks_by_eq.setdefault(task.equipment_id, []).append(task)
        diag_by_eq: dict[UUID, list[CompiledDiagnosticTask]] = {}
        for diag in model.diagnostic_tasks:
            diag_by_eq.setdefault(diag.equipment_id, []).append(diag)
        task_index = {
            task.id: index
            for index, task in enumerate(
                sorted(model.maintenance_tasks, key=lambda t: str(t.id))
            )
        }
        return _SimContext(
            model=model,
            horizon=horizon,
            rng=rng,
            clock=SimulationClock(),
            queue=EventQueue(),
            metrics=MetricsCollector(
                warmup=warmup,
                horizon=horizon,
                collect_events=configuration.collect_event_log,
                event_limit=configuration.event_log_limit,
                _collect_loss=configuration.collect_production_loss,
            ),
            resources=ResourceManager.from_resources(model.resources),
            spares=SparePartManager.from_spares(model.spare_parts),
            production=ProductionImpactEngine(model),
            failure_gen=FailureGenerator(),
            competing=CompetingRiskModel(),
            pf=PFIntervalScheduler(),
            diagnostics=DiagnosticEngine(),
            maintenance=MaintenanceEngine(),
            mode_index=mode_index,
            tasks_by_eq=tasks_by_eq,
            diag_by_eq=diag_by_eq,
            task_index=task_index,
        )

    def _initialize(self, ctx: _SimContext) -> None:
        for equipment in sorted(ctx.model.equipment, key=lambda e: str(e.id)):
            initial = EquipmentState.UP
            is_standby = equipment.standby_mode is not StandbyMode.NONE
            # Standby units start inactive unless they are the only unit.
            if is_standby and len(ctx.model.equipment) > 1:
                initial = EquipmentState.STANDBY
            runtime = _EquipRuntime(
                equipment_id=equipment.id,
                machine=EquipmentStateMachine(equipment.id, initial),
                renewal=RenewalState(),
                modes=[
                    m
                    for m in ctx.model.failure_modes
                    if m.equipment_id == equipment.id
                ],
                is_standby_unit=initial is EquipmentState.STANDBY,
            )
            ctx.equipment[equipment.id] = runtime
            ctx.metrics.register(equipment.id, initial)
            if initial is EquipmentState.UP:
                self._schedule_failures(ctx, runtime)
                self._schedule_pms(ctx, runtime)
        capacity = self._capacity(ctx)
        ctx.metrics.set_production(ctx.production.nominal_rate, capacity)

    def _dispatch(self, ctx: _SimContext, event: SimulationEvent) -> bool:
        """Dispatch ``event``; return whether it should be logged."""
        handlers: dict[
            EventType, Callable[[_SimContext, SimulationEvent], bool]
        ] = {
            EventType.POTENTIAL_FAILURE: self._on_potential_failure,
            EventType.DETECTION: self._on_detection,
            EventType.FAILURE: self._on_failure,
            EventType.CM_START: self._on_cm_start,
            EventType.CM_COMPLETE: self._on_cm_complete,
            EventType.PM_START: self._on_pm_start,
            EventType.PM_COMPLETE: self._on_pm_complete,
            EventType.SPARE_AVAILABLE: self._on_spare_available,
            EventType.RESOURCE_AVAILABLE: self._on_resource_available,
            EventType.RESOURCE_BUSY: self._log_only,
            EventType.SPARE_REQUEST: self._log_only,
            EventType.PRODUCTION_CHANGE: self._log_only,
            EventType.DIAGNOSTIC: self._log_only,
        }
        handler = handlers.get(event.event_type)
        if handler is None:
            return True
        return handler(ctx, event)

    @staticmethod
    def _log_only(_ctx: _SimContext, _event: SimulationEvent) -> bool:
        """Keep a queued informational event in the log."""
        return True

    def _schedule_failures(
        self, ctx: _SimContext, runtime: _EquipRuntime
    ) -> None:
        if runtime.machine.state not in (
            EquipmentState.UP,
            EquipmentState.POTENTIAL_FAILURE,
        ):
            return
        if not runtime.modes:
            return
        rngs = {
            mode.id: ctx.rng.generator(
                FailureGenerator.STREAM_BASE,
                ctx.mode_index[mode.id],
            )
            for mode in runtime.modes
        }
        sample = ctx.competing.next_failure(
            runtime.modes,
            ctx.clock.time,
            rngs,
            virtual_age=runtime.renewal.virtual_age,
            rate_multiplier=runtime.renewal.rate_multiplier,
            eliminated=runtime.renewal.eliminated or set(),
        )
        if sample is None or sample.absolute_time > ctx.horizon:
            runtime.pending = None
            return
        mode = next(m for m in runtime.modes if m.id == sample.failure_mode_id)
        window = ctx.pf.window(mode, sample.absolute_time)
        generation = runtime.generation
        pending = _PendingFailure(
            sample=sample,
            generation=generation,
            t_potential=window.t_potential,
        )
        if window.t_potential is not None:
            ctx.pf_windows.append((window.t_potential, window.t_failure))
            diag_rng = ctx.rng.generator(
                2000, ctx.mode_index[mode.id], generation
            )
            detection = ctx.diagnostics.evaluate_detection(
                window,
                ctx.diag_by_eq.get(runtime.equipment_id, []),
                diag_rng,
            )
            pending.detected = detection.detected
            pending.detection_time = detection.detection_time
            if window.t_potential <= ctx.horizon:
                ctx.queue.schedule(
                    SimulationEvent(
                        time=window.t_potential,
                        event_type=EventType.POTENTIAL_FAILURE,
                        equipment_id=runtime.equipment_id,
                        failure_mode_id=mode.id,
                        details={"generation": generation},
                    )
                )
            if detection.detected and detection.detection_time is not None:
                if detection.detection_time <= ctx.horizon:
                    ctx.queue.schedule(
                        SimulationEvent(
                            time=detection.detection_time,
                            event_type=EventType.DETECTION,
                            equipment_id=runtime.equipment_id,
                            failure_mode_id=mode.id,
                            task_id=detection.detecting_task_id,
                            details={"generation": generation},
                        )
                    )
        ctx.queue.schedule(
            SimulationEvent(
                time=sample.absolute_time,
                event_type=EventType.FAILURE,
                equipment_id=runtime.equipment_id,
                failure_mode_id=mode.id,
                details={"generation": generation},
            )
        )
        runtime.pending = pending

    def _schedule_pms(self, ctx: _SimContext, runtime: _EquipRuntime) -> None:
        tasks = ctx.maintenance.preventive_tasks(
            ctx.tasks_by_eq.get(runtime.equipment_id, []),
            runtime.equipment_id,
        )
        for task in tasks:
            t_next = ctx.maintenance.next_pm_time(
                task, runtime.renewal, ctx.clock.time
            )
            if t_next is None or t_next > ctx.horizon:
                continue
            ctx.queue.schedule(
                SimulationEvent(
                    time=t_next,
                    event_type=EventType.PM_START,
                    equipment_id=runtime.equipment_id,
                    task_id=task.id,
                    details={"generation": runtime.generation},
                )
            )

    def _cancel_pending(self, runtime: _EquipRuntime) -> None:
        if runtime.pending is not None:
            runtime.pending.cancelled = True
            runtime.pending = None
        runtime.generation += 1

    def _on_potential_failure(
        self, ctx: _SimContext, event: SimulationEvent
    ) -> bool:
        runtime = ctx.equipment[event.equipment_id]  # type: ignore[index]
        pending = runtime.pending
        if (
            pending is None
            or pending.cancelled
            or pending.generation != event.details.get("generation")
        ):
            return False
        if runtime.machine.state is not EquipmentState.UP:
            return False
        self._set_state(ctx, runtime, EquipmentState.POTENTIAL_FAILURE)
        runtime.active_failure_mode_id = event.failure_mode_id
        return True

    def _on_detection(self, ctx: _SimContext, event: SimulationEvent) -> bool:
        runtime = ctx.equipment[event.equipment_id]  # type: ignore[index]
        pending = runtime.pending
        if (
            pending is None
            or pending.cancelled
            or not pending.detected
            or pending.generation != event.details.get("generation")
        ):
            return False
        ctx.metrics.on_detection(runtime.equipment_id, True)
        # Cancel the functional failure; start condition-based CM.
        pending.cancelled = True
        runtime.pending = None
        runtime.active_failure_mode_id = event.failure_mode_id
        if runtime.machine.state is EquipmentState.UP:
            self._set_state(ctx, runtime, EquipmentState.POTENTIAL_FAILURE)
        task = ctx.maintenance.condition_task(
            ctx.tasks_by_eq.get(runtime.equipment_id, []),
            runtime.equipment_id,
            event.failure_mode_id,
        )
        if task is None:
            # No task: clear PF and reschedule as if restored.
            self._set_state(ctx, runtime, EquipmentState.UP)
            runtime.generation += 1
            self._schedule_failures(ctx, runtime)
            return True
        self._begin_maintenance(
            ctx,
            runtime,
            task,
            failure_mode_id=event.failure_mode_id,
            is_corrective=True,
        )
        return True

    def _on_failure(self, ctx: _SimContext, event: SimulationEvent) -> bool:
        runtime = ctx.equipment[event.equipment_id]  # type: ignore[index]
        pending = runtime.pending
        if (
            pending is None
            or pending.cancelled
            or pending.generation != event.details.get("generation")
        ):
            return False
        if pending.detected and pending.detection_time is not None:
            # Detection path already handled (or will handle) CM.
            if pending.detection_time < pending.sample.absolute_time:
                return False
        if pending.t_potential is not None and not pending.detected:
            ctx.metrics.on_detection(runtime.equipment_id, False)
        runtime.active_failure_mode_id = event.failure_mode_id
        if runtime.machine.state in (
            EquipmentState.UP,
            EquipmentState.POTENTIAL_FAILURE,
        ):
            self._set_state(ctx, runtime, EquipmentState.FAILED)
        self._activate_standby(ctx, runtime.equipment_id)
        task = ctx.maintenance.corrective_task(
            ctx.tasks_by_eq.get(runtime.equipment_id, []),
            runtime.equipment_id,
            event.failure_mode_id,
        )
        if task is None:
            runtime.pending = None
            return True
        eq_row = next(
            e for e in ctx.model.equipment if e.id == runtime.equipment_id
        )
        if not eq_row.is_repairable:
            runtime.pending = None
            return True
        runtime.pending = None
        self._begin_maintenance(
            ctx,
            runtime,
            task,
            failure_mode_id=event.failure_mode_id,
            is_corrective=True,
        )
        return True

    def _on_pm_start(self, ctx: _SimContext, event: SimulationEvent) -> bool:
        runtime = ctx.equipment[event.equipment_id]  # type: ignore[index]
        if event.details.get("generation") != runtime.generation:
            return False
        if runtime.machine.state not in (
            EquipmentState.UP,
            EquipmentState.POTENTIAL_FAILURE,
            EquipmentState.STANDBY,
        ):
            return False
        task = next(
            (
                t
                for t in ctx.tasks_by_eq.get(runtime.equipment_id, [])
                if t.id == event.task_id
            ),
            None,
        )
        if task is None:
            return False
        # PM preempts a pending failure.
        self._cancel_pending(runtime)
        self._begin_maintenance(
            ctx,
            runtime,
            task,
            failure_mode_id=task.failure_mode_id,
            is_corrective=False,
        )
        return True

    def _begin_maintenance(
        self,
        ctx: _SimContext,
        runtime: _EquipRuntime,
        task: CompiledMaintenanceTask,
        *,
        failure_mode_id: UUID | None,
        is_corrective: bool,
    ) -> None:
        task_key = ctx.task_index.get(task.id, 0)
        duration_rng = ctx.rng.generator(3000, task_key, runtime.generation)
        duration = ctx.maintenance.sample_duration(task, duration_rng)
        ctx.job_seq += 1
        job_id = uuid5(
            NAMESPACE_URL,
            f"job:{ctx.rng.seed}:{ctx.rng.run_id}:{ctx.job_seq}",
        )
        job = _MaintJob(
            job_id=job_id,
            equipment_id=runtime.equipment_id,
            task=task,
            failure_mode_id=failure_mode_id,
            is_corrective=is_corrective,
            generation=runtime.generation,
            duration=duration,
        )
        runtime.job = job
        ctx.jobs[job.job_id] = job
        if is_corrective and runtime.machine.state is EquipmentState.UP:
            self._set_state(ctx, runtime, EquipmentState.FAILED)
        if is_corrective and runtime.machine.state in (
            EquipmentState.FAILED,
            EquipmentState.POTENTIAL_FAILURE,
        ):
            self._set_state(ctx, runtime, EquipmentState.DIAGNOSIS)
        if is_corrective:
            ctx.metrics.log_event(
                SimulationEvent(
                    time=ctx.clock.time,
                    event_type=EventType.CM_START,
                    equipment_id=runtime.equipment_id,
                    failure_mode_id=failure_mode_id,
                    task_id=task.id,
                    details={"job_id": str(job.job_id)},
                )
            )
        self._try_start_work(ctx, job)

    def _try_start_work(self, ctx: _SimContext, job: _MaintJob) -> None:
        if job.cancelled:
            return
        runtime = ctx.equipment[job.equipment_id]
        if runtime.job is None or runtime.job.job_id != job.job_id:
            return
        req_res = job.task.resource_requirements
        req_sp = job.task.spare_requirements
        # Resources first.
        if req_res:
            got = ctx.resources.acquire(job.job_id, req_res, ctx.clock.time)
            if not got:
                if runtime.machine.state is EquipmentState.DIAGNOSIS:
                    self._set_state(
                        ctx,
                        runtime,
                        EquipmentState.WAITING_FOR_RESOURCE,
                    )
                elif runtime.machine.state in (
                    EquipmentState.UP,
                    EquipmentState.STANDBY,
                    EquipmentState.POTENTIAL_FAILURE,
                ):
                    self._set_state(
                        ctx,
                        runtime,
                        EquipmentState.WAITING_FOR_RESOURCE,
                    )
                ctx.queue.schedule(
                    SimulationEvent(
                        time=ctx.clock.time,
                        event_type=EventType.RESOURCE_BUSY,
                        equipment_id=runtime.equipment_id,
                        task_id=job.task.id,
                        details={"job_id": str(job.job_id)},
                    )
                )
                return
            ctx.resources.close_wait(job.job_id, ctx.clock.time)
        # Spares next.
        if req_sp:
            ok, orders = ctx.spares.request(job.job_id, req_sp, ctx.clock.time)
            for spare_id, available_at in orders:
                ctx.queue.schedule(
                    SimulationEvent(
                        time=available_at,
                        event_type=EventType.SPARE_AVAILABLE,
                        equipment_id=runtime.equipment_id,
                        spare_part_id=spare_id,
                        details={
                            "job_id": str(job.job_id),
                            "quantity": 1,
                        },
                    )
                )
                ctx.metrics.log_event(
                    SimulationEvent(
                        time=ctx.clock.time,
                        event_type=EventType.SPARE_REQUEST,
                        equipment_id=runtime.equipment_id,
                        spare_part_id=spare_id,
                        details={"job_id": str(job.job_id)},
                    )
                )
            if not ok:
                self._set_state(ctx, runtime, EquipmentState.WAITING_FOR_SPARE)
                return
            ctx.spares.close_wait(job.job_id, ctx.clock.time)
        # Ready to work.
        if runtime.machine.state is not EquipmentState.MAINTENANCE:
            self._set_state(ctx, runtime, EquipmentState.MAINTENANCE)
        complete_type = (
            EventType.CM_COMPLETE
            if job.is_corrective
            else EventType.PM_COMPLETE
        )
        complete_at = ctx.clock.time + max(job.duration, 0.0)
        ctx.queue.schedule(
            SimulationEvent(
                time=min(complete_at, ctx.horizon),
                event_type=complete_type,
                equipment_id=runtime.equipment_id,
                failure_mode_id=job.failure_mode_id,
                task_id=job.task.id,
                details={
                    "job_id": str(job.job_id),
                    "generation": job.generation,
                },
            )
        )

    def _on_cm_start(self, ctx: _SimContext, event: SimulationEvent) -> bool:
        # CM_START is logged from _begin_maintenance; nothing else.
        return True

    def _on_cm_complete(
        self, ctx: _SimContext, event: SimulationEvent
    ) -> bool:
        return self._complete_job(ctx, event, is_corrective=True)

    def _on_pm_complete(
        self, ctx: _SimContext, event: SimulationEvent
    ) -> bool:
        return self._complete_job(ctx, event, is_corrective=False)

    def _complete_job(
        self,
        ctx: _SimContext,
        event: SimulationEvent,
        *,
        is_corrective: bool,
    ) -> bool:
        runtime = ctx.equipment[event.equipment_id]  # type: ignore[index]
        job_id_str = event.details.get("job_id")
        job = None
        if job_id_str is not None:
            job = ctx.jobs.get(UUID(str(job_id_str)))
        if job is None:
            job = runtime.job
        if job is None or job.cancelled:
            return False
        if (
            event.details.get("generation") is not None
            and event.details.get("generation") != job.generation
        ):
            return False
        ready_res = ctx.resources.release(job.job_id)
        ctx.spares.release_unused(job.job_id)
        # Age accounting for running-time PM.
        if runtime.machine.state in (
            EquipmentState.UP,
            EquipmentState.POTENTIAL_FAILURE,
        ):
            pass
        operating_delta = 0.0
        if not is_corrective:
            # Approximate operating time advance since last renewal.
            operating_delta = max(
                0.0, ctx.clock.time - runtime.renewal.last_renewal_time
            )
        ctx.maintenance.apply_effect(
            job.task,
            runtime.renewal,
            ctx.clock.time,
            operating_delta=operating_delta,
        )
        if runtime.machine.state is EquipmentState.MAINTENANCE:
            self._set_state(ctx, runtime, EquipmentState.RESTORING)
        target = (
            EquipmentState.STANDBY
            if runtime.is_standby_unit
            else EquipmentState.UP
        )
        if runtime.machine.state is EquipmentState.RESTORING:
            self._set_state(ctx, runtime, target)
        elif runtime.machine.state is not target:
            # Direct path if restoring was skipped.
            if runtime.machine.state is EquipmentState.MAINTENANCE:
                self._set_state(ctx, runtime, target)
        runtime.active_failure_mode_id = None
        runtime.job = None
        ctx.jobs.pop(job.job_id, None)
        if is_corrective:
            pass
        else:
            ctx.metrics.on_pm_complete(runtime.equipment_id, ctx.clock.time)
        runtime.generation += 1
        if target is EquipmentState.UP:
            self._schedule_failures(ctx, runtime)
            self._schedule_pms(ctx, runtime)
        wake_ids = set(ready_res)
        for other in list(ctx.jobs.values()):
            if other.cancelled or other.job_id == job.job_id:
                continue
            other_rt = ctx.equipment[other.equipment_id]
            if other.job_id in wake_ids or other_rt.machine.state in (
                EquipmentState.WAITING_FOR_RESOURCE,
                EquipmentState.WAITING_FOR_SPARE,
                EquipmentState.DIAGNOSIS,
            ):
                self._try_start_work(ctx, other)
        return True

    def _on_spare_available(
        self, ctx: _SimContext, event: SimulationEvent
    ) -> bool:
        spare_id = event.spare_part_id
        if spare_id is None:
            return False
        quantity = int(event.details.get("quantity", 1))
        ready_jobs = ctx.spares.deliver(spare_id, quantity)
        for job_id in ready_jobs:
            job = ctx.jobs.get(job_id)
            if job is None:
                continue
            ctx.spares.close_wait(job_id, ctx.clock.time)
            self._try_start_work(ctx, job)
        for job in list(ctx.jobs.values()):
            rt = ctx.equipment[job.equipment_id]
            if rt.machine.state is EquipmentState.WAITING_FOR_SPARE:
                self._try_start_work(ctx, job)
        return True

    def _on_resource_available(
        self, ctx: _SimContext, event: SimulationEvent
    ) -> bool:
        for job in list(ctx.jobs.values()):
            rt = ctx.equipment[job.equipment_id]
            if rt.machine.state is EquipmentState.WAITING_FOR_RESOURCE:
                self._try_start_work(ctx, job)
        return True

    def _activate_standby(self, ctx: _SimContext, failed_id: UUID) -> None:
        for runtime in ctx.equipment.values():
            if runtime.equipment_id == failed_id:
                continue
            if runtime.machine.state is EquipmentState.STANDBY:
                self._set_state(ctx, runtime, EquipmentState.UP)
                runtime.is_standby_unit = False
                self._schedule_failures(ctx, runtime)
                self._schedule_pms(ctx, runtime)
                break

    def _set_state(
        self,
        ctx: _SimContext,
        runtime: _EquipRuntime,
        new_state: EquipmentState,
    ) -> None:
        if runtime.machine.state is new_state:
            return
        runtime.machine.transition(new_state)
        ctx.metrics.on_state_change(
            runtime.equipment_id, new_state, ctx.clock.time
        )
        ctx.metrics.log_event(
            SimulationEvent(
                time=ctx.clock.time,
                event_type=EventType.PRODUCTION_CHANGE,
                equipment_id=runtime.equipment_id,
                details={"state": new_state.value},
            )
        )

    def _capacity(self, ctx: _SimContext) -> float:
        states = {
            eq_id: rt.machine.state for eq_id, rt in ctx.equipment.items()
        }
        modes = {
            eq_id: rt.active_failure_mode_id
            for eq_id, rt in ctx.equipment.items()
        }
        return ctx.production.system_capacity(states, modes)

    def _sync_production(self, ctx: _SimContext) -> None:
        ctx.metrics.advance_production(ctx.clock.time, self._capacity(ctx))

    def _finalize(self, ctx: _SimContext) -> None:
        # False positives on diagnostic grids outside PF windows.
        fp_rng = ctx.rng.generator(4000)
        all_diag = list(ctx.model.diagnostic_tasks)
        ctx.metrics.false_positive_count = (
            ctx.diagnostics.count_false_positives(
                all_diag,
                ctx.horizon,
                fp_rng,
                excluded_windows=ctx.pf_windows,
            )
        )
        # Accrue operating time for UP equipment at horizon.
        for runtime in ctx.equipment.values():
            if runtime.machine.state in (
                EquipmentState.UP,
                EquipmentState.POTENTIAL_FAILURE,
            ):
                delta = max(
                    0.0,
                    ctx.clock.time - runtime.renewal.last_renewal_time,
                )
                runtime.renewal.operating_time += delta
        ctx.metrics.finalize(ctx.clock.time)
