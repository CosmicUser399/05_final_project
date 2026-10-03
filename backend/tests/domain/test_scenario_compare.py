"""Unit tests for scenario metric comparison (TZ §71)."""

from __future__ import annotations

import pytest

from app.domain.scenarios.compare import compare_metrics
from app.domain.scenarios.compare import extract_compare_metrics


def test_extract_and_compare_deltas() -> None:
    baseline = {
        "ai": {"mean": 0.90},
        "ao": {"mean": 0.88},
        "mtbf_minutes": {"mean": 1000.0},
        "mttr_minutes": {"mean": 100.0},
        "downtime_minutes": {"mean": 200.0},
        "production_loss": {"mean": 50.0},
        "production_availability": {"mean": 0.95},
        "equipment": [
            {
                "pm_count": {"mean": 2.0},
                "cm_count": {"mean": 3.0},
                "detection_count": {"mean": 4.0},
            }
        ],
    }
    scenario = {
        "ai": {"mean": 0.93},
        "ao": {"mean": 0.91},
        "mtbf_minutes": {"mean": 1100.0},
        "mttr_minutes": {"mean": 90.0},
        "downtime_minutes": {"mean": 150.0},
        "production_loss": {"mean": 40.0},
        "production_availability": {"mean": 0.97},
        "equipment": [
            {
                "pm_count": {"mean": 1.0},
                "cm_count": {"mean": 2.0},
                "detection_count": {"mean": 5.0},
            }
        ],
    }
    extracted = extract_compare_metrics(scenario)
    assert extracted["availability"] == 0.93
    assert extracted["pm_count"] == 1.0
    assert extracted["maintenance_cost"] is None

    result = compare_metrics(
        baseline_run_id="b1",
        scenario_run_id="s1",
        baseline_scenario_hash="a" * 64,
        scenario_scenario_hash="b" * 64,
        baseline_metrics=baseline,
        scenario_metrics=scenario,
    )
    assert result.deltas["availability"] == pytest.approx(0.03)
    assert result.deltas["production_loss"] == pytest.approx(-10.0)
    assert result.deltas["maintenance_cost"] is None
    by_metric = {row.metric: row for row in result.rows}
    assert by_metric["diagnostic_count"].delta == pytest.approx(1.0)
