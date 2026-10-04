"""Repositories for simulation runs, metrics and event logs."""

from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import Any
from uuid import UUID
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.errors import NotFoundError
from app.domain.simulation.aggregates import MonteCarloResult
from app.domain.simulation.aggregates import SystemAggregateMetrics
from app.domain.simulation.results import LoggedEvent
from app.domain.simulation.results import SimulationRunResult
from app.domain.simulation.status import SimulationRunStatus
from app.infrastructure.db.models import DiagnosticEventRow
from app.infrastructure.db.models import EquipmentMetricsRow
from app.infrastructure.db.models import FailureEventRow
from app.infrastructure.db.models import MaintenanceEventRow
from app.infrastructure.db.models import ProductionLossEventRow
from app.infrastructure.db.models import ResourceConsumptionRow
from app.infrastructure.db.models import SimulationConfigurationRow
from app.infrastructure.db.models import SimulationRunRow
from app.infrastructure.db.models import SparePartConsumptionRow
from app.infrastructure.db.models import SystemMetricsRow

_FAILURE_TYPES = frozenset({"FAILURE", "POTENTIAL_FAILURE"})
_MAINT_TYPES = frozenset(
    {"PM_START", "PM_COMPLETE", "CM_START", "CM_COMPLETE"}
)
_DIAG_TYPES = frozenset({"DIAGNOSTIC", "DETECTION"})
_PROD_TYPES = frozenset({"PRODUCTION_CHANGE"})
_RESOURCE_TYPES = frozenset({"RESOURCE_BUSY", "RESOURCE_AVAILABLE"})
_SPARE_TYPES = frozenset({"SPARE_REQUEST", "SPARE_AVAILABLE"})


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SimulationRepository:
    """Persistence helpers for simulation jobs and results."""

    def __init__(self, session: Session) -> None:
        """Bind to a short-lived SQLAlchemy session."""
        self._session = session

    def get_run(self, run_id: UUID) -> SimulationRunRow:
        """Return a simulation run or raise ``NotFoundError``."""
        row = self._session.get(SimulationRunRow, run_id)
        if row is None:
            raise NotFoundError(
                "simulation run not found",
                entity="SimulationRun",
                entity_id=str(run_id),
            )
        return row

    def list_by_version(
        self,
        version_id: UUID,
    ) -> list[SimulationRunRow]:
        """Return runs for a system version, newest first."""
        stmt = (
            select(SimulationRunRow)
            .where(SimulationRunRow.version_id == version_id)
            .order_by(SimulationRunRow.created_at.desc())
        )
        return list(self._session.scalars(stmt))

    def get_by_idempotency_key(
        self,
        key: str,
    ) -> SimulationRunRow | None:
        """Return an existing run for an idempotency key."""
        return self._session.scalars(
            select(SimulationRunRow).where(
                SimulationRunRow.idempotency_key == key
            )
        ).first()

    def add_configuration(
        self,
        *,
        version_id: UUID,
        configuration_hash: str,
        payload: dict[str, Any],
        name: str | None = None,
    ) -> SimulationConfigurationRow:
        """Insert a configuration snapshot."""
        row = SimulationConfigurationRow(
            id=uuid4(),
            version_id=version_id,
            configuration_hash=configuration_hash,
            payload_json=payload,
            name=name,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def add_run(self, row: SimulationRunRow) -> SimulationRunRow:
        """Insert a simulation run row."""
        self._session.add(row)
        self._session.flush()
        return row

    def get_configuration(
        self,
        configuration_id: UUID,
    ) -> SimulationConfigurationRow:
        """Return a configuration row."""
        row = self._session.get(
            SimulationConfigurationRow,
            configuration_id,
        )
        if row is None:
            raise NotFoundError(
                "simulation configuration not found",
                entity="SimulationConfiguration",
                entity_id=str(configuration_id),
            )
        return row

    def update_progress(
        self,
        run_id: UUID,
        *,
        completed_runs: int,
        total_runs: int,
        status: SimulationRunStatus | None = None,
    ) -> None:
        """Update progress fields and optional status."""
        row = self.get_run(run_id)
        if row.status == SimulationRunStatus.CANCELLED.value:
            return
        row.completed_runs = completed_runs
        row.total_runs = total_runs
        row.progress = completed_runs / total_runs if total_runs > 0 else 0.0
        if status is not None:
            row.status = status.value
        row.heartbeat_at = _utcnow()
        self._session.flush()

    def mark_status(
        self,
        run_id: UUID,
        status: SimulationRunStatus,
        *,
        error_message: str | None = None,
    ) -> bool:
        """Set status unless the run is already CANCELLED.

        Returns False when CANCELLED was preserved.
        """
        row = self.get_run(run_id)
        if row.status == SimulationRunStatus.CANCELLED.value:
            return False
        row.status = status.value
        if error_message is not None:
            row.error_message = error_message
        now = _utcnow()
        row.heartbeat_at = now
        if status is SimulationRunStatus.RUNNING and row.started_at is None:
            row.started_at = now
        if status in {
            SimulationRunStatus.COMPLETED,
            SimulationRunStatus.FAILED,
            SimulationRunStatus.CANCELLED,
        }:
            row.completed_at = now
            if status is SimulationRunStatus.COMPLETED:
                row.progress = 1.0
        self._session.flush()
        return True

    def is_cancelled(self, run_id: UUID) -> bool:
        """Return whether the run was cancelled."""
        row = self.get_run(run_id)
        return row.status == SimulationRunStatus.CANCELLED.value

    def persist_aggregates(
        self,
        run_id: UUID,
        result: MonteCarloResult,
    ) -> None:
        """Store aggregate metrics and fingerprint fields."""
        row = self.get_run(run_id)
        if row.status == SimulationRunStatus.CANCELLED.value:
            return
        aggregates = result.aggregates
        row.aggregates_json = aggregates.model_dump(mode="json")
        row.model_hash = result.model_hash
        row.scenario_hash = result.scenario_hash
        row.configuration_hash = result.configuration_hash
        row.simulation_fingerprint = result.simulation_fingerprint
        row.software_version = result.software_version
        self._session.add(
            SystemMetricsRow(
                id=uuid4(),
                simulation_run_id=run_id,
                metrics_json=aggregates.model_dump(mode="json"),
            )
        )
        for eq in aggregates.equipment:
            self._session.add(
                EquipmentMetricsRow(
                    id=uuid4(),
                    simulation_run_id=run_id,
                    equipment_id=eq.equipment_id,
                    metrics_json=eq.model_dump(mode="json"),
                )
            )
        self._session.flush()

    def persist_events_batch(
        self,
        run_id: UUID,
        trials: list[SimulationRunResult],
        *,
        batch_size: int = 500,
    ) -> None:
        """Insert normalized events in short batches."""
        buffer: list[object] = []

        def flush_buffer() -> None:
            if not buffer:
                return
            self._session.add_all(buffer)
            self._session.flush()
            buffer.clear()

        for trial in trials:
            for event in trial.events:
                row = self._event_row(run_id, trial.run_id, event)
                if row is None:
                    continue
                buffer.append(row)
                if len(buffer) >= batch_size:
                    flush_buffer()
        flush_buffer()

    def list_events(
        self,
        run_id: UUID,
        *,
        offset: int = 0,
        limit: int = 100,
        event_type: str | None = None,
        equipment_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        """Return a paginated unified event list."""
        self.get_run(run_id)
        rows: list[dict[str, Any]] = []
        sources = (
            (
                FailureEventRow,
                ("equipment_id", "failure_mode_id"),
            ),
            (
                MaintenanceEventRow,
                ("equipment_id", "task_id", "failure_mode_id"),
            ),
            (
                DiagnosticEventRow,
                ("equipment_id", "task_id", "failure_mode_id"),
            ),
            (
                ProductionLossEventRow,
                ("equipment_id",),
            ),
            (
                ResourceConsumptionRow,
                ("resource_id", "equipment_id"),
            ),
            (
                SparePartConsumptionRow,
                ("spare_part_id", "equipment_id"),
            ),
        )
        for model, fields in sources:
            stmt = select(model).where(model.simulation_run_id == run_id)
            if event_type is not None:
                stmt = stmt.where(model.event_type == event_type)
            if equipment_id is not None and hasattr(model, "equipment_id"):
                stmt = stmt.where(model.equipment_id == equipment_id)
            for row in self._session.scalars(stmt):
                item: dict[str, Any] = {
                    "id": getattr(row, "id"),
                    "trial_run_id": getattr(row, "trial_run_id"),
                    "time_minutes": getattr(row, "timestamp_minutes"),
                    "event_type": getattr(row, "event_type"),
                    "details": getattr(row, "details_json"),
                }
                for field in fields:
                    item[field] = getattr(row, field)
                rows.append(item)
        rows.sort(
            key=lambda item: (
                item["time_minutes"],
                item["trial_run_id"],
                str(item["id"]),
            )
        )
        return rows[offset : offset + limit]

    def get_system_metrics(
        self,
        run_id: UUID,
    ) -> SystemAggregateMetrics | None:
        """Return persisted system aggregates."""
        row = self._session.scalars(
            select(SystemMetricsRow).where(
                SystemMetricsRow.simulation_run_id == run_id
            )
        ).first()
        if row is None:
            run = self.get_run(run_id)
            if run.aggregates_json is None:
                return None
            return SystemAggregateMetrics.model_validate(run.aggregates_json)
        return SystemAggregateMetrics.model_validate(row.metrics_json)

    def _event_row(
        self,
        run_id: UUID,
        trial_run_id: int,
        event: LoggedEvent,
    ) -> object | None:
        common = {
            "id": uuid4(),
            "simulation_run_id": run_id,
            "trial_run_id": trial_run_id,
            "timestamp_minutes": event.time_minutes,
            "event_type": event.event_type,
            "details_json": dict(event.details),
        }
        et = event.event_type
        if et in _FAILURE_TYPES:
            return FailureEventRow(
                **common,
                equipment_id=event.equipment_id,
                failure_mode_id=event.failure_mode_id,
            )
        if et in _MAINT_TYPES:
            return MaintenanceEventRow(
                **common,
                equipment_id=event.equipment_id,
                task_id=event.task_id,
                failure_mode_id=event.failure_mode_id,
            )
        if et in _DIAG_TYPES:
            return DiagnosticEventRow(
                **common,
                equipment_id=event.equipment_id,
                task_id=event.task_id,
                failure_mode_id=event.failure_mode_id,
            )
        if et in _PROD_TYPES:
            return ProductionLossEventRow(
                **common,
                equipment_id=event.equipment_id,
            )
        if et in _RESOURCE_TYPES:
            return ResourceConsumptionRow(
                **common,
                resource_id=event.resource_id,
                equipment_id=event.equipment_id,
            )
        if et in _SPARE_TYPES:
            return SparePartConsumptionRow(
                **common,
                spare_part_id=event.spare_part_id,
                equipment_id=event.equipment_id,
            )
        return None
