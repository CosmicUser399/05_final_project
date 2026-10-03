"""Tests for ReliabilityCompiler and model_hash determinism."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.equipment.entities import ConnectionType
from app.domain.equipment.entities import Criticality
from app.domain.equipment.entities import EquipmentConnection
from app.domain.errors import ValidationError
from app.domain.reliability.compiler import ReliabilityCompiler
from app.domain.system.content import SystemVersionContent
from app.domain.units import TimeUnit
from tests.domain.factories import VERSION_ID
from tests.domain.factories import make_corrective_task
from tests.domain.factories import make_diagnostic
from tests.domain.factories import make_equipment
from tests.domain.factories import make_failure_distribution
from tests.domain.factories import make_impact
from tests.domain.factories import make_mode
from tests.domain.factories import make_task_duration
from tests.domain.factories import make_valid_content


def test_compile_converts_times_to_minutes() -> None:
    content = make_valid_content()
    compiled = ReliabilityCompiler().compile(VERSION_ID, content)
    mode = compiled.failure_modes[0]
    assert mode.pf_interval_minutes == pytest.approx(14 * 1440)
    assert mode.distribution.unit is TimeUnit.MINUTES
    diag = compiled.diagnostic_tasks[0]
    assert diag.interval_minutes == pytest.approx(7 * 1440)
    task = compiled.maintenance_tasks[0]
    assert task.duration.unit is TimeUnit.MINUTES
    assert task.duration.mean() == pytest.approx(10 * 60)


def test_model_hash_is_stable_across_insertion_order() -> None:
    pump = make_equipment("P-101", criticality=Criticality.CRITICAL)
    tank = make_equipment("T-201", criticality=Criticality.MEDIUM)
    mode_p = make_mode(pump)
    mode_t = make_mode(tank, name="Leak", detectable=False, pf_days=None)
    task_p = make_corrective_task(pump)
    task_t = make_corrective_task(tank)
    link = EquipmentConnection(
        version_id=VERSION_ID,
        source_id=pump.id,
        target_id=tank.id,
        connection_type=ConnectionType.PROCESS,
    )
    dist_p = make_failure_distribution(mode_p)
    dist_t = make_failure_distribution(mode_t)
    dur_p = make_task_duration(task_p)
    dur_t = make_task_duration(task_t)
    diag = make_diagnostic(pump, mode_p)
    impact = make_impact(pump)
    forward = SystemVersionContent(
        equipment=(pump, tank),
        failure_modes=(mode_p, mode_t),
        failure_distributions=(dist_p, dist_t),
        maintenance_tasks=(task_p, task_t),
        maintenance_distributions=(dur_p, dur_t),
        diagnostic_tasks=(diag,),
        production_impacts=(impact,),
        connections=(link,),
    )
    reverse = SystemVersionContent(
        equipment=(tank, pump),
        failure_modes=(mode_t, mode_p),
        failure_distributions=(dist_t, dist_p),
        maintenance_tasks=(task_t, task_p),
        maintenance_distributions=(dur_t, dur_p),
        diagnostic_tasks=(diag,),
        production_impacts=(impact,),
        connections=(link,),
    )
    compiler = ReliabilityCompiler()
    a = compiler.compile(VERSION_ID, forward)
    b = compiler.compile(VERSION_ID, reverse)
    assert a.model_hash() == b.model_hash()
    assert a.canonical_json() == b.canonical_json()
    assert len(a.model_hash()) == 64


def test_compile_rejects_invalid_model() -> None:
    content = SystemVersionContent(
        equipment=(make_equipment("P-101"),),
    )
    with pytest.raises(ValidationError) as exc:
        ReliabilityCompiler().compile(uuid4(), content)
    assert "NO_FAILURE_MODES" in {i.code for i in exc.value.issues}


def test_compiled_model_is_frozen() -> None:
    from pydantic import ValidationError as PydanticValidationError

    compiled = ReliabilityCompiler().compile(
        VERSION_ID,
        make_valid_content(),
    )
    with pytest.raises(PydanticValidationError):
        compiled.equipment = ()  # type: ignore[misc]
