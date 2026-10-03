"""Compare baseline vs scenario simulation aggregate metrics."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

COMPARE_METRIC_KEYS: tuple[str, ...] = (
    "availability",
    "operational_availability",
    "mtbf_minutes",
    "mttr_minutes",
    "downtime_minutes",
    "production_loss",
    "production_availability",
    "pm_count",
    "cm_count",
    "diagnostic_count",
    "maintenance_cost",
    "spare_cost",
)

DELTA_KEYS: tuple[str, ...] = (
    "availability",
    "production_loss",
    "maintenance_cost",
)


class MetricComparisonRow(BaseModel):
    """One metric with baseline, scenario and optional delta."""

    model_config = ConfigDict(frozen=True)

    metric: str
    baseline: float | None = None
    scenario: float | None = None
    delta: float | None = None


class ScenarioComparison(BaseModel):
    """Side-by-side comparison of two completed simulation runs."""

    model_config = ConfigDict(frozen=True)

    baseline_run_id: str
    scenario_run_id: str
    baseline_scenario_hash: str
    scenario_scenario_hash: str
    rows: tuple[MetricComparisonRow, ...] = ()
    deltas: dict[str, float | None] = Field(default_factory=dict)


def _summary_mean(node: Any) -> float | None:
    if node is None:
        return None
    if isinstance(node, (int, float)):
        return float(node)
    if isinstance(node, dict):
        value = node.get("mean")
        if value is None:
            value = node.get("value")
        if value is None:
            return None
        return float(value)
    mean = getattr(node, "mean", None)
    if mean is not None:
        return float(mean)
    value = getattr(node, "value", None)
    if value is not None:
        return float(value)
    return None


def _sum_equipment_metric(
    metrics: dict[str, Any],
    field: str,
) -> float | None:
    equipment = metrics.get("equipment") or ()
    total = 0.0
    found = False
    for item in equipment:
        if not isinstance(item, dict):
            continue
        value = _summary_mean(item.get(field))
        if value is None:
            continue
        total += value
        found = True
    return total if found else None


def extract_compare_metrics(
    metrics: dict[str, Any],
) -> dict[str, float | None]:
    """Map system aggregate JSON to comparison metric keys."""
    return {
        "availability": _summary_mean(metrics.get("ai")),
        "operational_availability": _summary_mean(metrics.get("ao")),
        "mtbf_minutes": _summary_mean(metrics.get("mtbf_minutes")),
        "mttr_minutes": _summary_mean(metrics.get("mttr_minutes")),
        "downtime_minutes": _summary_mean(
            metrics.get("downtime_minutes")
        ),
        "production_loss": _summary_mean(metrics.get("production_loss")),
        "production_availability": _summary_mean(
            metrics.get("production_availability")
        ),
        "pm_count": _sum_equipment_metric(metrics, "pm_count"),
        "cm_count": _sum_equipment_metric(metrics, "cm_count"),
        "diagnostic_count": _sum_equipment_metric(
            metrics,
            "detection_count",
        ),
        # Monetary costs are not modelled in MVP aggregates.
        "maintenance_cost": None,
        "spare_cost": None,
    }


def compare_metrics(
    *,
    baseline_run_id: str,
    scenario_run_id: str,
    baseline_scenario_hash: str,
    scenario_scenario_hash: str,
    baseline_metrics: dict[str, Any],
    scenario_metrics: dict[str, Any],
) -> ScenarioComparison:
    """Build TZ §71 comparison rows and key deltas."""
    base = extract_compare_metrics(baseline_metrics)
    scen = extract_compare_metrics(scenario_metrics)
    rows: list[MetricComparisonRow] = []
    for key in COMPARE_METRIC_KEYS:
        b_val = base.get(key)
        s_val = scen.get(key)
        delta: float | None = None
        if b_val is not None and s_val is not None:
            delta = s_val - b_val
        rows.append(
            MetricComparisonRow(
                metric=key,
                baseline=b_val,
                scenario=s_val,
                delta=delta,
            )
        )
    deltas: dict[str, float | None] = {}
    for key in DELTA_KEYS:
        b_val = base.get(key)
        s_val = scen.get(key)
        if b_val is None or s_val is None:
            deltas[key] = None
        else:
            deltas[key] = s_val - b_val
    return ScenarioComparison(
        baseline_run_id=baseline_run_id,
        scenario_run_id=scenario_run_id,
        baseline_scenario_hash=baseline_scenario_hash,
        scenario_scenario_hash=scenario_scenario_hash,
        rows=tuple(rows),
        deltas=deltas,
    )
