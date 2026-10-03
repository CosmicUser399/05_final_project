"""N-run Monte Carlo orchestration (no database)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import as_completed
from typing import Any

from app.domain.errors import SimulationError
from app.domain.reliability.compiled import CompiledModel
from app.domain.reliability.compiled import ScenarioOverlay
from app.domain.simulation.aggregates import MonteCarloResult
from app.domain.simulation.config import SimulationConfiguration
from app.domain.simulation.results import SimulationRunResult
from app.simulation.engine.simulation import SimulationEngine
from app.simulation.metrics.aggregator import MetricsAggregator
from app.simulation.monte_carlo.trial import run_trial_payload

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int], None]
CancelCallback = Callable[[], bool]


class MonteCarloRunner:
    """Run N independent trials and aggregate metrics."""

    def __init__(
        self,
        *,
        software_version: str,
        max_workers: int = 4,
        aggregator: MetricsAggregator | None = None,
    ) -> None:
        """Store orchestration settings."""
        self._software_version = software_version
        self._max_workers = max(1, max_workers)
        self._aggregator = aggregator or MetricsAggregator()

    def run(
        self,
        model: CompiledModel,
        scenario: ScenarioOverlay | None,
        configuration: SimulationConfiguration,
        *,
        seed: int | None = None,
        on_progress: ProgressCallback | None = None,
        should_cancel: CancelCallback | None = None,
        keep_trial_results: bool = True,
        event_log_runs: int = 5,
    ) -> MonteCarloResult:
        """Execute ``number_of_runs`` trials and return aggregates."""
        master_seed = configuration.random_seed if seed is None else seed
        n_runs = configuration.number_of_runs
        workers = min(
            self._max_workers,
            max(1, configuration.parallel_runs),
            n_runs,
        )
        base_cfg = configuration.model_copy(
            update={
                "random_seed": master_seed,
                "collect_event_log": False,
            }
        )
        results: list[SimulationRunResult | None] = [None] * n_runs
        completed = 0

        if workers <= 1:
            engine = SimulationEngine()
            for run_id in range(n_runs):
                if should_cancel is not None and should_cancel():
                    raise SimulationError(
                        "simulation cancelled",
                        code="SIMULATION_CANCELLED",
                    )
                cfg = base_cfg.model_copy(
                    update={
                        "run_id": run_id,
                        "collect_event_log": run_id < event_log_runs,
                    }
                )
                results[run_id] = engine.run(
                    model, scenario, cfg, seed=master_seed
                )
                completed += 1
                if on_progress is not None:
                    on_progress(completed, n_runs)
        else:
            self._run_parallel(
                model=model,
                scenario=scenario,
                base_cfg=base_cfg,
                master_seed=master_seed,
                n_runs=n_runs,
                workers=workers,
                event_log_runs=event_log_runs,
                results=results,
                on_progress=on_progress,
                should_cancel=should_cancel,
            )
            completed = sum(1 for item in results if item is not None)

        if should_cancel is not None and should_cancel():
            raise SimulationError(
                "simulation cancelled",
                code="SIMULATION_CANCELLED",
            )

        finished = [item for item in results if item is not None]
        if len(finished) != n_runs:
            raise SimulationError(
                f"incomplete Monte Carlo: {len(finished)}/{n_runs}",
            )

        mc = self._aggregator.aggregate(
            finished,
            base_cfg.model_copy(update={"number_of_runs": n_runs}),
            software_version=self._software_version,
        )
        if not keep_trial_results:
            return mc.model_copy(update={"trial_results": ()})
        return mc

    def _run_parallel(
        self,
        *,
        model: CompiledModel,
        scenario: ScenarioOverlay | None,
        base_cfg: SimulationConfiguration,
        master_seed: int,
        n_runs: int,
        workers: int,
        event_log_runs: int,
        results: list[SimulationRunResult | None],
        on_progress: ProgressCallback | None,
        should_cancel: CancelCallback | None,
    ) -> None:
        model_payload = model.model_dump(mode="json")
        scenario_payload = (
            None if scenario is None else scenario.model_dump(mode="json")
        )
        payloads: list[tuple[int, dict[str, Any]]] = []
        for run_id in range(n_runs):
            cfg = base_cfg.model_copy(
                update={
                    "run_id": run_id,
                    "collect_event_log": run_id < event_log_runs,
                }
            )
            payloads.append(
                (
                    run_id,
                    {
                        "model": model_payload,
                        "scenario": scenario_payload,
                        "configuration": cfg.model_dump(mode="json"),
                        "seed": master_seed,
                    },
                )
            )

        completed = 0
        batch_size = max(workers * 2, workers)
        with ProcessPoolExecutor(max_workers=workers) as pool:
            index = 0
            while index < n_runs:
                if should_cancel is not None and should_cancel():
                    raise SimulationError(
                        "simulation cancelled",
                        code="SIMULATION_CANCELLED",
                    )
                chunk = payloads[index : index + batch_size]
                index += len(chunk)
                futures = {
                    pool.submit(run_trial_payload, payload): run_id
                    for run_id, payload in chunk
                }
                for future in as_completed(futures):
                    run_id = futures[future]
                    raw = future.result()
                    results[run_id] = SimulationRunResult.model_validate(raw)
                    completed += 1
                    if on_progress is not None:
                        on_progress(completed, n_runs)
        logger.info(
            "monte carlo parallel finished runs=%s workers=%s",
            n_runs,
            workers,
        )


__all__ = ["MonteCarloRunner"]
