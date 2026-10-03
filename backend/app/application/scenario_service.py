"""Create scenarios, simulate overlays and compare results."""

# ruff: noqa: D102

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.application.simulation_service import SimulationService
from app.domain.errors import NotFoundError
from app.domain.errors import SimulationError
from app.domain.errors import ValidationError
from app.domain.reliability.compiled import CompiledModel
from app.domain.reliability.compiled import ScenarioChange
from app.domain.reliability.compiled import ScenarioOverlay
from app.domain.reliability.scenario_overlay import apply_scenario_overlay
from app.domain.scenarios.compare import compare_metrics
from app.domain.scenarios.dto import ScenarioChangeInput
from app.domain.scenarios.dto import ScenarioCreateInput
from app.domain.scenarios.dto import ScenarioVersionCreateInput
from app.domain.simulation.config import SimulationConfiguration
from app.infrastructure.db.models import ReliabilityModelRow
from app.infrastructure.db.models.simulation import SimulationRunRow
from app.infrastructure.db.scenario_repo import ScenarioRepository
from app.infrastructure.db.simulation_repo import SimulationRepository
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


class ScenarioService:
    """Application service for scenario CRUD, simulate and compare."""

    def __init__(
        self,
        uow_factory: Callable[[], SqlAlchemyUnitOfWork],
        simulation_service: SimulationService,
    ) -> None:
        """Store dependencies."""
        self._uow_factory = uow_factory
        self._simulation_service = simulation_service

    def list_for_version(self, version_id: UUID) -> list[dict[str, Any]]:
        """List scenarios for a system version."""
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            repo = ScenarioRepository(uow.session)
            rows = repo.list_for_version(version_id)
            return [
                repo.scenario_as_dict(row, include_changes=False)
                for row in rows
            ]

    def get(self, scenario_id: UUID) -> dict[str, Any]:
        """Return scenario with current version and changes."""
        with self._uow_factory() as uow:
            repo = ScenarioRepository(uow.session)
            row = repo.get(scenario_id)
            return repo.scenario_as_dict(row, include_changes=True)

    def create(
        self,
        version_id: UUID,
        payload: ScenarioCreateInput,
    ) -> dict[str, Any]:
        """Create a scenario with an initial validated change set."""
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            overlay = self._build_and_validate_overlay(
                uow,
                version_id,
                payload.changes,
            )
            repo = ScenarioRepository(uow.session)
            row = repo.create_scenario(
                version_id=version_id,
                name=payload.name,
                description=payload.description,
                changes=list(payload.changes),
                scenario_hash=overlay.scenario_hash(),
            )
            return repo.scenario_as_dict(row, include_changes=True)

    def add_version(
        self,
        scenario_id: UUID,
        payload: ScenarioVersionCreateInput,
    ) -> dict[str, Any]:
        """Append an immutable scenario version (new overlay)."""
        with self._uow_factory() as uow:
            repo = ScenarioRepository(uow.session)
            scenario = repo.get(scenario_id)
            overlay = self._build_and_validate_overlay(
                uow,
                scenario.version_id,
                payload.changes,
            )
            repo.add_version(
                scenario_id=scenario_id,
                changes=list(payload.changes),
                scenario_hash=overlay.scenario_hash(),
            )
            return repo.scenario_as_dict(
                repo.get(scenario_id),
                include_changes=True,
            )

    def simulate(
        self,
        scenario_id: UUID,
        *,
        configuration: SimulationConfiguration,
        idempotency_key: str | None = None,
        reliability_model_id: UUID | None = None,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """Enqueue a simulation that applies the current scenario overlay."""
        with self._uow_factory() as uow:
            repo = ScenarioRepository(uow.session)
            scenario = repo.get(scenario_id)
            version = repo.get_current_version(scenario_id)
            version_id = scenario.version_id
            scenario_version_id = version.id

        return self._simulation_service.create(
            version_id=version_id,
            configuration=configuration,
            idempotency_key=idempotency_key,
            reliability_model_id=reliability_model_id,
            seed=seed,
            scenario_version_id=scenario_version_id,
        )

    def compare(
        self,
        scenario_id: UUID,
        *,
        baseline_run_id: UUID | None = None,
        scenario_run_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Compare completed baseline vs scenario simulation metrics."""
        with self._uow_factory() as uow:
            repo = ScenarioRepository(uow.session)
            sim_repo = SimulationRepository(uow.session)
            scenario = repo.get(scenario_id)
            current = repo.get_current_version(scenario_id)

            scen_run = self._resolve_run(
                repo,
                sim_repo,
                run_id=scenario_run_id,
                version_id=scenario.version_id,
                scenario_version_id=current.id,
                label="scenario",
            )
            base_run = self._resolve_run(
                repo,
                sim_repo,
                run_id=baseline_run_id,
                version_id=scenario.version_id,
                scenario_version_id=None,
                label="baseline",
                prefer_configuration_hash=scen_run.configuration_hash,
            )

            base_metrics = repo.get_system_metrics_json(base_run.id)
            scen_metrics = repo.get_system_metrics_json(scen_run.id)
            if base_metrics is None or scen_metrics is None:
                raise SimulationError(
                    "system metrics missing for comparison",
                    code="RESULTS_NOT_READY",
                    entity="SystemMetrics",
                )

            comparison = compare_metrics(
                baseline_run_id=str(base_run.id),
                scenario_run_id=str(scen_run.id),
                baseline_scenario_hash=base_run.scenario_hash,
                scenario_scenario_hash=scen_run.scenario_hash,
                baseline_metrics=base_metrics,
                scenario_metrics=scen_metrics,
            )
            payload = comparison.model_dump(mode="json")
            payload["scenario_id"] = scenario.id
            payload["scenario_version_id"] = current.id
            payload["version_id"] = scenario.version_id
            return payload

    def _resolve_run(
        self,
        repo: ScenarioRepository,
        sim_repo: SimulationRepository,
        *,
        run_id: UUID | None,
        version_id: UUID,
        scenario_version_id: UUID | None,
        label: str,
        prefer_configuration_hash: str | None = None,
    ) -> SimulationRunRow:
        if run_id is not None:
            row = sim_repo.get_run(run_id)
            if row.version_id != version_id:
                raise ValidationError(
                    f"{label} run belongs to another version",
                    code="RUN_VERSION_MISMATCH",
                    entity="SimulationRun",
                    entity_id=str(run_id),
                )
            expected = scenario_version_id
            if row.scenario_version_id != expected:
                raise ValidationError(
                    f"{label} run scenario mismatch",
                    code="RUN_SCENARIO_MISMATCH",
                    entity="SimulationRun",
                    entity_id=str(run_id),
                )
            return row

        found: SimulationRunRow | None = None
        if prefer_configuration_hash is not None:
            found = repo.latest_completed_run(
                version_id=version_id,
                scenario_version_id=scenario_version_id,
                configuration_hash=prefer_configuration_hash,
            )
        if found is None:
            found = repo.latest_completed_run(
                version_id=version_id,
                scenario_version_id=scenario_version_id,
            )
        if found is None:
            raise NotFoundError(
                f"no completed {label} simulation found",
                entity="SimulationRun",
                entity_id=str(version_id),
            )
        return found

    def _build_and_validate_overlay(
        self,
        uow: SqlAlchemyUnitOfWork,
        version_id: UUID,
        changes: list[ScenarioChangeInput],
    ) -> ScenarioOverlay:
        overlay = ScenarioOverlay(
            changes=tuple(
                ScenarioChange(
                    change_type=item.change_type,
                    target_lineage_id=item.target_lineage_id,
                    parameters=dict(item.parameters),
                )
                for item in changes
            )
        )
        model_row = uow.session.scalars(
            select(ReliabilityModelRow)
            .where(ReliabilityModelRow.version_id == version_id)
            .order_by(ReliabilityModelRow.generated_at.desc())
        ).first()
        if model_row is None:
            raise ValidationError(
                "compile a reliability model before creating scenarios",
                code="MODEL_REQUIRED",
                entity="ReliabilityModel",
                entity_id=str(version_id),
            )
        model = CompiledModel.model_validate(model_row.snapshot_json)
        # Dry-run apply validates lineage targets and parameters.
        apply_scenario_overlay(model, overlay)
        return overlay
