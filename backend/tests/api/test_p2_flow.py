"""API -> DB integration tests for P2 acceptance flow."""

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
    assert len(versions) == 1
    return versions[0]


def test_create_model_and_retrieve_full_model(client: TestClient) -> None:
    system = _create_system(client)
    version = _first_version(client, system["id"])
    version_id = version["id"]

    equipment = client.post(
        f"/api/v1/versions/{version_id}/equipment",
        json={"tag": "P-101", "name": "Feed pump", "criticality": "CRITICAL"},
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
        },
    )
    assert task.status_code == 201, task.text

    model = client.get(f"/api/v1/versions/{version_id}/model")
    assert model.status_code == 200, model.text
    body = model.json()
    assert body["version"]["id"] == version_id
    assert body["version"]["status"] == "DRAFT"
    assert len(body["content"]["equipment"]) == 1
    assert body["content"]["equipment"][0]["tag"] == "P-101"
    assert len(body["content"]["failure_modes"]) == 1
    assert len(body["content"]["failure_distributions"]) == 1
    assert len(body["content"]["maintenance_tasks"]) == 1


def test_clone_preserves_lineage_and_content(client: TestClient) -> None:
    system = _create_system(client)
    version = _first_version(client, system["id"])
    version_id = version["id"]

    equipment = client.post(
        f"/api/v1/versions/{version_id}/equipment",
        json={"tag": "C-201", "name": "Compressor"},
    )
    assert equipment.status_code == 201
    source_equipment_id = equipment.json()["id"]
    source_lineage = equipment.json()["lineage_id"]

    clone = client.post(f"/api/v1/versions/{version_id}/clone")
    assert clone.status_code == 201, clone.text
    cloned = clone.json()
    assert cloned["status"] == "DRAFT"
    assert cloned["lineage_id"] == version["lineage_id"]
    assert cloned["parent_version_id"] == version_id
    assert cloned["version_number"] == version["version_number"] + 1

    model = client.get(f"/api/v1/versions/{cloned['id']}/model")
    assert model.status_code == 200
    content = model.json()["content"]
    assert len(content["equipment"]) == 1
    cloned_equipment = content["equipment"][0]
    assert cloned_equipment["tag"] == "C-201"
    assert cloned_equipment["lineage_id"] == source_lineage
    assert cloned_equipment["id"] != source_equipment_id


def test_frozen_version_rejects_writes(client: TestClient) -> None:
    system = _create_system(client)
    version = _first_version(client, system["id"])
    version_id = version["id"]

    created = client.post(
        f"/api/v1/versions/{version_id}/equipment",
        json={"tag": "E-1", "name": "Exchanger"},
    )
    assert created.status_code == 201

    transition = client.post(
        f"/api/v1/versions/{version_id}/transition",
        json={"status": "VALIDATED"},
    )
    assert transition.status_code == 200
    assert transition.json()["status"] == "VALIDATED"

    blocked = client.post(
        f"/api/v1/versions/{version_id}/equipment",
        json={"tag": "E-2", "name": "Blocked"},
    )
    assert blocked.status_code == 409
    error = blocked.json()["error"]
    assert error["code"] == "VERSION_FROZEN"
    assert set(error) == {"code", "message", "entity", "entity_id"}


def test_not_found_uses_unified_error(client: TestClient) -> None:
    missing = "00000000-0000-0000-0000-000000000099"
    response = client.get(f"/api/v1/systems/{missing}")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "ENTITY_NOT_FOUND"
    assert error["entity"] == "System"
