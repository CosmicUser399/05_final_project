"""Contract tests for MockPetriPilotProvider."""

from __future__ import annotations

import json

from app.application.ports import PetriPilotStatus
from app.infrastructure.mcp.mock_petri_pilot import MockPetriPilotProvider
from app.infrastructure.mcp.whitelist import PETRI_PILOT_WHITELIST

MODEL = json.dumps(
    {
        "name": "up-failed",
        "places": [{"id": "up", "initial": 1}, {"id": "failed"}],
        "transitions": [{"id": "fail"}, {"id": "repair"}],
        "arcs": [
            {"from": "up", "to": "fail"},
            {"from": "fail", "to": "failed"},
            {"from": "failed", "to": "repair"},
            {"from": "repair", "to": "up"},
        ],
    }
)


def test_whitelist_covers_runtime_tools() -> None:
    expected = {
        "petri_validate",
        "petri_analyze",
        "petri_verify",
        "petri_invariants",
        "petri_simulate",
        "petri_conformance",
        "petri_diff",
        "petri_canonical",
    }
    assert PETRI_PILOT_WHITELIST == expected


def test_mock_validate_analyze_verify_conformance() -> None:
    pilot = MockPetriPilotProvider()
    validated = pilot.validate(MODEL)
    assert validated.status is PetriPilotStatus.SUCCESS
    assert validated.data["valid"] is True

    analyzed = pilot.analyze(MODEL)
    assert analyzed.status is PetriPilotStatus.SUCCESS
    assert analyzed.data["analysis"]["has_deadlocks"] is False

    verified = pilot.verify(MODEL, ["deadlock-free", "bounded"])
    assert verified.data["ok"] is True
    assert verified.data["proved"] == 2

    log = json.dumps(
        [
            {"case": "c1", "activity": "fail"},
            {"case": "c1", "activity": "repair"},
        ]
    )
    conf = pilot.conformance(MODEL, log)
    assert conf.data["fitness"] == 1.0

    assert [c[0] for c in pilot.calls] == [
        "petri_validate",
        "petri_analyze",
        "petri_verify",
        "petri_conformance",
    ]


def test_mock_rejects_invalid_json() -> None:
    pilot = MockPetriPilotProvider()
    result = pilot.validate("{not-json")
    assert result.status is PetriPilotStatus.VALIDATION_ERROR
