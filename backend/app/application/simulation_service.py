"""Create and query Monte Carlo simulation jobs."""

# ruff: noqa: D102

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID
from uuid import uuid4

from sqlalchemy import select

from app.config import Settings
from app.config import get_settings
from app.domain.errors import NotFoundError
from app.domain.errors import SimulationError
from app.domain.errors import ValidationError
from app.domain.reliability.compiled import CompiledModel
from app.domain.reliability.compiled import ScenarioOverlay
from app.domain.simulation.config import SimulationConfiguration
from app.domain.simulation.fingerprint import configuration_hash
from app.domain.simulation.fingerprint import simulation_fingerprint
from app.domain.simulation.status import CANCELLABLE_STATUSES
from app.domain.simulation.status import SimulationRunStatus
from app.domain.units import TimeUnit
from app.domain.units import UnitConverter
from app.infrastructure.db.models import ReliabilityModelRow
from app.infrastructure.db.models import SimulationRunRow
from app.infrastructure.db.simulation_repo import SimulationRepository
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


class SimulationService:
    """Application service for simulation job lifecycle."""

    def __init__(
        self,
        uow_factory: Callable[[], SqlAlchemyUnitOfWork],
        settings: Settings | None = None,
    ) -> None:
        """Store dependencies."""
        self._uow_factory = uow_factory
        self._settings = settings or get_settings()

    def create(
        self,
        *,
        version_id: UUID,
        configuration: SimulationConfiguration,
        idempotency_key: str | None = None,
        reliability_model_id: UUID | None = None,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """Enqueue a simulation job (idempotent when key is set)."""
        self._validate_limits(configuration)
        master_seed = (
            self._settings.simulation_default_seed if seed is None else seed
        )
        cfg = configuration.model_copy(update={"random_seed": master_seed})

        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            repo = SimulationRepository(uow.session)

            if idempotency_key:
                existing = repo.get_by_idempotency_key(idempotency_key)
                if existing is not None:
                    return existing.as_status_dict()

            model_row = self._resolve_model(
                uow,
                version_id,
                reliability_model_id,
            )
            model = CompiledModel.model_validate(model_row.snapshot_json)
            scenario = ScenarioOverlay()
            model_hash = model.model_hash()
            scen_hash = scenario.scenario_hash()
            cfg_hash = configuration_hash(cfg)
            fingerprint = simulation_fingerprint(
                model_hash=model_hash,
                scenario_hash=scen_hash,
                configuration_hash_value=cfg_hash,
                seed=master_seed,
                software_version=self._settings.software_version,
            )

            cfg_row = repo.add_configuration(
                version_id=version_id,
                configuration_hash=cfg_hash,
                payload=cfg.model_dump(mode="json"),
            )
            run = SimulationRunRow(
                id=uuid4(),
                version_id=version_id,
                reliability_model_id=model_row.id,
                configuration_id=cfg_row.id,
                status=SimulationRunStatus.QUEUED.value,
                progress=0.0,
                completed_runs=0,
                total_runs=cfg.number_of_runs,
                random_seed=master_seed,
                model_hash=model_hash,
                scenario_hash=scen_hash,
                configuration_hash=cfg_hash,
                software_version=self._settings.software_version,
                simulation_fingerprint=fingerprint,
                idempotency_key=idempotency_key,
            )
            repo.add_run(run)
            return run.as_status_dict()

    def get(self, run_id: UUID) -> dict[str, Any]:
        """Return simulation status/details."""
        with self._uow_factory() as uow:
            row = SimulationRepository(uow.session).get_run(run_id)
            return row.as_status_dict()

    def get_status(self, run_id: UUID) -> dict[str, Any]:
        """Return a compact status payload."""
        return self.get(run_id)

    def get_results(self, run_id: UUID) -> dict[str, Any]:
        """Return aggregate metrics for a completed run."""
        with self._uow_factory() as uow:
            repo = SimulationRepository(uow.session)
            row = repo.get_run(run_id)
            if row.status != SimulationRunStatus.COMPLETED.value:
                raise SimulationError(
                    f"results not ready (status={row.status})",
                    code="RESULTS_NOT_READY",
                    entity="SimulationRun",
                    entity_id=str(run_id),
                )
            metrics = repo.get_system_metrics(run_id)
            if metrics is None:
                raise NotFoundError(
                    "system metrics not found",
                    entity="SystemMetrics",
                    entity_id=str(run_id),
                )
            return {
                "id": row.id,
                "status": row.status,
                "simulation_fingerprint": row.simulation_fingerprint,
                "model_hash": row.model_hash,
                "scenario_hash": row.scenario_hash,
                "configuration_hash": row.configuration_hash,
                "software_version": row.software_version,
                "random_seed": row.random_seed,
                "metrics": metrics.model_dump(mode="json"),
            }

    def get_events(
        self,
        run_id: UUID,
        *,
        offset: int = 0,
        limit: int = 100,
        event_type: str | None = None,
        equipment_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Return a page of normalized simulation events."""
        limit = min(max(limit, 1), 1000)
        offset = max(offset, 0)
        with self._uow_factory() as uow:
            repo = SimulationRepository(uow.session)
            repo.get_run(run_id)
            items = repo.list_events(
                run_id,
                offset=offset,
                limit=limit,
                event_type=event_type,
                equipment_id=equipment_id,
            )
            return {
                "items": items,
                "offset": offset,
                "limit": limit,
                "count": len(items),
            }

    def cancel(self, run_id: UUID) -> dict[str, Any]:
        """Request cancellation of a non-terminal run."""
        with self._uow_factory() as uow:
            repo = SimulationRepository(uow.session)
            row = repo.get_run(run_id)
            status = SimulationRunStatus(row.status)
            if status not in CANCELLABLE_STATUSES:
                raise SimulationError(
                    f"cannot cancel status={row.status}",
                    code="INVALID_STATUS_TRANSITION",
                    entity="SimulationRun",
                    entity_id=str(run_id),
                )
            row.status = SimulationRunStatus.CANCELLED.value
            row.error_message = "cancelled by user"
            return row.as_status_dict()

    def _validate_limits(
        self,
        configuration: SimulationConfiguration,
    ) -> None:
        settings = self._settings
        if configuration.number_of_runs > settings.simulation_max_runs:
            raise ValidationError(
                f"number_of_runs exceeds max {settings.simulation_max_runs}",
                code="SIMULATION_LIMIT",
                entity="SimulationConfiguration",
            )
        if configuration.parallel_runs > settings.simulation_max_workers:
            raise ValidationError(
                f"parallel_runs exceeds max {settings.simulation_max_workers}",
                code="SIMULATION_LIMIT",
                entity="SimulationConfiguration",
            )
        horizon_years = UnitConverter.convert_time(
            configuration.horizon,
            configuration.horizon_unit,
            TimeUnit.YEARS,
        )
        if horizon_years > settings.simulation_max_horizon_years:
            raise ValidationError(
                f"horizon exceeds max "
                f"{settings.simulation_max_horizon_years} years",
                code="SIMULATION_LIMIT",
                entity="SimulationConfiguration",
            )

    def _resolve_model(
        self,
        uow: SqlAlchemyUnitOfWork,
        version_id: UUID,
        reliability_model_id: UUID | None,
    ) -> ReliabilityModelRow:
        if reliability_model_id is not None:
            row = uow.session.get(
                ReliabilityModelRow,
                reliability_model_id,
            )
            if row is None:
                raise NotFoundError(
                    "reliability model not found",
                    entity="ReliabilityModel",
                    entity_id=str(reliability_model_id),
                )
            if row.version_id != version_id:
                raise ValidationError(
                    "reliability model belongs to another version",
                    code="MODEL_VERSION_MISMATCH",
                    entity="ReliabilityModel",
                    entity_id=str(reliability_model_id),
                )
            return row
        row = uow.session.scalars(
            select(ReliabilityModelRow)
            .where(ReliabilityModelRow.version_id == version_id)
            .order_by(ReliabilityModelRow.generated_at.desc())
        ).first()
        if row is None:
            raise SimulationError(
                "compile a reliability model before simulating",
                code="MODEL_REQUIRED",
                entity="ReliabilityModel",
                entity_id=str(version_id),
            )
        return row
