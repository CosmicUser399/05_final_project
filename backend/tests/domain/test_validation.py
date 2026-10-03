"""Tests for domain and engineering validation (levels 1-3)."""

from uuid import uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.domain.diagnostics.entities import DiagnosticTask
from app.domain.equipment.entities import Criticality
from app.domain.equipment.entities import EquipmentComponent
from app.domain.equipment.entities import EquipmentConnection
from app.domain.errors import DomainError
from app.domain.errors import ModelGenerationError
from app.domain.errors import SimulationError
from app.domain.errors import ValidationError
from app.domain.maintenance.entities import MaintenanceEffect
from app.domain.maintenance.entities import MaintenanceEffectType
from app.domain.production.entities import ProductionFunction
from app.domain.production.entities import ProductionImpact
from app.domain.provenance import Provenance
from app.domain.reliability.distributions import Weibull
from app.domain.reliability.entities import FailureDistribution
from app.domain.reliability.entities import ReliabilityStructure
from app.domain.reliability.entities import ReliabilityStructureMember
from app.domain.reliability.entities import StructureType
from app.domain.resources.entities import Resource
from app.domain.resources.entities import ResourceRequirement
from app.domain.resources.entities import SparePart
from app.domain.resources.entities import SparePartRequirement
from app.domain.system.content import SystemVersionContent
from app.domain.units import MassRate
from app.domain.units import MassUnit
from app.domain.units import TimeUnit
from app.domain.units import TimeValue
from app.domain.validation import Severity
from app.domain.validation import ValidationIssue
from app.domain.validation import ValidationLevel
from app.domain.validation import ValidationReport
from app.domain.validation import schema_issues
from app.domain.validation import validate_content
from app.domain.validation import validate_domain
from app.domain.validation import validate_engineering
from tests.domain.factories import VERSION_ID
from tests.domain.factories import make_corrective_task
from tests.domain.factories import make_diagnostic
from tests.domain.factories import make_equipment
from tests.domain.factories import make_failure_distribution
from tests.domain.factories import make_impact
from tests.domain.factories import make_mode
from tests.domain.factories import make_task_duration
from tests.domain.factories import make_valid_content


def _codes(report: ValidationReport) -> frozenset[str]:
    return report.codes()


def _error_codes(report: ValidationReport) -> frozenset[str]:
    return frozenset(i.code for i in report.errors)


# -- baseline --------------------------------------------------------


def test_valid_content_has_no_issues() -> None:
    report = validate_content(make_valid_content())
    assert report.is_valid
    assert report.issues == ()
    report.raise_if_invalid()


def test_empty_content_is_valid() -> None:
    assert validate_content(SystemVersionContent()).is_valid


# -- equipment -------------------------------------------------------


def test_duplicate_tag_case_insensitive() -> None:
    a = make_equipment("P-101")
    b = make_equipment("p-101")
    c = make_equipment("P-102")
    report = validate_domain(SystemVersionContent(equipment=(a, b, c)))
    assert "DUPLICATE_TAG" in _error_codes(report)
    flagged = {i.entity_id for i in report.errors}
    assert flagged == {str(a.id), str(b.id)}


def test_unknown_parent_and_hierarchy_cycle() -> None:
    a = make_equipment("A")
    b = make_equipment("B", parent_id=a.id)
    a_cyclic = a.model_copy(update={"parent_id": b.id})
    orphan = make_equipment("C", parent_id=uuid4())
    free = make_equipment("D")
    report = validate_domain(
        SystemVersionContent(equipment=(a_cyclic, b, orphan, free))
    )
    codes = _error_codes(report)
    assert {"EQUIPMENT_HIERARCHY_CYCLE", "UNKNOWN_PARENT"} <= codes
    cycle_ids = {
        i.entity_id
        for i in report.errors
        if i.code == "EQUIPMENT_HIERARCHY_CYCLE"
    }
    assert cycle_ids == {str(a.id), str(b.id)}


def test_valid_hierarchy_has_no_issue() -> None:
    root = make_equipment("PLANT")
    child = make_equipment("P-101", parent_id=root.id)
    grandchild = make_equipment("P-101A", parent_id=child.id)
    report = validate_domain(
        SystemVersionContent(equipment=(root, child, grandchild))
    )
    assert report.is_valid


def test_component_and_connection_references() -> None:
    a = make_equipment("A")
    b = make_equipment("B")
    content = SystemVersionContent(
        equipment=(a, b),
        components=(
            EquipmentComponent(
                version_id=VERSION_ID, equipment_id=uuid4(), name="x"
            ),
        ),
        connections=(
            EquipmentConnection(
                version_id=VERSION_ID, source_id=a.id, target_id=b.id
            ),
            EquipmentConnection(
                version_id=VERSION_ID, source_id=a.id, target_id=b.id
            ),
            EquipmentConnection(
                version_id=VERSION_ID, source_id=a.id, target_id=uuid4()
            ),
        ),
    )
    codes = _error_codes(validate_domain(content))
    assert codes == {
        "COMPONENT_UNKNOWN_EQUIPMENT",
        "DUPLICATE_CONNECTION",
        "CONNECTION_UNKNOWN_ENDPOINT",
    }


# -- failure modes ---------------------------------------------------


def test_detectable_mode_requires_pf_interval() -> None:
    pump = make_equipment("P")
    mode = make_mode(pump, detectable=True, pf_days=None)
    report = validate_domain(
        SystemVersionContent(equipment=(pump,), failure_modes=(mode,))
    )
    assert "INVALID_PF_INTERVAL" in _error_codes(report)


def test_pf_on_non_detectable_mode_is_a_warning() -> None:
    pump = make_equipment("P")
    mode = make_mode(pump, detectable=False, pf_days=5)
    report = validate_domain(
        SystemVersionContent(equipment=(pump,), failure_modes=(mode,))
    )
    assert report.is_valid
    assert "PF_WITHOUT_DETECTABLE" in _codes(report)
    assert report.warnings[0].severity is Severity.WARNING


def test_failure_mode_references() -> None:
    pump = make_equipment("P")
    other = make_equipment("Q")
    comp = EquipmentComponent(
        version_id=VERSION_ID, equipment_id=other.id, name="c"
    )
    ghost = make_mode(pump).model_copy(update={"equipment_id": uuid4()})
    wrong_comp = make_mode(pump).model_copy(update={"component_id": comp.id})
    content = SystemVersionContent(
        equipment=(pump, other),
        components=(comp,),
        failure_modes=(ghost, wrong_comp),
    )
    codes = _error_codes(validate_domain(content))
    assert "FAILURE_MODE_UNKNOWN_EQUIPMENT" in codes
    assert "FAILURE_MODE_UNKNOWN_COMPONENT" in codes


def test_failure_distribution_references_and_duplicates() -> None:
    pump = make_equipment("P")
    mode = make_mode(pump)
    first = make_failure_distribution(mode)
    second = make_failure_distribution(mode)
    ghost = make_failure_distribution(mode).model_copy(
        update={"failure_mode_id": uuid4()}
    )
    content = SystemVersionContent(
        equipment=(pump,),
        failure_modes=(mode,),
        failure_distributions=(first, second, ghost),
    )
    codes = _error_codes(validate_domain(content))
    assert codes == {
        "DUPLICATE_FAILURE_DISTRIBUTION",
        "DISTRIBUTION_UNKNOWN_FAILURE_MODE",
    }


# -- maintenance -----------------------------------------------------


def test_maintenance_references() -> None:
    pump = make_equipment("P")
    other = make_equipment("Q")
    foreign_mode = make_mode(other)
    task = make_corrective_task(pump).model_copy(
        update={"failure_mode_id": foreign_mode.id}
    )
    ghost_task = make_corrective_task(pump).model_copy(
        update={"equipment_id": uuid4(), "failure_mode_id": uuid4()}
    )
    content = SystemVersionContent(
        equipment=(pump, other),
        failure_modes=(foreign_mode,),
        maintenance_tasks=(task, ghost_task),
    )
    codes = _error_codes(validate_domain(content))
    assert codes == {
        "MAINTENANCE_EQUIPMENT_MISMATCH",
        "MAINTENANCE_UNKNOWN_EQUIPMENT",
        "MAINTENANCE_UNKNOWN_FAILURE_MODE",
    }


def test_maintenance_distribution_and_effect_references() -> None:
    pump = make_equipment("P")
    task = make_corrective_task(pump)
    dist_a = make_task_duration(task)
    dist_b = make_task_duration(task)
    ghost_dist = make_task_duration(task).model_copy(
        update={"maintenance_task_id": uuid4()}
    )
    effect = MaintenanceEffect(
        version_id=VERSION_ID,
        maintenance_task_id=uuid4(),
        effect_type=MaintenanceEffectType.ELIMINATE_FAILURE_MODE,
        failure_mode_id=uuid4(),
    )
    content = SystemVersionContent(
        equipment=(pump,),
        maintenance_tasks=(task,),
        maintenance_distributions=(dist_a, dist_b, ghost_dist),
        maintenance_effects=(effect,),
    )
    codes = _error_codes(validate_domain(content))
    assert codes == {
        "DUPLICATE_MAINTENANCE_DISTRIBUTION",
        "DURATION_UNKNOWN_TASK",
        "EFFECT_UNKNOWN_TASK",
        "EFFECT_UNKNOWN_FAILURE_MODE",
    }


def test_requirement_references() -> None:
    content = SystemVersionContent(
        resource_requirements=(
            ResourceRequirement(
                version_id=VERSION_ID,
                maintenance_task_id=uuid4(),
                resource_id=uuid4(),
            ),
        ),
        spare_part_requirements=(
            SparePartRequirement(
                version_id=VERSION_ID,
                maintenance_task_id=uuid4(),
                spare_part_id=uuid4(),
            ),
        ),
    )
    codes = _error_codes(validate_domain(content))
    assert codes == {
        "REQUIREMENT_UNKNOWN_TASK",
        "REQUIREMENT_UNKNOWN_RESOURCE",
        "REQUIREMENT_UNKNOWN_SPARE_PART",
    }


# -- diagnostics -----------------------------------------------------


def test_diagnostic_references_and_detectability() -> None:
    pump = make_equipment("P")
    other = make_equipment("Q")
    blind = make_mode(pump, detectable=False, pf_days=None)
    mode_q = make_mode(other)
    content = SystemVersionContent(
        equipment=(pump, other),
        failure_modes=(blind, mode_q),
        diagnostic_tasks=(
            make_diagnostic(pump, blind),
            make_diagnostic(pump, mode_q),
            make_diagnostic(pump, blind).model_copy(
                update={"failure_mode_id": uuid4(), "equipment_id": uuid4()}
            ),
        ),
    )
    codes = _error_codes(validate_domain(content))
    assert codes == {
        "DIAGNOSTIC_ON_UNDETECTABLE_MODE",
        "DIAGNOSTIC_EQUIPMENT_MISMATCH",
        "DIAGNOSTIC_UNKNOWN_EQUIPMENT",
        "DIAGNOSTIC_UNKNOWN_FAILURE_MODE",
    }


# -- production ------------------------------------------------------


def test_production_references() -> None:
    pump = make_equipment("P")
    rate = MassRate(
        value=1, mass_unit=MassUnit.TONNES, time_unit=TimeUnit.HOURS
    )
    functions = tuple(
        ProductionFunction(
            version_id=VERSION_ID, product=f"p{i}", nominal_rate=rate
        )
        for i in range(2)
    )
    content = SystemVersionContent(
        equipment=(pump,),
        production_functions=functions,
        production_impacts=(
            ProductionImpact(
                version_id=VERSION_ID,
                equipment_id=uuid4(),
                failure_mode_id=uuid4(),
                loss_fraction=0.5,
            ),
        ),
    )
    codes = _error_codes(validate_domain(content))
    assert codes == {
        "MULTIPLE_PRODUCTION_FUNCTIONS",
        "IMPACT_UNKNOWN_EQUIPMENT",
        "IMPACT_UNKNOWN_FAILURE_MODE",
    }


# -- structures ------------------------------------------------------


def _struct(
    kind: StructureType, k: int | None = None, **kw: object
) -> ReliabilityStructure:
    return ReliabilityStructure(
        version_id=VERSION_ID,
        name="s",
        structure_type=kind,
        k=k,
        **kw,
    )


def _member(
    struct: ReliabilityStructure, eq_id: object | None = None, **kw: object
) -> ReliabilityStructureMember:
    if eq_id is None and "child_structure_id" not in kw:
        eq_id = uuid4()
    return ReliabilityStructureMember(
        version_id=VERSION_ID,
        structure_id=struct.id,
        equipment_id=eq_id,
        **kw,
    )


def test_valid_redundancy_structure() -> None:
    a = make_equipment("A")
    b = make_equipment("B")
    c = make_equipment("C")
    root = _struct(StructureType.SERIES)
    par = _struct(StructureType.PARALLEL, parent_structure_id=root.id)
    kon = _struct(StructureType.K_OF_N, k=2, parent_structure_id=root.id)
    members = (
        _member(root, child_structure_id=par.id),
        _member(root, child_structure_id=kon.id),
        _member(par, a.id),
        _member(par, b.id),
        _member(kon, a.id),
        _member(kon, b.id),
        _member(kon, c.id),
    )
    content = SystemVersionContent(
        equipment=(a, b, c),
        structures=(root, par, kon),
        structure_members=members,
    )
    assert validate_domain(content).is_valid


def test_structure_rules() -> None:
    a = make_equipment("A")
    empty = _struct(StructureType.SERIES)
    lonely = _struct(StructureType.PARALLEL)
    standby = _struct(StructureType.STANDBY)
    wide = _struct(StructureType.K_OF_N, k=3)
    orphan = _struct(StructureType.SERIES, parent_structure_id=uuid4())
    content = SystemVersionContent(
        equipment=(a,),
        structures=(empty, lonely, standby, wide, orphan),
        structure_members=(
            _member(lonely, a.id),
            _member(standby, a.id),
            _member(wide, a.id),
            _member(wide, a.id),
            _member(orphan, a.id),
        ),
    )
    report = validate_domain(content)
    by_code = {i.code: i.entity_id for i in report.errors}
    assert by_code["STRUCTURE_EMPTY"] == str(empty.id)
    assert by_code["K_OF_N_INVALID"] == str(wide.id)
    assert by_code["STRUCTURE_UNKNOWN_PARENT"] == str(orphan.id)
    too_few = {
        i.entity_id
        for i in report.errors
        if i.code == "STRUCTURE_TOO_FEW_MEMBERS"
    }
    assert too_few == {str(lonely.id), str(standby.id)}


def test_structure_cycle_and_member_references() -> None:
    a = _struct(StructureType.SERIES)
    b = _struct(StructureType.SERIES, parent_structure_id=a.id)
    a_cyclic = a.model_copy(update={"parent_structure_id": b.id})
    stray = _struct(StructureType.SERIES)
    content = SystemVersionContent(
        structures=(a_cyclic, b),
        structure_members=(
            _member(a, uuid4()),
            _member(b, uuid4()),
            _member(stray, uuid4(), position=1),
            _member(a_cyclic, child_structure_id=uuid4()),
        ),
    )
    codes = _error_codes(validate_domain(content))
    assert {
        "STRUCTURE_CYCLE",
        "MEMBER_UNKNOWN_STRUCTURE",
        "MEMBER_UNKNOWN_EQUIPMENT",
        "MEMBER_UNKNOWN_CHILD_STRUCTURE",
    } <= codes


# -- engineering -----------------------------------------------------


def test_critical_equipment_needs_production_impact() -> None:
    pump = make_equipment("P", criticality=Criticality.CRITICAL)
    report = validate_engineering(SystemVersionContent(equipment=(pump,)))
    assert _error_codes(report) == {"CRITICAL_WITHOUT_PRODUCTION_IMPACT"}
    assert all(i.level is ValidationLevel.ENGINEERING for i in report.issues)
    with_impact = SystemVersionContent(
        equipment=(pump,), production_impacts=(make_impact(pump),)
    )
    assert validate_engineering(with_impact).is_valid
    non_critical = make_equipment("Q", criticality=Criticality.HIGH)
    assert validate_engineering(
        SystemVersionContent(equipment=(non_critical,))
    ).is_valid


def test_pf_longer_than_median_life_warns() -> None:
    pump = make_equipment("P")
    mode = make_mode(pump, pf_days=900)
    dist = make_failure_distribution(mode).model_copy(
        update={
            "distribution": Weibull(
                shape=2.0, scale=1000.0, unit=TimeUnit.DAYS
            )
        }
    )
    # median = 1000 * ln(2)^0.5 ~ 832 days < PF 900 days
    report = validate_engineering(
        SystemVersionContent(
            equipment=(pump,),
            failure_modes=(mode,),
            failure_distributions=(dist,),
        )
    )
    assert report.is_valid
    assert "PF_EXCEEDS_TYPICAL_LIFE" in _codes(report)


def test_pf_comparison_uses_common_units() -> None:
    pump = make_equipment("P")
    mode = make_mode(pump, pf_days=14)
    dist = make_failure_distribution(mode).model_copy(
        update={
            "distribution": Weibull(
                shape=2.0, scale=10_000.0, unit=TimeUnit.HOURS
            )
        }
    )
    # median ~ 8326 h ~ 347 days > 14 days: no warning
    report = validate_engineering(
        SystemVersionContent(
            equipment=(pump,),
            failure_modes=(mode,),
            failure_distributions=(dist,),
        )
    )
    assert report.issues == ()


def test_diagnostic_interval_not_shorter_than_pf_warns() -> None:
    pump = make_equipment("P")
    mode = make_mode(pump, pf_days=14)
    content = SystemVersionContent(
        equipment=(pump,),
        failure_modes=(mode,),
        diagnostic_tasks=(make_diagnostic(pump, mode, interval_days=14),),
    )
    report = validate_engineering(content)
    assert "DIAGNOSTIC_INTERVAL_EXCEEDS_PF" in _codes(report)
    assert report.is_valid


def test_resource_requirement_exceeding_capacity() -> None:
    pump = make_equipment("P")
    task = make_corrective_task(pump)
    crew = Resource(version_id=VERSION_ID, name="Crew", capacity=2)
    content = SystemVersionContent(
        equipment=(pump,),
        maintenance_tasks=(task,),
        resources=(crew,),
        resource_requirements=(
            ResourceRequirement(
                version_id=VERSION_ID,
                maintenance_task_id=task.id,
                resource_id=crew.id,
                quantity=3,
            ),
        ),
    )
    report = validate_engineering(content)
    assert _error_codes(report) == {"RESOURCE_REQUIREMENT_EXCEEDS_CAPACITY"}


def test_spare_part_without_supply_warns() -> None:
    pump = make_equipment("P")
    task = make_corrective_task(pump)
    seal = SparePart(version_id=VERSION_ID, name="Seal", stock=0)
    supplied = SparePart(
        version_id=VERSION_ID,
        name="Bearing",
        stock=0,
        lead_time=TimeValue(value=7, unit=TimeUnit.DAYS),
    )
    content = SystemVersionContent(
        equipment=(pump,),
        maintenance_tasks=(task,),
        spare_parts=(seal, supplied),
        spare_part_requirements=tuple(
            SparePartRequirement(
                version_id=VERSION_ID,
                maintenance_task_id=task.id,
                spare_part_id=part.id,
            )
            for part in (seal, supplied)
        ),
    )
    report = validate_engineering(content)
    assert report.is_valid
    assert [i.code for i in report.warnings] == ["SPARE_PART_NO_SUPPLY"]


def test_synthetic_parameters_are_flagged() -> None:
    pump = make_equipment("P")
    mode = make_mode(pump, detectable=False, pf_days=None)
    synthetic = FailureDistribution(
        version_id=VERSION_ID,
        failure_mode_id=mode.id,
        distribution=Weibull(shape=2.0, scale=1000.0, unit=TimeUnit.DAYS),
        provenance=Provenance.fabricate_estimate("conv-1"),
    )
    task = make_corrective_task(pump)
    task_dist = make_task_duration(task).model_copy(
        update={"provenance": Provenance.ai_estimate("gpt")}
    )
    diag = make_diagnostic(pump, mode).model_copy(
        update={"provenance": Provenance.ai_estimate("gpt")}
    )
    report = validate_engineering(
        SystemVersionContent(
            equipment=(pump,),
            failure_modes=(mode,),
            failure_distributions=(synthetic,),
            maintenance_tasks=(task,),
            maintenance_distributions=(task_dist,),
            diagnostic_tasks=(diag,),
        )
    )
    assert report.is_valid
    flagged = [i for i in report.warnings if i.code == "SYNTHETIC_PARAMETER"]
    assert {i.entity for i in flagged} == {
        "FailureDistribution",
        "MaintenanceDistribution",
        "DiagnosticTask",
    }


# -- reports and errors ----------------------------------------------


def test_report_merge_and_raise() -> None:
    err = ValidationIssue(
        code="E1",
        message="bad",
        level=ValidationLevel.DOMAIN,
        entity="Equipment",
        entity_id="42",
    )
    warn = ValidationIssue(
        code="W1",
        message="meh",
        level=ValidationLevel.ENGINEERING,
        severity=Severity.WARNING,
    )
    merged = ValidationReport((warn,)).merge(ValidationReport((err,)))
    assert not merged.is_valid
    assert merged.codes() == {"E1", "W1"}
    with pytest.raises(ValidationError) as info:
        merged.raise_if_invalid()
    assert info.value.code == "E1"
    assert info.value.entity == "Equipment"
    assert info.value.entity_id == "42"
    assert info.value.issues == (err,)
    ValidationReport((warn,)).raise_if_invalid()


def test_schema_issues_from_pydantic_error() -> None:
    with pytest.raises(PydanticValidationError) as info:
        DiagnosticTask(
            version_id=VERSION_ID,
            equipment_id=uuid4(),
            failure_mode_id=uuid4(),
            name="d",
            interval=TimeValue(value=1, unit=TimeUnit.DAYS),
            detection_probability=1.5,
        )
    issues = schema_issues(info.value, entity="DiagnosticTask")
    assert issues
    assert issues[0].level is ValidationLevel.SCHEMA
    assert issues[0].code == "SCHEMA_ERROR"
    assert "detection_probability" in issues[0].message
    assert issues[0].entity == "DiagnosticTask"


def test_error_hierarchy_and_codes() -> None:
    assert issubclass(ValidationError, DomainError)
    assert issubclass(ModelGenerationError, DomainError)
    assert issubclass(SimulationError, DomainError)
    err = DomainError("x", code="CUSTOM", entity="E", entity_id="1")
    assert (err.code, err.entity, err.entity_id) == ("CUSTOM", "E", "1")
    assert str(err) == "x"
    assert ValidationError("y").code == "VALIDATION_ERROR"
    assert ValidationError("y").issues == ()
    assert ModelGenerationError("z").code == "MODEL_GENERATION_ERROR"
    assert SimulationError("z").code == "SIMULATION_ERROR"
