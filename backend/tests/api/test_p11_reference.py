"""API tests for P11 OREDA / ISO reference data."""

from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient


def _ingest(client: TestClient) -> dict:
    response = client.post("/api/v1/reference/ingest", json={})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available"] is True
    assert body["oreda_total"] >= 1
    assert body["iso_total"] >= 1
    return body


def test_reference_status_empty_then_loaded(client: TestClient) -> None:
    empty = client.get("/api/v1/reference/status")
    assert empty.status_code == 200
    assert empty.json()["available"] is False

    _ingest(client)
    loaded = client.get("/api/v1/reference/status")
    assert loaded.json()["available"] is True
    assert loaded.json()["oreda_parameters"] >= 1


def test_search_parameters_and_taxonomy(client: TestClient) -> None:
    _ingest(client)
    params = client.get(
        "/api/v1/reference/parameters",
        params={"query": "pump", "limit": 20},
    )
    assert params.status_code == 200
    body = params.json()
    assert body["available"] is True
    assert body["count"] >= 1
    row = body["items"][0]
    assert row["source_type"] == "OREDA"
    assert row["source_reference"]
    assert row["confidence"]

    taxonomy = client.get(
        "/api/v1/reference/taxonomy",
        params={"query": "PUMP"},
    )
    assert taxonomy.status_code == 200
    tax = taxonomy.json()
    assert tax["count"] >= 1
    assert tax["items"][0]["code"].startswith("PUMP")


def test_suggest_and_link_equipment(client: TestClient) -> None:
    _ingest(client)
    system = client.post(
        "/api/v1/systems",
        json={"name": "Ref link system"},
    )
    assert system.status_code == 201
    system_id = system.json()["id"]
    versions = client.get(f"/api/v1/systems/{system_id}/versions")
    version_id = versions.json()[0]["id"]

    equipment = client.post(
        f"/api/v1/versions/{version_id}/equipment",
        json={
            "tag": "P-101",
            "name": "Feed pump",
            "equipment_class": "Centrifugal pump",
            "quantity": 1,
        },
    )
    assert equipment.status_code == 201
    equipment_id = equipment.json()["id"]

    suggest = client.get(
        "/api/v1/reference/suggest",
        params={"equipment_class": "Centrifugal pump"},
    )
    assert suggest.status_code == 200
    items = suggest.json()["items"]
    assert any(item["kind"] == "taxonomy_node" for item in items)
    node = next(item for item in items if item["kind"] == "taxonomy_node")

    linked = client.post(
        f"/api/v1/reference/equipment/{equipment_id}/link",
        json={"taxonomy_node_id": node["taxonomy_node_id"]},
    )
    assert linked.status_code == 200
    assert linked.json()["taxonomy_node_id"] == node["taxonomy_node_id"]


def test_apply_oreda_parameter_to_failure_mode(client: TestClient) -> None:
    _ingest(client)
    system = client.post(
        "/api/v1/systems",
        json={"name": "Ref apply system"},
    )
    system_id = system.json()["id"]
    versions = client.get(f"/api/v1/systems/{system_id}/versions")
    version_id = versions.json()[0]["id"]
    equipment = client.post(
        f"/api/v1/versions/{version_id}/equipment",
        json={"tag": "P-201", "name": "Pump", "quantity": 1},
    )
    equipment_id = equipment.json()["id"]
    mode = client.post(
        f"/api/v1/equipment/{equipment_id}/failure-modes",
        json={"name": "Fail to function", "is_detectable": False},
    )
    assert mode.status_code == 201
    mode_id = mode.json()["id"]

    params = client.get(
        "/api/v1/reference/parameters",
        params={"equipment_class_code": "PUMP.CENT", "limit": 5},
    )
    parameter_id = params.json()["items"][0]["id"]

    applied = client.post(
        f"/api/v1/reference/parameters/{parameter_id}/apply",
        json={"failure_mode_id": mode_id},
    )
    assert applied.status_code == 200, applied.text
    body = applied.json()
    assert body["failure_mode_id"] == mode_id
    assert body["provenance"]["source_type"] == "OREDA"
    assert body["provenance"]["source_reference"]
    assert UUID(body["id"])


def test_analyst_reference_search_available(client: TestClient) -> None:
    _ingest(client)
    response = client.post(
        "/api/v1/ai/chat",
        json={"message": "Найди OREDA параметры для pump"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    tool_names = [call["name"] for call in body["tool_calls"]]
    assert "reference.search" in tool_names
    ref_call = next(
        call
        for call in body["tool_calls"]
        if call["name"] == "reference.search"
    )
    assert ref_call["ok"] is True
    assert ref_call["result"]["available"] is True
    assert ref_call["result"]["count"] >= 1
