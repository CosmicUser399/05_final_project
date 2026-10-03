"""API integration tests for P6 Petri generate/validate/analyze."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


def _create_system(client: TestClient) -> dict[str, Any]:
    response = client.post(
        "/api/v1/systems",
        json={"name": "УПП-100", "description": "Demo plant"},
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def _first_version(client: TestClient, system_id: str) -> dict[str, Any]:
    response = client.get(f"/api/v1/systems/{system_id}/versions")
    assert response.status_code == 200, response.text
    versions: list[dict[str, Any]] = response.json()
    return versions[0]


def _seed_valid_model(client: TestClient, version_id: str) -> None:
    equipment = client.post(
        f"/api/v1/versions/{version_id}/equipment",
        json={
            "tag": "P-101",
            "name": "Feed pump",
            "criticality": "CRITICAL",
        },
    )
    assert equipment.status_code == 201, equipment.text
    equipment_id = equipment.json()["id"]

    mode = client.post(
        f"/api/v1/equipment/{equipment_id}/failure-modes",
        json={
            "name": "Seal leak",
            "is_detectable": True,
            "pf_interval": {"value": 14, "unit": "DAYS"},
            "distribution": {
                "distribution": {
                    "type": "WEIBULL",
                    "shape": 2.0,
                    "scale": 1000.0,
                    "unit": "DAYS",
                },
                "provenance": {
                    "source_type": "USER_DEFINED",
                    "confidence": "MEDIUM",
                },
            },
        },
    )
    assert mode.status_code == 201, mode.text
    mode_id = mode.json()["id"]

    task = client.post(
        f"/api/v1/equipment/{equipment_id}/maintenance",
        json={
            "name": "Replace seal",
            "task_type": "CORRECTIVE",
            "trigger": "ON_FAILURE",
            "failure_mode_id": mode_id,
            "duration": {
                "distribution": {
                    "type": "CONSTANT",
                    "value": 10.0,
                    "unit": "HOURS",
                },
                "provenance": {
                    "source_type": "USER_DEFINED",
                    "confidence": "MEDIUM",
                },
            },
        },
    )
    assert task.status_code == 201, task.text

    impact = client.post(
        f"/api/v1/versions/{version_id}/production-impacts",
        json={
            "equipment_id": equipment_id,
            "loss_fraction": 1.0,
        },
    )
    assert impact.status_code == 201, impact.text


def test_generate_validate_analyze_petri(client: TestClient) -> None:
    system = _create_system(client)
    version = _first_version(client, system["id"])
    version_id = version["id"]
    _seed_valid_model(client, version_id)

    reliability = client.post(
        f"/api/v1/versions/{version_id}/reliability/generate"
    )
    assert reliability.status_code == 201, reliability.text

    generated = client.post(
        f"/api/v1/versions/{version_id}/petri/generate",
        json={"notes": "baseline petri"},
    )
    assert generated.status_code == 201, generated.text
    body = generated.json()
    assert body["version_id"] == version_id
    assert body["validation_status"] == "PENDING"
    assert body["notes"] == "baseline petri"
    assert body["reliability_model_id"] == reliability.json()["id"]
    definition = body["definition"]
    assert "id_map" in definition
    assert "subnets" in definition
    # Opaque export surface: no equipment tag leaked into id_map keys.
    assert all(key.startswith(("p", "t", "a")) for key in definition["id_map"])
    assert "P-101" not in str(definition["id_map"].keys())

    latest = client.get(f"/api/v1/versions/{version_id}/petri")
    assert latest.status_code == 200, latest.text
    assert latest.json()["id"] == body["id"]

    by_id = client.get(f"/api/v1/petri/{body['id']}")
    assert by_id.status_code == 200, by_id.text

    validated = client.post(f"/api/v1/petri/{body['id']}/validate")
    assert validated.status_code == 200, validated.text
    report = validated.json()
    assert report["validation_status"] == "VALID"
    assert report["report"]["is_valid"] is True
    assert report["subnets"]

    analyzed = client.post(
        f"/api/v1/petri/{body['id']}/analyze",
        json={"full": False},
    )
    assert analyzed.status_code == 200, analyzed.text
    assert analyzed.json()["subnets"]

    verified = client.post(
        f"/api/v1/petri/{body['id']}/verify",
        json={"properties": ["deadlock-free", "bounded"]},
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["properties"] == ["deadlock-free", "bounded"]

    canonical = client.post(f"/api/v1/petri/{body['id']}/canonical")
    assert canonical.status_code == 200, canonical.text
    assert canonical.json()["subnets"]


def test_petri_diff_and_conformance_with_empty_log(
    client: TestClient,
) -> None:
    system = _create_system(client)
    version = _first_version(client, system["id"])
    version_id = version["id"]
    _seed_valid_model(client, version_id)

    first = client.post(f"/api/v1/versions/{version_id}/petri/generate")
    assert first.status_code == 201, first.text
    second = client.post(f"/api/v1/versions/{version_id}/petri/generate")
    assert second.status_code == 201, second.text

    diff = client.post(
        f"/api/v1/petri/{first.json()['id']}/diff",
        json={"other_petri_model_id": second.json()["id"]},
    )
    assert diff.status_code == 200, diff.text
    assert "result" in diff.json()

    # Conformance without a completed run still accepts the endpoint
    # shape via a missing run -> 404 from simulation service.
    missing = client.post(
        f"/api/v1/petri/{first.json()['id']}/conformance",
        json={
            "simulation_run_id": "00000000-0000-4000-8000-000000000099",
        },
    )
    assert missing.status_code == 404, missing.text
