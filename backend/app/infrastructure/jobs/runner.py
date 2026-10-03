"""Local DB-queue SimulationJobRunner (SQLite / PostgreSQL)."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy import update
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.domain.errors import SimulationError
from app.domain.reliability.compiled import CompiledModel
from app.domain.reliability.compiled import ScenarioOverlay
from app.domain.simulation.config import SimulationConfiguration
from app.domain.simulation.status import ACTIVE_STATUSES
from app.domain.simulation.status import SimulationRunStatus
from app.infrastructure.db.models import ReliabilityModelRow
from app.infrastructure.db.models import SimulationRunRow
from app.infrastructure.db.scenario_repo import ScenarioRepository
from app.infrastructure.db.simulation_repo import SimulationRepository
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.simulation.monte_carlo.runner import MonteCarloRunner

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class LocalProcessJobRunner:
    """Claim simulation jobs from ``simulation_runs`` and execute them."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        settings: Settings,
        *,
        worker_id: str | None = None,
    ) -> None:
        """Store session factory and worker identity."""
        self._session_factory = session_factory
        self._settings = settings
        self._worker_id = worker_id or f"worker-{uuid.uuid4().hex[:12]}"
        self._uow_factory: Callable[[], SqlAlchemyUnitOfWork] = lambda: (
            SqlAlchemyUnitOfWork(session_factory)
        )

    @property
    def worker_id(self) -> str:
        """Return this worker's opaque id."""
        return self._worker_id

    def reclaim_stale(self) -> int:
        """Return active jobs with expired heartbeat to ``QUEUED``."""
        timeout = timedelta(
            seconds=self._settings.simulation_heartbeat_timeout_seconds
        )
        cutoff = _utcnow() - timeout
        active = [status.value for status in ACTIVE_STATUSES]
        with self._session_factory() as session:
            stmt = (
                update(SimulationRunRow)
                .where(SimulationRunRow.status.in_(active))
                .where(SimulationRunRow.heartbeat_at.is_not(None))
                .where(SimulationRunRow.heartbeat_at < cutoff)
                .values(
                    status=SimulationRunStatus.QUEUED.value,
                    worker_id=None,
                    claimed_at=None,
                    heartbeat_at=None,
                    progress=0.0,
                    completed_runs=0,
                    error_message=None,
                )
            )
            result = session.execute(stmt)
            session.commit()
            count = int(getattr(result, "rowcount", 0) or 0)
            if count:
                logger.warning("reclaimed %s stale simulation jobs", count)
            return count

    def claim_next(self) -> UUID | None:
        """Atomically claim the oldest ``QUEUED`` job."""
        dialect = self._dialect_name()
        if dialect == "sqlite":
            row = self._claim_sqlite()
        else:
            row = self._claim_postgres()
        return None if row is None else row.id

    def heartbeat(self, run_id: UUID) -> None:
        """Touch heartbeat for an in-flight job owned by this worker."""
        with self._session_factory() as session:
            row = session.get(SimulationRunRow, run_id)
            if row is None:
                return
            if row.status == SimulationRunStatus.CANCELLED.value:
                return
            if row.worker_id != self._worker_id:
                return
            row.heartbeat_at = _utcnow()
            session.commit()

    def execute(self, run_id: UUID) -> None:
        """Run validation + Monte Carlo and persist results."""
        model, scenario, configuration = self._load_inputs(run_id)
        if self._is_cancelled(run_id):
            return

        self._set_status(run_id, SimulationRunStatus.RUNNING)

        runner = MonteCarloRunner(
            software_version=self._settings.software_version,
            max_workers=self._settings.simulation_max_workers,
        )

        def on_progress(done: int, total: int) -> None:
            with self._session_factory() as session:
                repo = SimulationRepository(session)
                if repo.is_cancelled(run_id):
                    return
                repo.update_progress(
                    run_id,
                    completed_runs=done,
                    total_runs=total,
                    status=SimulationRunStatus.RUNNING,
                )
                session.commit()

        def should_cancel() -> bool:
            return self._is_cancelled(run_id)

        try:
            result = runner.run(
                model,
                scenario,
                configuration,
                seed=configuration.random_seed,
                on_progress=on_progress,
                should_cancel=should_cancel,
                keep_trial_results=True,
                event_log_runs=self._settings.simulation_event_log_runs,
            )
        except SimulationError as exc:
            if exc.code == "SIMULATION_CANCELLED" or self._is_cancelled(
                run_id
            ):
                self._set_status(run_id, SimulationRunStatus.CANCELLED)
                return
            self._set_status(
                run_id,
                SimulationRunStatus.FAILED,
                error_message=exc.message,
            )
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("simulation %s failed", run_id)
            self._set_status(
                run_id,
                SimulationRunStatus.FAILED,
                error_message=str(exc),
            )
            return

        if self._is_cancelled(run_id):
            return

        self._set_status(run_id, SimulationRunStatus.AGGREGATING)
        batch = self._settings.simulation_result_batch_size
        with self._session_factory() as session:
            repo = SimulationRepository(session)
            if repo.is_cancelled(run_id):
                session.commit()
                return
            repo.persist_aggregates(run_id, result)
            session.commit()

        # Event log in separate short transactions (P5-04b).
        trials = list(result.trial_results)
        for start in range(0, len(trials), 1):
            if self._is_cancelled(run_id):
                return
            chunk = trials[start : start + 1]
            with self._session_factory() as session:
                repo = SimulationRepository(session)
                repo.persist_events_batch(
                    run_id,
                    chunk,
                    batch_size=batch,
                )
                session.commit()

        self._set_status(run_id, SimulationRunStatus.COMPLETED)
        logger.info(
            "simulation %s completed fingerprint=%s",
            run_id,
            result.simulation_fingerprint,
        )

    def process_once(self) -> bool:
        """Reclaim stale jobs, claim one, execute it. Return True if any."""
        self.reclaim_stale()
        claimed = self.claim_next()
        if claimed is None:
            return False
        logger.info(
            "claimed simulation %s worker=%s",
            claimed,
            self._worker_id,
        )
        self.execute(claimed)
        return True

    def _dialect_name(self) -> str:
        with self._session_factory() as session:
            return session.get_bind().dialect.name

    def _claim_sqlite(self) -> SimulationRunRow | None:
        now = _utcnow()
        with self._session_factory() as session:
            result = session.execute(
                text(
                    """
                    UPDATE simulation_runs
                    SET status = :validating,
                        worker_id = :worker_id,
                        claimed_at = :now,
                        heartbeat_at = :now
                    WHERE id = (
                        SELECT id FROM simulation_runs
                        WHERE status = :queued
                        ORDER BY created_at
                        LIMIT 1
                    )
                    AND status = :queued
                    """
                ),
                {
                    "validating": SimulationRunStatus.VALIDATING.value,
                    "queued": SimulationRunStatus.QUEUED.value,
                    "worker_id": self._worker_id,
                    "now": now.isoformat(),
                },
            )
            if int(getattr(result, "rowcount", 0) or 0) == 0:
                session.rollback()
                return None
            session.commit()
            row = session.scalars(
                select(SimulationRunRow)
                .where(
                    SimulationRunRow.worker_id == self._worker_id,
                    SimulationRunRow.status
                    == SimulationRunStatus.VALIDATING.value,
                )
                .order_by(SimulationRunRow.claimed_at.desc())
            ).first()
            if row is None:
                return None
            # Detach a lightweight copy for the caller.
            session.expunge(row)
            return row

    def _claim_postgres(self) -> SimulationRunRow | None:
        now = _utcnow()
        with self._session_factory() as session:
            selected = session.execute(
                text(
                    """
                    SELECT id FROM simulation_runs
                    WHERE status = :queued
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                    """
                ),
                {"queued": SimulationRunStatus.QUEUED.value},
            ).first()
            if selected is None:
                session.rollback()
                return None
            run_id = selected[0]
            session.execute(
                text(
                    """
                    UPDATE simulation_runs
                    SET status = :validating,
                        worker_id = :worker_id,
                        claimed_at = :now,
                        heartbeat_at = :now
                    WHERE id = :id AND status = :queued
                    """
                ),
                {
                    "validating": SimulationRunStatus.VALIDATING.value,
                    "queued": SimulationRunStatus.QUEUED.value,
                    "worker_id": self._worker_id,
                    "now": now,
                    "id": run_id,
                },
            )
            session.commit()
            row = session.get(SimulationRunRow, run_id)
            if row is None:
                return None
            session.expunge(row)
            return row

    def _load_inputs(
        self,
        run_id: UUID,
    ) -> tuple[CompiledModel, ScenarioOverlay | None, SimulationConfiguration]:
        with self._uow_factory() as uow:
            repo = SimulationRepository(uow.session)
            run = repo.get_run(run_id)
            if run.status == SimulationRunStatus.CANCELLED.value:
                raise SimulationError(
                    "simulation cancelled",
                    code="SIMULATION_CANCELLED",
                )
            cfg_row = repo.get_configuration(run.configuration_id)
            configuration = SimulationConfiguration.model_validate(
                cfg_row.payload_json
            )
            model_row: ReliabilityModelRow | None = None
            if run.reliability_model_id is not None:
                model_row = uow.session.get(
                    ReliabilityModelRow,
                    run.reliability_model_id,
                )
            if model_row is None:
                model_row = uow.session.scalars(
                    select(ReliabilityModelRow)
                    .where(ReliabilityModelRow.version_id == run.version_id)
                    .order_by(ReliabilityModelRow.generated_at.desc())
                ).first()
            if model_row is None:
                raise SimulationError(
                    "reliability model snapshot required",
                    code="MODEL_REQUIRED",
                    entity="ReliabilityModel",
                    entity_id=str(run.version_id),
                )
            model = CompiledModel.model_validate(model_row.snapshot_json)
            scenario: ScenarioOverlay | None
            if run.scenario_version_id is None:
                scenario = ScenarioOverlay()
            else:
                scenario = ScenarioRepository(uow.session).overlay_for_version(
                    run.scenario_version_id
                )
            return model, scenario, configuration

    def _set_status(
        self,
        run_id: UUID,
        status: SimulationRunStatus,
        *,
        error_message: str | None = None,
    ) -> None:
        with self._session_factory() as session:
            repo = SimulationRepository(session)
            repo.mark_status(
                run_id,
                status,
                error_message=error_message,
            )
            session.commit()

    def _is_cancelled(self, run_id: UUID) -> bool:
        with self._session_factory() as session:
            repo = SimulationRepository(session)
            return repo.is_cancelled(run_id)


class MockSimulationJobRunner:
    """In-memory mock for unit tests (no DB claim)."""

    def __init__(self) -> None:
        """Initialize empty claim log."""
        self.claimed: list[UUID] = []
        self.executed: list[UUID] = []
        self._queue: list[UUID] = []

    def enqueue(self, run_id: UUID) -> None:
        """Add a run id to the mock queue."""
        self._queue.append(run_id)

    def reclaim_stale(self) -> int:
        """No-op reclaim."""
        return 0

    def claim_next(self) -> UUID | None:
        """Pop one queued id."""
        if not self._queue:
            return None
        run_id = self._queue.pop(0)
        self.claimed.append(run_id)
        return run_id

    def heartbeat(self, run_id: UUID) -> None:
        """No-op heartbeat."""
        del run_id

    def execute(self, run_id: UUID) -> None:
        """Record execution without running the engine."""
        self.executed.append(run_id)

    def process_once(self) -> bool:
        """Claim and execute one mock job."""
        claimed = self.claim_next()
        if claimed is None:
            return False
        self.execute(claimed)
        return True
