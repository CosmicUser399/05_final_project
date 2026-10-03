"""Tests for model validation levels 4 and 5."""

from __future__ import annotations

from app.domain.equipment.entities import ConnectionType
from app.domain.equipment.entities import Criticality
from app.domain.equipment.entities import EquipmentConnection
from app.domain.reliability.model_validation import validate_for_compile
from app.domain.reliability.model_validation import validate_model
from app.domain.reliability.model_validation import (
    validate_simulation_readiness,
)
from app.domain.system.content import SystemVersionContent
from tests.domain.factories import VERSION_ID
from tests.domain.factories import make_corrective_task
from tests.domain.factories import make_equipment
from tests.domain.factories import make_failure_distribution
from tests.domain.factories import make_impact
from tests.domain.factories import make_mode
from tests.domain.factories import make_task_duration
from tests.domain.factories import make_valid_content


def test_valid_content_compiles_clean() -> None:
    report = validate_for_compile(make_valid_content())
    assert report.is_valid
    assert "MISSING_FAILURE_DISTRIBUTION" not in report.codes()


def test_missing_failure_distribution_is_model_error() -> None:
    pump = make_equipment("P-101", criticality=Criticality.CRITICAL)
    mode = make_mode(pump)
    task = make_corrective_task(pump)
    content = SystemVersionContent(
        equipment=(pump,),
        failure_modes=(mode,),
        maintenance_tasks=(task,),
        maintenance_distributions=(make_task_duration(task),),
        production_impacts=(make_impact(pump),),
    )
    report = validate_model(content)
    assert "MISSING_FAILURE_DISTRIBUTION" in report.codes()
    assert not report.is_valid


def test_simulation_requires_failure_modes() -> None:
    content = SystemVersionContent(
        equipment=(make_equipment("P-101"),),
    )
    report = validate_simulation_readiness(content)
    assert "NO_FAILURE_MODES" in report.codes()


def test_unreachable_equipment_via_connections() -> None:
    a = make_equipment("A-1")
    b = make_equipment("B-1")
    orphan = make_equipment("Z-9")
    link = EquipmentConnection(
        version_id=VERSION_ID,
        source_id=a.id,
        target_id=b.id,
        connection_type=ConnectionType.PROCESS,
    )
    content = SystemVersionContent(
        equipment=(a, b, orphan),
        connections=(link,),
    )
    report = validate_model(content)
    assert "UNREACHABLE_EQUIPMENT" in report.codes()
    orphan_issues = [
        i
        for i in report.issues
        if i.code == "UNREACHABLE_EQUIPMENT" and i.entity_id == str(orphan.id)
    ]
    assert len(orphan_issues) == 1


def test_broken_connection_is_reported() -> None:
    pump = make_equipment("P-101")
    missing = make_equipment("X-1").id
    link = EquipmentConnection(
        version_id=VERSION_ID,
        source_id=pump.id,
        target_id=missing,
        connection_type=ConnectionType.PROCESS,
    )
    content = SystemVersionContent(
        equipment=(pump,),
        connections=(link,),
    )
    report = validate_model(content)
    assert "BROKEN_CONNECTION" in report.codes()


def test_repairable_without_cm_is_warning() -> None:
    pump = make_equipment("P-101", criticality=Criticality.MEDIUM)
    mode = make_mode(pump, detectable=False, pf_days=None)
    content = SystemVersionContent(
        equipment=(pump,),
        failure_modes=(mode,),
        failure_distributions=(make_failure_distribution(mode),),
    )
    report = validate_simulation_readiness(content)
    assert "REPAIRABLE_WITHOUT_CM" in report.codes()
    assert report.is_valid
    assert report.warnings
