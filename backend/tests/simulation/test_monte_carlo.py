"""Monte Carlo runner, aggregator and confidence intervals."""

from __future__ import annotations

import math

import pytest

from app.domain.errors import SimulationError
from app.domain.reliability.compiled import ScenarioOverlay
from app.domain.simulation import SimulationConfiguration
from app.domain.simulation.fingerprint import configuration_hash
from app.domain.simulation.fingerprint import simulation_fingerprint
from app.simulation import MonteCarloRunner
from app.simulation.metrics.confidence import proportion_interval
from app.simulation.metrics.confidence import summarize_numeric
from app.simulation.metrics.confidence import wilson_interval
from tests.simulation.factories import repairable_exponential_model


def test_wilson_interval_bounds() -> None:
    summary = wilson_interval(95, 100, 0.95)
    assert summary.value == 0.95
    assert summary.ci_low is not None
    assert summary.ci_high is not None
    assert 0.0 <= summary.ci_low <= summary.value <= summary.ci_high <= 1.0


def test_proportion_uses_exact_for_small_n() -> None:
    summary = proportion_interval(1, 5, 0.95)
    assert summary.method == "clopper_pearson"


def test_summarize_numeric_percentiles() -> None:
    summary = summarize_numeric([1.0, 2.0, 3.0, 4.0, 5.0], 0.95)
    assert summary.mean == 3.0
    assert summary.median == 3.0
    assert summary.p50 == 3.0
    assert summary.sample_size == 5
    assert summary.ci_low is not None
    assert summary.ci_high is not None


def test_fingerprint_stable() -> None:
    cfg = SimulationConfiguration(
        horizon=1000,
        horizon_unit="HOURS",
        number_of_runs=10,
        random_seed=42,
        run_id=3,
    )
    h1 = configuration_hash(cfg)
    h2 = configuration_hash(cfg.model_copy(update={"run_id": 99}))
    assert h1 == h2
    fp = simulation_fingerprint(
        model_hash="a" * 64,
        scenario_hash="b" * 64,
        configuration_hash_value=h1,
        seed=42,
        software_version="0.1.0",
    )
    assert len(fp) == 64


def test_monte_carlo_deterministic() -> None:
    model = repairable_exponential_model()
    cfg = SimulationConfiguration(
        horizon=5_000,
        horizon_unit="HOURS",
        number_of_runs=8,
        random_seed=123,
        parallel_runs=1,
        collect_event_log=True,
    )
    runner = MonteCarloRunner(software_version="0.1.0", max_workers=1)
    a = runner.run(model, ScenarioOverlay(), cfg, event_log_runs=2)
    b = runner.run(model, ScenarioOverlay(), cfg, event_log_runs=2)
    assert a.simulation_fingerprint == b.simulation_fingerprint
    assert a.aggregates.ai.mean == b.aggregates.ai.mean
    assert len(a.trial_results) == 8
    assert a.trial_results[0].events
    # Later trials may omit event logs.
    assert a.trial_results[2].events == ()


def test_monte_carlo_ai_converges() -> None:
    """Mean Ai across runs approaches 1000/1010."""
    model = repairable_exponential_model(mtbf_hours=1000.0, mttr_hours=10.0)
    cfg = SimulationConfiguration(
        horizon=20_000,
        horizon_unit="HOURS",
        warmup_period=1_000,
        warmup_unit="HOURS",
        number_of_runs=40,
        random_seed=2026,
        parallel_runs=1,
        confidence_level=0.95,
    )
    result = MonteCarloRunner(
        software_version="0.1.0",
        max_workers=1,
    ).run(model, None, cfg, keep_trial_results=False, event_log_runs=0)
    assert result.aggregates.ai.mean is not None
    expected = 1000.0 / 1010.0
    assert abs(result.aggregates.ai.mean - expected) < 0.05
    assert result.aggregates.ai.ci_low is not None
    assert result.aggregates.ai.ci_high is not None
    assert (
        result.aggregates.ai.ci_low
        <= expected
        <= (result.aggregates.ai.ci_high + 0.05)
    )


def test_monte_carlo_progress_and_cancel() -> None:
    model = repairable_exponential_model()
    cfg = SimulationConfiguration(
        horizon=2_000,
        horizon_unit="HOURS",
        number_of_runs=20,
        random_seed=7,
        parallel_runs=1,
    )
    seen: list[tuple[int, int]] = []

    def on_progress(done: int, total: int) -> None:
        seen.append((done, total))

    cancelled = {"flag": False}

    def should_cancel() -> bool:
        return cancelled["flag"]

    runner = MonteCarloRunner(software_version="0.1.0", max_workers=1)

    def progress_then_cancel(done: int, total: int) -> None:
        seen.append((done, total))
        if done >= 3:
            cancelled["flag"] = True

    with pytest.raises(SimulationError) as exc:
        runner.run(
            model,
            None,
            cfg,
            on_progress=progress_then_cancel,
            should_cancel=should_cancel,
        )
    assert exc.value.code == "SIMULATION_CANCELLED"
    assert seen
    assert seen[-1][0] >= 3


def test_reliability_at_horizon_in_unit_interval() -> None:
    model = repairable_exponential_model()
    cfg = SimulationConfiguration(
        horizon=500,
        horizon_unit="HOURS",
        number_of_runs=25,
        random_seed=11,
        parallel_runs=1,
    )
    result = MonteCarloRunner(software_version="0.1.0", max_workers=1).run(
        model, None, cfg, keep_trial_results=False, event_log_runs=0
    )
    rel = result.aggregates.reliability_at_horizon
    assert rel.value is not None
    assert 0.0 <= rel.value <= 1.0
    assert math.isfinite(rel.value)
