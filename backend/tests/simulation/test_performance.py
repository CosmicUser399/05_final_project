"""Performance smoke: many short Monte Carlo trials."""

from __future__ import annotations

import time

import pytest

from app.domain.simulation import SimulationConfiguration
from app.simulation import MonteCarloRunner
from tests.simulation.factories import repairable_exponential_model


@pytest.mark.slow
def test_10k_short_runs_complete_reasonably_fast() -> None:
    """10k trials of a tiny horizon should finish in tens of seconds."""
    model = repairable_exponential_model()
    cfg = SimulationConfiguration(
        horizon=200,
        horizon_unit="HOURS",
        number_of_runs=10_000,
        random_seed=1,
        parallel_runs=1,
        collect_event_log=False,
    )
    runner = MonteCarloRunner(software_version="0.1.0", max_workers=1)
    started = time.perf_counter()
    result = runner.run(
        model,
        None,
        cfg,
        keep_trial_results=False,
        event_log_runs=0,
    )
    elapsed = time.perf_counter() - started
    assert result.aggregates.completed_runs == 10_000
    # Soft budget for CI machines; local should be much faster.
    assert elapsed < 120.0
