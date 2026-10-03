"""Repository for scenarios, versions and changes."""

from __future__ import annotations

from typing import Any
from uuid import UUID
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.domain.errors import NotFoundError
from app.domain.reliability.compiled import ScenarioChange
from app.domain.reliability.compiled import ScenarioChangeType
from app.domain.reliability.compiled import ScenarioOverlay
from app.domain.scenarios.dto import ScenarioChangeInput
from app.domain.simulation.status import SimulationRunStatus
from app.infrastructure.db.models.scenario import ScenarioChangeRow
from app.infrastructure.db.models.scenario import ScenarioRow
from app.infrastructure.db.models.scenario import ScenarioVersionRow
from app.infrastructure.db.models.simulation import SimulationRunRow
from app.infrastructure.db.models.simulation import SystemMetricsRow


class ScenarioRepository:
    """Persist and load scenario aggregates."""

    def __init__(self, session: Session) -> None:
        """Bind a SQLAlchemy session."""
        self._session = session

    def list_for_version(self, version_id: UUID) -> list[ScenarioRow]:
        """Return scenarios for a system version (newest first)."""
        stmt = (
            select(ScenarioRow)
            .where(ScenarioRow.version_id == version_id)
            .order_by(ScenarioRow.created_at.desc())
        )
        return list(self._session.scalars(stmt).all())

    def get(self, scenario_id: UUID) -> ScenarioRow:
        """Return a scenario or raise NotFoundError."""
        row = self._session.get(ScenarioRow, scenario_id)
        if row is None:
            raise NotFoundError(
                "scenario not found",
                entity="Scenario",
                entity_id=str(scenario_id),
            )
        return row

    def get_version(
        self,
        scenario_version_id: UUID,
        *,
        with_changes: bool = True,
    ) -> ScenarioVersionRow:
        """Return a scenario version (optionally with changes)."""
        if with_changes:
            stmt = (
                select(ScenarioVersionRow)
                .where(ScenarioVersionRow.id == scenario_version_id)
                .options(selectinload(ScenarioVersionRow.changes))
            )
            row = self._session.scalars(stmt).first()
        else:
            row = self._session.get(
                ScenarioVersionRow,
                scenario_version_id,
            )
        if row is None:
            raise NotFoundError(
                "scenario version not found",
                entity="ScenarioVersion",
                entity_id=str(scenario_version_id),
            )
        return row

    def get_current_version(
        self,
        scenario_id: UUID,
    ) -> ScenarioVersionRow:
        """Return the current (latest) scenario version with changes."""
        scenario = self.get(scenario_id)
        if scenario.current_version_id is None:
            raise NotFoundError(
                "scenario has no versions",
                entity="ScenarioVersion",
                entity_id=str(scenario_id),
            )
        return self.get_version(scenario.current_version_id)

    def create_scenario(
        self,
        *,
        version_id: UUID,
        name: str,
        description: str | None,
        changes: list[ScenarioChangeInput],
        scenario_hash: str,
    ) -> ScenarioRow:
        """Insert scenario + first version + changes."""
        scenario = ScenarioRow(
            id=uuid4(),
            version_id=version_id,
            name=name,
            description=description,
        )
        self._session.add(scenario)
        self._session.flush()
        version = self._add_version(
            scenario=scenario,
            version_number=1,
            changes=changes,
            scenario_hash=scenario_hash,
        )
        scenario.current_version_id = version.id
        self._session.flush()
        return scenario

    def add_version(
        self,
        *,
        scenario_id: UUID,
        changes: list[ScenarioChangeInput],
        scenario_hash: str,
    ) -> ScenarioVersionRow:
        """Append an immutable scenario version and promote current."""
        scenario = self.get(scenario_id)
        next_number = self._next_version_number(scenario_id)
        version = self._add_version(
            scenario=scenario,
            version_number=next_number,
            changes=changes,
            scenario_hash=scenario_hash,
        )
        scenario.current_version_id = version.id
        self._session.flush()
        return version

    def overlay_for_version(
        self,
        scenario_version_id: UUID,
    ) -> ScenarioOverlay:
        """Load changes and build a runtime overlay."""
        version = self.get_version(scenario_version_id)
        changes = tuple(
            ScenarioChange(
                change_type=ScenarioChangeType(row.change_type),
                target_lineage_id=row.target_lineage_id,
                parameters=dict(row.parameters_json or {}),
            )
            for row in sorted(
                version.changes,
                key=lambda item: item.sort_order,
            )
        )
        return ScenarioOverlay(changes=changes)

    def latest_completed_run(
        self,
        *,
        version_id: UUID,
        scenario_version_id: UUID | None,
        configuration_hash: str | None = None,
    ) -> SimulationRunRow | None:
        """Find newest COMPLETED run for baseline or a scenario version."""
        stmt = (
            select(SimulationRunRow)
            .where(SimulationRunRow.version_id == version_id)
            .where(
                SimulationRunRow.status
                == SimulationRunStatus.COMPLETED.value
            )
            .order_by(SimulationRunRow.completed_at.desc())
        )
        if scenario_version_id is None:
            stmt = stmt.where(
                SimulationRunRow.scenario_version_id.is_(None)
            )
        else:
            stmt = stmt.where(
                SimulationRunRow.scenario_version_id
                == scenario_version_id
            )
        if configuration_hash is not None:
            stmt = stmt.where(
                SimulationRunRow.configuration_hash == configuration_hash
            )
        return self._session.scalars(stmt).first()

    def get_system_metrics_json(
        self,
        run_id: UUID,
    ) -> dict[str, Any] | None:
        """Return persisted system metrics JSON for a run."""
        row = self._session.scalars(
            select(SystemMetricsRow).where(
                SystemMetricsRow.simulation_run_id == run_id
            )
        ).first()
        if row is None:
            return None
        return dict(row.metrics_json)

    def scenario_as_dict(
        self,
        row: ScenarioRow,
        *,
        include_changes: bool = True,
    ) -> dict[str, Any]:
        """Serialize scenario + current version for API."""
        payload: dict[str, Any] = {
            "id": row.id,
            "version_id": row.version_id,
            "name": row.name,
            "description": row.description,
            "current_version_id": row.current_version_id,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "current_version": None,
        }
        if row.current_version_id is None:
            return payload
        version = self.get_version(
            row.current_version_id,
            with_changes=include_changes,
        )
        changes = (
            [change.as_dict() for change in version.changes]
            if include_changes
            else []
        )
        payload["current_version"] = {
            "id": version.id,
            "scenario_id": version.scenario_id,
            "version_number": version.version_number,
            "scenario_hash": version.scenario_hash,
            "created_at": version.created_at,
            "changes": changes,
        }
        return payload

    def _next_version_number(self, scenario_id: UUID) -> int:
        stmt = (
            select(ScenarioVersionRow.version_number)
            .where(ScenarioVersionRow.scenario_id == scenario_id)
            .order_by(ScenarioVersionRow.version_number.desc())
            .limit(1)
        )
        current = self._session.scalars(stmt).first()
        return 1 if current is None else int(current) + 1

    def _add_version(
        self,
        *,
        scenario: ScenarioRow,
        version_number: int,
        changes: list[ScenarioChangeInput],
        scenario_hash: str,
    ) -> ScenarioVersionRow:
        version = ScenarioVersionRow(
            id=uuid4(),
            scenario_id=scenario.id,
            version_number=version_number,
            scenario_hash=scenario_hash,
        )
        self._session.add(version)
        self._session.flush()
        for index, change in enumerate(changes):
            self._session.add(
                ScenarioChangeRow(
                    id=uuid4(),
                    scenario_version_id=version.id,
                    change_type=change.change_type.value,
                    target_lineage_id=change.target_lineage_id,
                    parameters_json=dict(change.parameters),
                    sort_order=index,
                )
            )
        self._session.flush()
        return self.get_version(version.id)
