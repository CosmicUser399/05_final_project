"""Unit tests for Petri model generation and conformance mapping."""

from __future__ import annotations

from app.domain.petri.conformance import events_to_conformance_log
from app.domain.petri.entities import TransitionRole
from app.domain.petri.export import to_pilot_json
from app.domain.petri.generator import PetriModelGenerator
from app.domain.petri.validation import validate_petri_structure
from app.domain.simulation.results import LoggedEvent
from tests.simulation.factories import pf_detection_model
from tests.simulation.factories import repairable_exponential_model


def test_generator_is_deterministic() -> None:
    compiled = repairable_exponential_model()
    gen = PetriModelGenerator()
    first = gen.generate(compiled)
    second = gen.generate(compiled)
    assert first.definition_dict() == second.definition_dict()


def test_opaque_ids_have_no_equipment_tags() -> None:
    compiled = repairable_exponential_model()
    model = PetriModelGenerator().generate(compiled)
    pilot = to_pilot_json(model.subnets[0])
    assert "P-101" not in pilot
    assert "Random failure" not in pilot
    assert "p0001" in pilot
    for opaque in model.id_map:
        assert opaque.startswith(("p", "t", "a"))


def test_failure_mode_and_system_subnets() -> None:
    compiled = repairable_exponential_model()
    model = PetriModelGenerator().generate(compiled)
    keys = {s.key for s in model.subnets}
    assert "system" in keys
    assert any(k.startswith("fm:") for k in keys)
    report = validate_petri_structure(model)
    assert report.is_valid, report.issues


def test_detectable_mode_has_pf_branch() -> None:
    compiled = pf_detection_model()
    model = PetriModelGenerator().generate(compiled)
    fm = next(s for s in model.subnets if s.kind == "failure_mode")
    roles = {t.role for t in fm.transitions}
    assert TransitionRole.TO_PF in roles
    assert TransitionRole.DETECT in roles
    assert TransitionRole.MISS in roles
    assert validate_petri_structure(model).is_valid


def test_conformance_maps_ram_events_to_opaque_activities() -> None:
    compiled = pf_detection_model()
    model = PetriModelGenerator().generate(compiled)
    fm_id = compiled.failure_modes[0].id
    eq_id = compiled.equipment[0].id
    events = (
        LoggedEvent(
            time_minutes=100.0,
            event_type="POTENTIAL_FAILURE",
            equipment_id=eq_id,
            failure_mode_id=fm_id,
        ),
        LoggedEvent(
            time_minutes=150.0,
            event_type="DETECTION",
            equipment_id=eq_id,
            failure_mode_id=fm_id,
        ),
        LoggedEvent(
            time_minutes=151.0,
            event_type="CM_START",
            equipment_id=eq_id,
            failure_mode_id=fm_id,
        ),
        LoggedEvent(
            time_minutes=200.0,
            event_type="CM_COMPLETE",
            equipment_id=eq_id,
            failure_mode_id=fm_id,
        ),
    )
    log = events_to_conformance_log(model, events)
    assert len(log) == 4
    assert all(item.case.startswith("fm:") for item in log)
    activities = {item.activity for item in log}
    assert activities <= set(model.id_map)
    assert "POTENTIAL_FAILURE" not in activities
