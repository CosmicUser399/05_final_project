"""Golden and integration tests for SimulationEngine."""

from app.domain.reliability.compiled import ScenarioOverlay
from app.domain.simulation import SimulationConfiguration
from app.simulation import SimulationEngine
from app.simulation.events import EventType
from tests.simulation.factories import FM_ID
from tests.simulation.factories import competing_risks_model
from tests.simulation.factories import pf_detection_model
from tests.simulation.factories import pm_calendar_model
from tests.simulation.factories import production_loss_model
from tests.simulation.factories import repairable_exponential_model
from tests.simulation.factories import resource_wait_model
from tests.simulation.factories import spare_wait_model


def _config(
    horizon_hours: float,
    *,
    seed: int = 42,
    warmup_hours: float = 0.0,
) -> SimulationConfiguration:
    return SimulationConfiguration(
        horizon=horizon_hours,
        horizon_unit="HOURS",
        warmup_period=warmup_hours,
        warmup_unit="HOURS",
        random_seed=seed,
        collect_event_log=True,
        number_of_runs=1,
    )


def test_determinism_same_seed() -> None:
    model = repairable_exponential_model()
    engine = SimulationEngine()
    cfg = _config(5_000.0, seed=123)
    a = engine.run(model, ScenarioOverlay(), cfg, seed=123)
    b = engine.run(model, ScenarioOverlay(), cfg, seed=123)
    assert a.metrics == b.metrics
    assert a.events == b.events
    assert a.model_hash == b.model_hash


def test_different_seeds_differ() -> None:
    model = repairable_exponential_model()
    engine = SimulationEngine()
    a = engine.run(model, None, _config(5_000.0, seed=1), seed=1)
    b = engine.run(model, None, _config(5_000.0, seed=2), seed=2)
    assert a.events != b.events or a.metrics.failure_count != (
        b.metrics.failure_count
    )


def test_golden_p101_availability() -> None:
    """Exp MTBF=1000 h, MTTR=10 h => Ai ≈ 1000/1010."""
    model = repairable_exponential_model(mtbf_hours=1000.0, mttr_hours=10.0)
    # Long horizon so the time-average converges.
    result = SimulationEngine().run(
        model,
        None,
        _config(200_000.0, seed=2026, warmup_hours=1_000.0),
        seed=2026,
    )
    assert result.metrics.failure_count >= 50
    assert result.metrics.ai is not None
    expected = 1000.0 / 1010.0
    assert abs(result.metrics.ai - expected) < 0.03
    assert result.metrics.mtbf_minutes is not None
    assert result.metrics.mttr_minutes is not None
    # MTBF ~ 1000 h, MTTR ~ 10 h (minutes).
    assert abs(result.metrics.mtbf_minutes / 60.0 - 1000.0) < 150.0
    assert abs(result.metrics.mttr_minutes / 60.0 - 10.0) < 1.0


def test_golden_pf_detection_prevents_functional_failure() -> None:
    """T_f=1000 h, PF=100 h, check at 950 h, p=1 -> detected, no FAILURE."""
    model = pf_detection_model(
        t_f_hours=1000.0,
        pf_hours=100.0,
        diag_interval_hours=950.0,
        p_detect=1.0,
        mttr_hours=1.0,
    )
    result = SimulationEngine().run(
        model, None, _config(1_100.0, seed=7), seed=7
    )
    types = [e.event_type for e in result.events]
    assert EventType.DETECTION.value in types
    assert EventType.POTENTIAL_FAILURE.value in types
    assert EventType.FAILURE.value not in types
    assert result.metrics.detection_count == 1
    assert result.metrics.missed_detection_count == 0
    detect = next(
        e for e in result.events if e.event_type == EventType.DETECTION.value
    )
    assert detect.time_minutes == 950.0 * 60.0


def test_missed_detection_allows_failure() -> None:
    model = pf_detection_model(
        diag_interval_hours=950.0,
        p_detect=0.0,
    )
    result = SimulationEngine().run(
        model, None, _config(1_100.0, seed=7), seed=7
    )
    types = [e.event_type for e in result.events]
    assert EventType.FAILURE.value in types
    assert EventType.DETECTION.value not in types
    assert result.metrics.missed_detection_count == 1


def test_competing_risks_engine() -> None:
    model = competing_risks_model()
    result = SimulationEngine().run(
        model, None, _config(200.0, seed=1), seed=1
    )
    failure = next(
        e for e in result.events if e.event_type == EventType.FAILURE.value
    )
    assert failure.failure_mode_id == FM_ID
    assert failure.time_minutes == 100.0 * 60.0


def test_resource_waiting() -> None:
    # capacity=0 means CM cannot start until... never with current manager.
    # Use capacity=1 so repair proceeds; then a second overlapping job would
    # wait. For a single asset, verify capacity=1 completes and wait=0.
    model = resource_wait_model(capacity=1)
    result = SimulationEngine().run(model, None, _config(50.0, seed=3), seed=3)
    types = [e.event_type for e in result.events]
    assert EventType.CM_COMPLETE.value in types
    assert result.resource_wait_minutes == 0.0

    # With capacity 0 the job stays waiting (no completion).
    blocked = resource_wait_model(capacity=0)
    stuck = SimulationEngine().run(
        blocked, None, _config(50.0, seed=3), seed=3
    )
    stuck_types = [e.event_type for e in stuck.events]
    assert EventType.RESOURCE_BUSY.value in stuck_types
    assert EventType.CM_COMPLETE.value not in stuck_types
    assert stuck.metrics.downtime_minutes > 0.0


def test_spare_waiting_and_delivery() -> None:
    model = spare_wait_model(stock=0, lead_time_hours=5.0, repair_hours=1.0)
    result = SimulationEngine().run(model, None, _config(30.0, seed=5), seed=5)
    types = [e.event_type for e in result.events]
    assert EventType.SPARE_REQUEST.value in types
    assert EventType.SPARE_AVAILABLE.value in types
    assert EventType.CM_COMPLETE.value in types
    # Failure at 10 h, lead 5 h, repair 1 h -> complete at 16 h.
    complete = next(
        e for e in result.events if e.event_type == EventType.CM_COMPLETE.value
    )
    assert complete.time_minutes == 16.0 * 60.0
    assert result.spare_wait_minutes == 5.0 * 60.0


def test_production_loss() -> None:
    model = production_loss_model(nominal_rate=100.0, loss_fraction=1.0)
    # Horizon 20 h: down from 10 h to 20 h => 10 h * 100 /h loss.
    # Rate is in model units per minute? CompiledProduction.nominal_rate
    # is used as-is with minute durations in the integrator.
    # loss = nominal * (1-capacity) * duration_minutes.
    # If nominal_rate is "per hour", we should scale. The engine treats
    # nominal_rate as "per minute" of simulation time. For the test,
    # use nominal_rate in per-minute units: 100/60.
    model = production_loss_model(nominal_rate=100.0 / 60.0, loss_fraction=1.0)
    result = SimulationEngine().run(model, None, _config(20.0, seed=9), seed=9)
    # 10 hours downtime * 100 units/hour = 1000.
    assert abs(result.metrics.production_loss - 1000.0) < 1e-6
    assert result.metrics.production_availability is not None
    assert result.metrics.production_availability < 1.0


def test_preventive_maintenance_runs() -> None:
    model = pm_calendar_model(
        pm_interval_hours=50.0,
        pm_duration_hours=2.0,
        t_f_hours=10_000.0,
    )
    result = SimulationEngine().run(
        model, None, _config(120.0, seed=11), seed=11
    )
    assert result.metrics.pm_count >= 1
    types = [e.event_type for e in result.events]
    assert EventType.PM_START.value in types
    assert EventType.PM_COMPLETE.value in types
    assert EventType.FAILURE.value not in types
