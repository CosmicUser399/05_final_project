"""Monte Carlo aggregate metrics and confidence intervals."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from app.domain.simulation.results import SimulationRunResult


class MetricSummary(BaseModel):
    """Summary statistics for one numeric metric across runs."""

    model_config = ConfigDict(frozen=True)

    mean: float | None = None
    median: float | None = None
    p5: float | None = None
    p50: float | None = None
    p95: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    sample_size: int = 0


class ProportionSummary(BaseModel):
    """Proportion with a Wilson / Clopper-Pearson interval."""

    model_config = ConfigDict(frozen=True)

    value: float | None = None
    successes: int = 0
    trials: int = 0
    ci_low: float | None = None
    ci_high: float | None = None
    method: str = "wilson"


class ParetoItem(BaseModel):
    """One contributor in a Pareto ranking."""

    model_config = ConfigDict(frozen=True)

    key: str
    count: int
    share: float


class EquipmentAggregateMetrics(BaseModel):
    """Aggregated per-equipment metrics across Monte Carlo runs."""

    model_config = ConfigDict(frozen=True)

    equipment_id: UUID
    failure_count: MetricSummary
    downtime_minutes: MetricSummary
    mtbf_minutes: MetricSummary
    mttr_minutes: MetricSummary
    ai: MetricSummary
    pm_count: MetricSummary
    cm_count: MetricSummary
    detection_count: MetricSummary


class SystemAggregateMetrics(BaseModel):
    """System-level Monte Carlo aggregates."""

    model_config = ConfigDict(frozen=True)

    number_of_runs: int
    completed_runs: int
    confidence_level: float
    reliability_at_horizon: ProportionSummary
    ai: MetricSummary
    ao: MetricSummary
    mtbf_minutes: MetricSummary
    mttr_minutes: MetricSummary
    mtbm_minutes: MetricSummary
    mdt_minutes: MetricSummary
    downtime_minutes: MetricSummary
    production_loss: MetricSummary
    production_availability: MetricSummary
    repair_p90_minutes: float | None = None
    repair_p95_minutes: float | None = None
    maintainability_at_mttr: ProportionSummary | None = None
    failure_pareto: tuple[ParetoItem, ...] = ()
    equipment: tuple[EquipmentAggregateMetrics, ...] = ()


class MonteCarloResult(BaseModel):
    """Full output of an N-run Monte Carlo campaign."""

    model_config = ConfigDict(frozen=True)

    seed: int
    model_hash: str
    scenario_hash: str
    configuration_hash: str
    software_version: str
    simulation_fingerprint: str
    aggregates: SystemAggregateMetrics
    trial_results: tuple[SimulationRunResult, ...] = Field(default=())
