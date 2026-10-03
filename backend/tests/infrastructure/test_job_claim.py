"""Atomic claim, reclaim and cancel semantics for simulation jobs."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.domain.simulation.status import SimulationRunStatus
from app.infrastructure.db.models import SimulationConfigurationRow
from app.infrastructure.db.models import SimulationRunRow
from app.infrastructure.db.models import SystemRow
from app.infrastructure.db.models import SystemVersionRow
from app.infrastructure.db.simulation_repo import SimulationRepository
from app.infrastructure.jobs.runner import LocalProcessJobRunner
from app.infrastructure.jobs.runner import MockSimulationJobRunner


def _seed_queued_run(session: Session) -> SimulationRunRow:
    system_id = uuid4()
    version_id = uuid4()
    cfg_id = uuid4()
    run_id = uuid4()
    session.add(
        SystemRow(
            id=system_id,
            name=f"Plant-{system_id.hex[:8]}",
            description=None,
            created_by=None,
        )
    )
    session.flush()
    session.add(
        SystemVersionRow(
            id=version_id,
            system_id=system_id,
            version_number=1,
            status="DRAFT",
            lineage_id=version_id,
            comment=None,
            created_by=None,
        )
    )
    session.flush()
    session.add(
        SimulationConfigurationRow(
            id=cfg_id,
            version_id=version_id,
            configuration_hash="c" * 64,
            payload_json={"horizon": 1, "horizon_unit": "HOURS"},
        )
    )
    session.flush()
    run = SimulationRunRow(
        id=run_id,
        version_id=version_id,
        configuration_id=cfg_id,
        status=SimulationRunStatus.QUEUED.value,
        progress=0.0,
        completed_runs=0,
        total_runs=10,
        random_seed=1,
        model_hash="m" * 64,
        scenario_hash="s" * 64,
        configuration_hash="c" * 64,
        software_version="0.1.0",
        simulation_fingerprint="f" * 64,
    )
    session.add(run)
    session.commit()
    return run


def test_two_workers_do_not_claim_same_job(
    session_factory: sessionmaker[Session],
) -> None:
    settings = Settings(app_env="test", log_json=False)
    with session_factory() as session:
        run = _seed_queued_run(session)
        run_id = run.id

    w1 = LocalProcessJobRunner(
        session_factory,
        settings,
        worker_id="w1",
    )
    w2 = LocalProcessJobRunner(
        session_factory,
        settings,
        worker_id="w2",
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(w1.claim_next), pool.submit(w2.claim_next)]
        claimed = [f.result() for f in futures]

    ids = [item for item in claimed if item is not None]
    assert len(ids) == 1
    assert ids[0] == run_id
    assert claimed.count(None) == 1


def test_stale_job_is_reclaimed(
    session_factory: sessionmaker[Session],
) -> None:
    settings = Settings(
        app_env="test",
        log_json=False,
        simulation_heartbeat_timeout_seconds=30,
    )
    with session_factory() as session:
        run = _seed_queued_run(session)
        run.status = SimulationRunStatus.RUNNING.value
        run.worker_id = "dead-worker"
        run.heartbeat_at = datetime.now(UTC) - timedelta(seconds=120)
        session.commit()
        run_id = run.id

    runner = LocalProcessJobRunner(
        session_factory,
        settings,
        worker_id="alive",
    )
    assert runner.reclaim_stale() == 1
    claimed = runner.claim_next()
    assert claimed == run_id


def test_cancelled_not_overwritten_by_progress(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        run = _seed_queued_run(session)
        run.status = SimulationRunStatus.CANCELLED.value
        session.commit()
        run_id = run.id

    # Direct status write path used after execute.
    with session_factory() as session:
        repo = SimulationRepository(session)
        ok = repo.mark_status(run_id, SimulationRunStatus.COMPLETED)
        assert ok is False
        repo.update_progress(
            run_id,
            completed_runs=10,
            total_runs=10,
            status=SimulationRunStatus.RUNNING,
        )
        session.commit()
        row = repo.get_run(run_id)
        assert row.status == SimulationRunStatus.CANCELLED.value


def test_mock_job_runner_protocol() -> None:
    mock = MockSimulationJobRunner()
    run_id = uuid4()
    mock.enqueue(run_id)
    assert mock.process_once() is True
    assert mock.claimed == [run_id]
    assert mock.executed == [run_id]
    assert mock.process_once() is False
