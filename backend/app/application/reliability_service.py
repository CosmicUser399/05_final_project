"""Generate and validate compiled reliability models."""

# ruff: noqa: D102

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID
from uuid import uuid4

from sqlalchemy import select

from app.domain.equipment.entities import Criticality
from app.domain.errors import NotFoundError
from app.domain.maintenance.entities import MaintenanceDistribution
from app.domain.maintenance.entities import MaintenanceTask
from app.domain.maintenance.entities import MaintenanceTaskType
from app.domain.maintenance.entities import MaintenanceTrigger
from app.domain.production.entities import ProductionImpact
from app.domain.provenance import Provenance
from app.domain.reliability.compiled import CompiledModel
from app.domain.reliability.compiler import ReliabilityCompiler
from app.domain.reliability.distributions import Constant
from app.domain.reliability.distributions import Weibull
from app.domain.reliability.entities import FailureDistribution
from app.domain.reliability.entities import FailureMode
from app.domain.reliability.model_validation import validate_for_compile
from app.domain.reliability.pf import PFInterval
from app.domain.units import TimeUnit
from app.domain.validation import ValidationReport
from app.infrastructure.db.models import ReliabilityModelRow
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


class ReliabilityService:
    """Compile, persist and validate reliability models."""

    def __init__(
        self,
        uow_factory: Callable[[], SqlAlchemyUnitOfWork],
        compiler: ReliabilityCompiler | None = None,
    ) -> None:
        """Store dependencies."""
        self._uow_factory = uow_factory
        self._compiler = compiler or ReliabilityCompiler()

    def validate(self, version_id: UUID) -> ValidationReport:
        """Run validation levels 2-5 for a version."""
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            content = uow.content.load_content(version_id)
            return validate_for_compile(content)

    def prepare_and_generate(
        self,
        version_id: UUID,
        *,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Fill minimal FM/CM/impact drafts, then compile."""
        self._prepare_minimal(version_id)
        return self.generate(
            version_id,
            notes=notes or "compiled from prepare step",
        )

    def generate(
        self,
        version_id: UUID,
        *,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Compile and persist a reliability model snapshot."""
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            content = uow.content.load_content(version_id)
            compiled = self._compiler.compile(version_id, content)
            row = ReliabilityModelRow(
                id=uuid4(),
                version_id=version_id,
                model_hash=compiled.model_hash(),
                snapshot_json=compiled.model_dump(mode="json"),
                validation_status="VALID",
                notes=notes,
            )
            uow.session.add(row)
            uow.session.flush()
            uow.session.refresh(row)
            return row.as_dict()

    def _prepare_minimal(self, version_id: UUID) -> dict[str, int]:
        """Ensure compile-ready drafts exist for each equipment row."""
        created_fm = 0
        updated_pf = 0
        created_fd = 0
        created_cm = 0
        created_md = 0
        created_pi = 0
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            content = uow.content.load_content(version_id)
            modes_by_eq: dict[UUID, list[FailureMode]] = {}
            for mode in content.failure_modes:
                modes_by_eq.setdefault(mode.equipment_id, []).append(mode)
            dist_by_mode = {
                dist.failure_mode_id: dist
                for dist in content.failure_distributions
            }
            tasks_by_eq: dict[UUID, list[MaintenanceTask]] = {}
            for task in content.maintenance_tasks:
                tasks_by_eq.setdefault(task.equipment_id, []).append(task)
            duration_by_task = {
                dist.maintenance_task_id: dist
                for dist in content.maintenance_distributions
            }
            impacted = {
                impact.equipment_id for impact in content.production_impacts
            }
            provenance = Provenance.user_defined("prepare_minimal")

            for equipment in content.equipment:
                modes = list(modes_by_eq.get(equipment.id, []))
                if not modes:
                    mode = FailureMode(
                        version_id=version_id,
                        equipment_id=equipment.id,
                        name=f"Default failure ({equipment.tag})",
                        is_detectable=True,
                        pf_interval=PFInterval(
                            value=14,
                            unit=TimeUnit.DAYS,
                        ),
                    )
                    uow.content.save_failure_mode(mode)
                    modes = [mode]
                    modes_by_eq[equipment.id] = modes
                    created_fm += 1

                primary = modes[0]
                for mode in modes:
                    if mode.is_detectable and mode.pf_interval is None:
                        updated = mode.model_copy(
                            update={
                                "pf_interval": PFInterval(
                                    value=14,
                                    unit=TimeUnit.DAYS,
                                )
                            }
                        )
                        uow.content.save_failure_mode(updated)
                        updated_pf += 1
                        if mode.id == primary.id:
                            primary = updated
                    if mode.id not in dist_by_mode:
                        dist = FailureDistribution(
                            version_id=version_id,
                            failure_mode_id=mode.id,
                            distribution=Weibull(
                                shape=2.0,
                                scale=1000.0,
                                unit=TimeUnit.DAYS,
                            ),
                            provenance=provenance,
                        )
                        uow.content.save_failure_distribution(dist)
                        dist_by_mode[mode.id] = dist
                        created_fd += 1

                cm_tasks = [
                    task
                    for task in tasks_by_eq.get(equipment.id, [])
                    if task.task_type is MaintenanceTaskType.CORRECTIVE
                ]
                if equipment.is_repairable and not cm_tasks:
                    task = MaintenanceTask(
                        version_id=version_id,
                        equipment_id=equipment.id,
                        failure_mode_id=primary.id,
                        name=f"Corrective repair ({equipment.tag})",
                        task_type=MaintenanceTaskType.CORRECTIVE,
                        trigger=MaintenanceTrigger.ON_FAILURE,
                    )
                    uow.content.save_maintenance_task(task)
                    cm_tasks = [task]
                    tasks_by_eq.setdefault(equipment.id, []).append(task)
                    created_cm += 1

                for task in cm_tasks:
                    if task.id not in duration_by_task:
                        duration = MaintenanceDistribution(
                            version_id=version_id,
                            maintenance_task_id=task.id,
                            distribution=Constant(
                                value=10.0,
                                unit=TimeUnit.HOURS,
                            ),
                            provenance=provenance,
                        )
                        uow.content.save_maintenance_distribution(duration)
                        duration_by_task[task.id] = duration
                        created_md += 1

                needs_impact = equipment.criticality in {
                    Criticality.CRITICAL,
                    Criticality.HIGH,
                }
                if needs_impact and equipment.id not in impacted:
                    impact = ProductionImpact(
                        version_id=version_id,
                        equipment_id=equipment.id,
                        loss_fraction=1.0,
                    )
                    uow.content.save_production_impact(impact)
                    impacted.add(equipment.id)
                    created_pi += 1

        return {
            "created_failure_modes": created_fm,
            "updated_pf_intervals": updated_pf,
            "created_failure_distributions": created_fd,
            "created_corrective_tasks": created_cm,
            "created_maintenance_durations": created_md,
            "created_production_impacts": created_pi,
        }

    def get_latest(self, version_id: UUID) -> dict[str, Any] | None:
        """Return the newest reliability model for a version."""
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            row = uow.session.scalars(
                select(ReliabilityModelRow)
                .where(ReliabilityModelRow.version_id == version_id)
                .order_by(ReliabilityModelRow.generated_at.desc())
            ).first()
            return None if row is None else row.as_dict()

    def get(self, model_id: UUID) -> dict[str, Any]:
        """Return one reliability model by id."""
        with self._uow_factory() as uow:
            row = uow.session.get(ReliabilityModelRow, model_id)
            if row is None:
                raise NotFoundError(
                    "reliability model not found",
                    entity="ReliabilityModel",
                    entity_id=str(model_id),
                )
            return row.as_dict()

    def compile_only(
        self,
        version_id: UUID,
    ) -> CompiledModel:
        """Compile without persisting (for tests and overlays)."""
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            content = uow.content.load_content(version_id)
            return self._compiler.compile(version_id, content)
