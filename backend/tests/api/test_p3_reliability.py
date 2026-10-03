"""API integration tests for P3 reliability validate/generate."""

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


def _seed_valid_model(client: TestClient, version_id: str) -> str:
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
    return str(equipment_id)


def test_validate_and_generate_reliability_model(
    client: TestClient,
) -> None:
    system = _create_system(client)
    version = _first_version(client, system["id"])
    version_id = version["id"]
    _seed_valid_model(client, version_id)

    validated = client.post(f"/api/v1/versions/{version_id}/validate")
    assert validated.status_code == 200, validated.text
    report = validated.json()
    assert report["is_valid"] is True

    generated = client.post(
        f"/api/v1/versions/{version_id}/reliability/generate",
        json={"notes": "baseline"},
    )
    assert generated.status_code == 201, generated.text
    body = generated.json()
    assert body["version_id"] == version_id
    assert body["validation_status"] == "VALID"
    assert len(body["model_hash"]) == 64
    assert body["snapshot"]["version_id"] == version_id
    assert len(body["snapshot"]["equipment"]) == 1
    assert body["notes"] == "baseline"

    latest = client.get(f"/api/v1/versions/{version_id}/reliability")
    assert latest.status_code == 200, latest.text
    assert latest.json()["id"] == body["id"]
    assert latest.json()["model_hash"] == body["model_hash"]

    by_id = client.get(f"/api/v1/reliability-models/{body['id']}")
    assert by_id.status_code == 200, by_id.text
    assert by_id.json()["model_hash"] == body["model_hash"]

    again = client.post(f"/api/v1/versions/{version_id}/reliability/generate")
    assert again.status_code == 201, again.text
    assert again.json()["model_hash"] == body["model_hash"]
    assert again.json()["id"] != body["id"]


def test_generate_rejects_incomplete_model(client: TestClient) -> None:
    system = _create_system(client)
    version = _first_version(client, system["id"])
    version_id = version["id"]

    equipment = client.post(
        f"/api/v1/versions/{version_id}/equipment",
        json={"tag": "P-101", "name": "Pump"},
    )
    assert equipment.status_code == 201, equipment.text

    validated = client.post(f"/api/v1/versions/{version_id}/validate")
    assert validated.status_code == 200, validated.text
    assert validated.json()["is_valid"] is False
    codes = {i["code"] for i in validated.json()["issues"]}
    assert "NO_FAILURE_MODES" in codes

    generated = client.post(
        f"/api/v1/versions/{version_id}/reliability/generate"
    )
    assert generated.status_code == 422, generated.text
    assert generated.json()["error"]["code"] in {
        "NO_FAILURE_MODES",
        "VALIDATION_ERROR",
        "MODEL_EMPTY",
    }
