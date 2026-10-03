"""Aggregate per-run results into Monte Carlo system metrics."""

from __future__ import annotations

from collections import Counter
from collections import defaultdict
from uuid import UUID

from app.domain.simulation.aggregates import EquipmentAggregateMetrics
from app.domain.simulation.aggregates import MonteCarloResult
from app.domain.simulation.aggregates import ParetoItem
from app.domain.simulation.aggregates import SystemAggregateMetrics
from app.domain.simulation.config import SimulationConfiguration
from app.domain.simulation.fingerprint import configuration_hash
from app.domain.simulation.fingerprint import simulation_fingerprint
from app.domain.simulation.results import EquipmentRunMetrics
from app.domain.simulation.results import SimulationRunResult
from app.simulation.metrics.confidence import percentile
from app.simulation.metrics.confidence import proportion_interval
from app.simulation.metrics.confidence import summarize_numeric


def _collect(
    results: list[SimulationRunResult],
    getter: object,
) -> list[float]:
    values: list[float] = []
    for result in results:
        value = getter(result)  # type: ignore[operator]
        if value is not None:
            values.append(float(value))
    return values


class MetricsAggregator:
    """Build system/equipment aggregates and CIs from trial results."""

    def aggregate(
        self,
        results: list[SimulationRunResult],
        configuration: SimulationConfiguration,
        *,
        software_version: str,
        horizon_minutes: float | None = None,
    ) -> MonteCarloResult:
        """Aggregate completed trial results."""
        if not results:
            msg = "no trial results to aggregate"
            raise ValueError(msg)

        conf = configuration.confidence_level
        horizon = (
            horizon_minutes
            if horizon_minutes is not None
            else configuration.horizon_minutes()
        )
        survivors = sum(
            1
            for r in results
            if r.metrics.first_failure_minutes is None
            or r.metrics.first_failure_minutes > horizon
        )
        reliability = proportion_interval(
            survivors,
            len(results),
            conf,
        )

        repair_samples = _collect(results, lambda r: r.metrics.mttr_minutes)
        # Maintainability at mean repair: share of runs with MTTR
        # at or below the sample mean (simple MVP proxy for M(t)).
        maint = None
        if repair_samples:
            mean_repair = sum(repair_samples) / len(repair_samples)
            ok = sum(1 for v in repair_samples if v <= mean_repair)
            maint = proportion_interval(ok, len(repair_samples), conf)

        pareto = self._failure_pareto(results)
        equipment = self._equipment_aggregates(results, conf)

        aggregates = SystemAggregateMetrics(
            number_of_runs=configuration.number_of_runs,
            completed_runs=len(results),
            confidence_level=conf,
            reliability_at_horizon=reliability,
            ai=summarize_numeric(
                _collect(results, lambda r: r.metrics.ai), conf
            ),
            ao=summarize_numeric(
                _collect(results, lambda r: r.metrics.ao), conf
            ),
            mtbf_minutes=summarize_numeric(
                _collect(results, lambda r: r.metrics.mtbf_minutes),
                conf,
            ),
            mttr_minutes=summarize_numeric(repair_samples, conf),
            mtbm_minutes=summarize_numeric(
                _collect(results, lambda r: r.metrics.mtbm_minutes),
                conf,
            ),
            mdt_minutes=summarize_numeric(
                _collect(results, lambda r: r.metrics.mdt_minutes),
                conf,
            ),
            downtime_minutes=summarize_numeric(
                _collect(results, lambda r: r.metrics.downtime_minutes),
                conf,
            ),
            production_loss=summarize_numeric(
                _collect(results, lambda r: r.metrics.production_loss),
                conf,
            ),
            production_availability=summarize_numeric(
                _collect(
                    results,
                    lambda r: r.metrics.production_availability,
                ),
                conf,
            ),
            repair_p90_minutes=percentile(repair_samples, 90),
            repair_p95_minutes=percentile(repair_samples, 95),
            maintainability_at_mttr=maint,
            failure_pareto=pareto,
            equipment=equipment,
        )

        first = results[0]
        cfg_hash = configuration_hash(configuration)
        fingerprint = simulation_fingerprint(
            model_hash=first.model_hash,
            scenario_hash=first.scenario_hash,
            configuration_hash_value=cfg_hash,
            seed=configuration.random_seed,
            software_version=software_version,
        )
        return MonteCarloResult(
            seed=configuration.random_seed,
            model_hash=first.model_hash,
            scenario_hash=first.scenario_hash,
            configuration_hash=cfg_hash,
            software_version=software_version,
            simulation_fingerprint=fingerprint,
            aggregates=aggregates,
            trial_results=tuple(results),
        )

    def _failure_pareto(
        self,
        results: list[SimulationRunResult],
    ) -> tuple[ParetoItem, ...]:
        counts: Counter[str] = Counter()
        for result in results:
            for event in result.events:
                if event.event_type != "FAILURE":
                    continue
                key = (
                    str(event.failure_mode_id)
                    if event.failure_mode_id is not None
                    else "unknown"
                )
                counts[key] += 1
        total = sum(counts.values())
        if total <= 0:
            return ()
        items = [
            ParetoItem(
                key=key,
                count=count,
                share=count / total,
            )
            for key, count in counts.most_common()
        ]
        return tuple(items)

    def _equipment_aggregates(
        self,
        results: list[SimulationRunResult],
        confidence: float,
    ) -> tuple[EquipmentAggregateMetrics, ...]:
        by_eq: dict[UUID, list[EquipmentRunMetrics]] = defaultdict(list)
        for result in results:
            for row in result.equipment_metrics:
                by_eq[row.equipment_id].append(row)
        out: list[EquipmentAggregateMetrics] = []
        for equipment_id in sorted(by_eq, key=str):
            rows = by_eq[equipment_id]
            out.append(
                EquipmentAggregateMetrics(
                    equipment_id=equipment_id,
                    failure_count=summarize_numeric(
                        [float(r.failure_count) for r in rows],
                        confidence,
                    ),
                    downtime_minutes=summarize_numeric(
                        [r.downtime_minutes for r in rows],
                        confidence,
                    ),
                    mtbf_minutes=summarize_numeric(
                        [
                            r.mtbf_minutes
                            for r in rows
                            if r.mtbf_minutes is not None
                        ],
                        confidence,
                    ),
                    mttr_minutes=summarize_numeric(
                        [
                            r.mttr_minutes
                            for r in rows
                            if r.mttr_minutes is not None
                        ],
                        confidence,
                    ),
                    ai=summarize_numeric(
                        [r.ai for r in rows if r.ai is not None],
                        confidence,
                    ),
                    pm_count=summarize_numeric(
                        [float(r.pm_count) for r in rows],
                        confidence,
                    ),
                    cm_count=summarize_numeric(
                        [float(r.cm_count) for r in rows],
                        confidence,
                    ),
                    detection_count=summarize_numeric(
                        [float(r.detection_count) for r in rows],
                        confidence,
                    ),
                )
            )
        return tuple(out)
