"""Tests for domain entities and their invariants."""

from uuid import uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.domain.diagnostics.entities import DiagnosticTask
from app.domain.equipment.entities import ConnectionType
from app.domain.equipment.entities import Criticality
from app.domain.equipment.entities import EquipmentComponent
from app.domain.equipment.entities import EquipmentConnection
from app.domain.equipment.entities import Taxonomy
from app.domain.equipment.entities import TaxonomyKind
from app.domain.equipment.entities import TaxonomyNode
from app.domain.maintenance.entities import MaintenanceEffect
from app.domain.maintenance.entities import MaintenanceEffectType
from app.domain.maintenance.entities import MaintenanceTask
from app.domain.maintenance.entities import MaintenanceTaskType
from app.domain.maintenance.entities import MaintenanceTrigger
from app.domain.production.entities import ProductionFunction
from app.domain.production.entities import ProductionImpact
from app.domain.reliability.entities import FailureMode
from app.domain.reliability.entities import ReliabilityStructure
from app.domain.reliability.entities import ReliabilityStructureMember
from app.domain.reliability.entities import StructureType
from app.domain.resources.entities import Resource
from app.domain.resources.entities import ResourceRequirement
from app.domain.resources.entities import SparePart
from app.domain.resources.entities import SparePartRequirement
from app.domain.units import MassRate
from app.domain.units import MassUnit
from app.domain.units import TimeUnit
from app.domain.units import TimeValue
from tests.domain.factories import VERSION_ID
from tests.domain.factories import make_equipment
from tests.domain.factories import make_mode

DAY = TimeUnit.DAYS


# -- equipment -------------------------------------------------------


def test_equipment_defaults_and_ids() -> None:
    eq = make_equipment("P-101")
    assert eq.id != eq.lineage_id
    assert eq.quantity == 1
    assert eq.is_repairable
    assert eq.criticality is Criticality.MEDIUM


def test_equipment_tag_is_stripped_and_required() -> None:
    assert make_equipment("  P-101 ").tag == "P-101"
    with pytest.raises(PydanticValidationError):
        make_equipment("   ")


def test_equipment_rejects_bad_quantity_and_self_parent() -> None:
    with pytest.raises(PydanticValidationError):
        make_equipment("A", quantity=0)
    eq = make_equipment("A")
    with pytest.raises(PydanticValidationError):
        eq.parent_id = eq.id


def test_equipment_validates_on_assignment() -> None:
    eq = make_equipment("A")
    with pytest.raises(PydanticValidationError):
        eq.quantity = -1
    eq.quantity = 2
    assert eq.quantity == 2


def test_clone_for_version_keeps_lineage_and_changes_id() -> None:
    eq = make_equipment("A")
    other_version = uuid4()
    clone = eq.clone_for_version(other_version)
    assert clone.id != eq.id
    assert clone.lineage_id == eq.lineage_id
    assert clone.version_id == other_version
    assert eq.version_id == VERSION_ID
    assert clone.tag == eq.tag


def test_component_and_connection_rules() -> None:
    eq = make_equipment("A")
    comp = EquipmentComponent(
        version_id=VERSION_ID, equipment_id=eq.id, name=" Seal "
    )
    assert comp.name == "Seal"
    with pytest.raises(PydanticValidationError):
        EquipmentComponent(version_id=VERSION_ID, equipment_id=eq.id, name=" ")
    with pytest.raises(PydanticValidationError):
        EquipmentConnection(
            version_id=VERSION_ID, source_id=eq.id, target_id=eq.id
        )
    link = EquipmentConnection(
        version_id=VERSION_ID, source_id=eq.id, target_id=uuid4()
    )
    assert link.connection_type is ConnectionType.PROCESS


def test_connection_types_cover_the_union() -> None:
    assert {c.value for c in ConnectionType} == {
        "PROCESS",
        "MATERIAL",
        "ENERGY",
        "ELECTRICAL",
        "CONTROL",
        "SIGNAL",
        "UTILITY",
        "DEPENDENCY",
    }


def test_taxonomy_node_cannot_be_its_own_parent() -> None:
    tax = Taxonomy(name="Business", kind=TaxonomyKind.BUSINESS)
    node = TaxonomyNode(taxonomy_id=tax.id, code="PUMP", name="Pump")
    assert node.parent_id is None
    with pytest.raises(PydanticValidationError):
        TaxonomyNode(
            id=node.id,
            taxonomy_id=tax.id,
            code="X",
            name="X",
            parent_id=node.id,
        )


# -- failure modes ---------------------------------------------------


def test_failure_mode_pf_is_embedded_value_object() -> None:
    mode = make_mode(make_equipment("A"), pf_days=14)
    assert mode.pf_interval is not None
    assert mode.pf_interval.value == 14
    assert mode.pf_interval.unit is DAY
    assert FailureMode.model_fields["pf_interval"].default is None


def test_failure_mode_rejects_invalid_pf() -> None:
    with pytest.raises(PydanticValidationError):
        FailureMode(
            version_id=VERSION_ID,
            equipment_id=uuid4(),
            name="x",
            pf_interval={"value": 0, "unit": "DAYS"},
        )


# -- maintenance -----------------------------------------------------


def _task(**kw: object) -> MaintenanceTask:
    data: dict[str, object] = {
        "version_id": VERSION_ID,
        "equipment_id": uuid4(),
        "name": "t",
        "task_type": MaintenanceTaskType.PREVENTIVE,
        "trigger": MaintenanceTrigger.CALENDAR,
        "interval": TimeValue(value=30, unit=DAY),
    }
    data.update(kw)
    return MaintenanceTask(**data)


def test_periodic_task_needs_positive_interval() -> None:
    assert _task().interval is not None
    with pytest.raises(PydanticValidationError):
        _task(interval=None)
    with pytest.raises(PydanticValidationError):
        _task(interval=TimeValue(value=0, unit=DAY))
    with pytest.raises(PydanticValidationError):
        _task(trigger=MaintenanceTrigger.RUNNING_TIME, interval=None)


def test_non_periodic_task_has_no_interval() -> None:
    task = _task(trigger=MaintenanceTrigger.CONDITION_BASED, interval=None)
    assert task.interval is None
    with pytest.raises(PydanticValidationError):
        _task(trigger=MaintenanceTrigger.ON_FAILURE)


def test_corrective_task_triggers_on_failure_only() -> None:
    ok = _task(
        task_type=MaintenanceTaskType.CORRECTIVE,
        trigger=MaintenanceTrigger.ON_FAILURE,
        interval=None,
    )
    assert ok.task_type is MaintenanceTaskType.CORRECTIVE
    with pytest.raises(PydanticValidationError):
        _task(task_type=MaintenanceTaskType.CORRECTIVE)


def test_task_types_follow_the_spec() -> None:
    assert {t.value for t in MaintenanceTaskType} == {
        "INSPECTION",
        "PREVENTIVE",
        "CORRECTIVE",
    }


def _effect(kind: MaintenanceEffectType, **kw: object) -> MaintenanceEffect:
    return MaintenanceEffect(
        version_id=VERSION_ID,
        maintenance_task_id=uuid4(),
        effect_type=kind,
        **kw,
    )


@pytest.mark.parametrize(
    "kind",
    [
        MaintenanceEffectType.RESTORE_AS_NEW,
        MaintenanceEffectType.RESTORE_AS_OLD,
        MaintenanceEffectType.RESET_FAILURE_AGE,
        MaintenanceEffectType.NONE,
    ],
)
def test_parameterless_effects(kind: MaintenanceEffectType) -> None:
    assert _effect(kind).parameter is None
    with pytest.raises(PydanticValidationError):
        _effect(kind, parameter=0.5)


@pytest.mark.parametrize(
    "kind",
    [
        MaintenanceEffectType.PARTIAL_RESTORATION,
        MaintenanceEffectType.REDUCE_REMAINING_LIFE,
    ],
)
def test_fraction_effects(kind: MaintenanceEffectType) -> None:
    assert _effect(kind, parameter=0.3).parameter == 0.3
    assert _effect(kind, parameter=1.0).parameter == 1.0
    for bad in (None, -0.1, 1.1):
        with pytest.raises(PydanticValidationError):
            _effect(kind, parameter=bad)


def test_failure_rate_multiplier_effect() -> None:
    kind = MaintenanceEffectType.CHANGE_FAILURE_RATE_MULTIPLIER
    assert _effect(kind, parameter=0.5).parameter == 0.5
    assert _effect(kind, parameter=2.0).parameter == 2.0
    for bad in (None, 0.0, -1.0):
        with pytest.raises(PydanticValidationError):
            _effect(kind, parameter=bad)


def test_eliminate_failure_mode_needs_target() -> None:
    kind = MaintenanceEffectType.ELIMINATE_FAILURE_MODE
    with pytest.raises(PydanticValidationError):
        _effect(kind)
    assert _effect(kind, failure_mode_id=uuid4()).failure_mode_id


# -- diagnostics -----------------------------------------------------


def _diag(**kw: object) -> DiagnosticTask:
    data: dict[str, object] = {
        "version_id": VERSION_ID,
        "equipment_id": uuid4(),
        "failure_mode_id": uuid4(),
        "name": "d",
        "interval": TimeValue(value=7, unit=DAY),
        "detection_probability": 0.85,
    }
    data.update(kw)
    return DiagnosticTask(**data)


def test_diagnostic_task_is_a_first_class_entity() -> None:
    diag = _diag()
    assert diag.false_positive_probability == 0.0
    assert diag.detection_probability == 0.85


@pytest.mark.parametrize("bad", [-0.01, 1.01])
def test_diagnostic_probabilities_are_in_unit_interval(bad: float) -> None:
    with pytest.raises(PydanticValidationError):
        _diag(detection_probability=bad)
    with pytest.raises(PydanticValidationError):
        _diag(false_positive_probability=bad)


def test_diagnostic_interval_must_be_positive() -> None:
    with pytest.raises(PydanticValidationError):
        _diag(interval=TimeValue(value=0, unit=DAY))


# -- resources and production ---------------------------------------


def test_resources_and_requirements() -> None:
    assert Resource(version_id=VERSION_ID, name="Crew").capacity == 1
    with pytest.raises(PydanticValidationError):
        Resource(version_id=VERSION_ID, name="Crew", capacity=0)
    with pytest.raises(PydanticValidationError):
        SparePart(version_id=VERSION_ID, name="Seal", stock=-1)
    part = SparePart(
        version_id=VERSION_ID,
        name="Seal",
        stock=2,
        lead_time=TimeValue(value=14, unit=DAY),
    )
    assert part.lead_time is not None
    with pytest.raises(PydanticValidationError):
        ResourceRequirement(
            version_id=VERSION_ID,
            maintenance_task_id=uuid4(),
            resource_id=uuid4(),
            quantity=0,
        )
    with pytest.raises(PydanticValidationError):
        SparePartRequirement(
            version_id=VERSION_ID,
            maintenance_task_id=uuid4(),
            spare_part_id=uuid4(),
            quantity=0,
        )


def test_production_function_and_impact() -> None:
    func = ProductionFunction(
        version_id=VERSION_ID,
        product="Polystyrene",
        nominal_rate=MassRate(
            value=100_000,
            mass_unit=MassUnit.TONNES,
            time_unit=TimeUnit.YEARS,
        ),
    )
    assert func.nominal_rate.to_kg_per_minute() > 0
    for bad in (-0.1, 1.1):
        with pytest.raises(PydanticValidationError):
            ProductionImpact(
                version_id=VERSION_ID,
                equipment_id=uuid4(),
                loss_fraction=bad,
            )


# -- reliability structure ------------------------------------------


def test_k_of_n_requires_k_and_others_forbid_it() -> None:
    with pytest.raises(PydanticValidationError):
        ReliabilityStructure(
            version_id=VERSION_ID,
            name="s",
            structure_type=StructureType.K_OF_N,
        )
    with pytest.raises(PydanticValidationError):
        ReliabilityStructure(
            version_id=VERSION_ID,
            name="s",
            structure_type=StructureType.SERIES,
            k=1,
        )
    ok = ReliabilityStructure(
        version_id=VERSION_ID,
        name="s",
        structure_type=StructureType.K_OF_N,
        k=2,
    )
    assert ok.k == 2


def test_structure_cannot_be_its_own_parent() -> None:
    struct = ReliabilityStructure(
        version_id=VERSION_ID, name="s", structure_type=StructureType.SERIES
    )
    with pytest.raises(PydanticValidationError):
        struct.parent_structure_id = struct.id


def test_member_has_exactly_one_target() -> None:
    sid = uuid4()
    with pytest.raises(PydanticValidationError):
        ReliabilityStructureMember(version_id=VERSION_ID, structure_id=sid)
    with pytest.raises(PydanticValidationError):
        ReliabilityStructureMember(
            version_id=VERSION_ID,
            structure_id=sid,
            equipment_id=uuid4(),
            child_structure_id=uuid4(),
        )
    with pytest.raises(PydanticValidationError):
        ReliabilityStructureMember(
            version_id=VERSION_ID, structure_id=sid, child_structure_id=sid
        )
    ok = ReliabilityStructureMember(
        version_id=VERSION_ID, structure_id=sid, equipment_id=uuid4()
    )
    assert ok.position == 0


def test_structure_types_follow_the_spec() -> None:
    assert {t.value for t in StructureType} == {
        "SERIES",
        "PARALLEL",
        "K_OF_N",
        "STANDBY",
    }
