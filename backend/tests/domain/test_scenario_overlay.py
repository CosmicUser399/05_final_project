"""Tests for ScenarioOverlay application and scenario_hash."""

from __future__ import annotations

import pytest

from app.domain.errors import ValidationError
from app.domain.reliability.compiled import ScenarioChange
from app.domain.reliability.compiled import ScenarioChangeType
from app.domain.reliability.compiled import ScenarioOverlay
from app.domain.reliability.compiler import ReliabilityCompiler
from app.domain.reliability.scenario_overlay import apply_scenario_overlay
from app.domain.units import TimeUnit
from tests.domain.factories import VERSION_ID
from tests.domain.factories import make_valid_content


def _compiled():
    return ReliabilityCompiler().compile(VERSION_ID, make_valid_content())


def test_scenario_hash_is_deterministic() -> None:
    diag_lineage = _compiled().diagnostic_tasks[0].lineage_id
    overlay = ScenarioOverlay(
        changes=(
            ScenarioChange(
                change_type=ScenarioChangeType.CHANGE_DIAGNOSTIC_INTERVAL,
                target_lineage_id=diag_lineage,
                parameters={"value": 30.0, "unit": "DAYS"},
            ),
        )
    )
    assert overlay.scenario_hash() == overlay.scenario_hash()
    assert len(overlay.scenario_hash()) == 64


def test_change_diagnostic_interval() -> None:
    model = _compiled()
    diag = model.diagnostic_tasks[0]
    overlay = ScenarioOverlay(
        changes=(
            ScenarioChange(
                change_type=ScenarioChangeType.CHANGE_DIAGNOSTIC_INTERVAL,
                target_lineage_id=diag.lineage_id,
                parameters={"value": 30.0, "unit": TimeUnit.DAYS},
            ),
        )
    )
    updated = apply_scenario_overlay(model, overlay)
    assert updated.diagnostic_tasks[0].interval_minutes == pytest.approx(
        30 * 1440
    )
    assert updated.model_hash() != model.model_hash()


def test_change_detection_probability() -> None:
    model = _compiled()
    diag = model.diagnostic_tasks[0]
    overlay = ScenarioOverlay(
        changes=(
            ScenarioChange(
                change_type=(ScenarioChangeType.CHANGE_DETECTION_PROBABILITY),
                target_lineage_id=diag.lineage_id,
                parameters={"detection_probability": 0.5},
            ),
        )
    )
    updated = apply_scenario_overlay(model, overlay)
    assert updated.diagnostic_tasks[0].detection_probability == 0.5


def test_disable_diagnostic_task() -> None:
    model = _compiled()
    diag = model.diagnostic_tasks[0]
    overlay = ScenarioOverlay(
        changes=(
            ScenarioChange(
                change_type=ScenarioChangeType.DISABLE_TASK,
                target_lineage_id=diag.lineage_id,
            ),
        )
    )
    updated = apply_scenario_overlay(model, overlay)
    assert updated.diagnostic_tasks == ()


def test_change_failure_parameter() -> None:
    model = _compiled()
    mode = model.failure_modes[0]
    overlay = ScenarioOverlay(
        changes=(
            ScenarioChange(
                change_type=ScenarioChangeType.CHANGE_FAILURE_PARAMETER,
                target_lineage_id=mode.lineage_id,
                parameters={"shape": 3.5},
            ),
        )
    )
    updated = apply_scenario_overlay(model, overlay)
    assert updated.failure_modes[0].distribution.shape == 3.5


def test_unknown_target_raises() -> None:
    model = _compiled()
    from uuid import uuid4

    overlay = ScenarioOverlay(
        changes=(
            ScenarioChange(
                change_type=ScenarioChangeType.CHANGE_DIAGNOSTIC_INTERVAL,
                target_lineage_id=uuid4(),
                parameters={"minutes": 100.0},
            ),
        )
    )
    with pytest.raises(ValidationError) as exc:
        apply_scenario_overlay(model, overlay)
    assert exc.value.code == "SCENARIO_TARGET_NOT_FOUND"
