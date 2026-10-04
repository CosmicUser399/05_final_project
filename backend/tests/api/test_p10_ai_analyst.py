"""API tests for P10 AI Analyst chat."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.application.analyst.grounding import collect_allowed_numbers
from app.application.analyst.grounding import is_grounded
from app.config import Settings
from app.infrastructure.jobs.runner import LocalProcessJobRunner


def _create_system(client: TestClient) -> dict[str, Any]:
    response = client.post(
        "/api/v1/systems",
        json={"name": "УПП-100", "description": "Demo"},
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def _first_version(client: TestClient, system_id: str) -> dict[str, Any]:
    response = client.get(f"/api/v1/systems/{system_id}/versions")
    assert response.status_code == 200, response.text
    versions: list[dict[str, Any]] = response.json()
    return versions[0]


def _seed_and_compile(client: TestClient, version_id: str) -> str:
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
            "name": "Random failure",
            "is_detectable": False,
            "distribution": {
                "distribution": {
                    "type": "EXPONENTIAL",
                    "lambda": 0.001,
                    "unit": "HOURS",
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
            "name": "Repair",
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

    generated = client.post(
        f"/api/v1/versions/{version_id}/reliability/generate"
    )
    assert generated.status_code == 201, generated.text
    return str(generated.json()["id"])


def _run_simulation(
    client: TestClient,
    session_factory: sessionmaker[Session],
    version_id: str,
    model_id: str,
) -> dict[str, Any]:
    created = client.post(
        "/api/v1/simulations",
        json={
            "version_id": version_id,
            "reliability_model_id": model_id,
            "horizon": 2000,
            "horizon_unit": "HOURS",
            "number_of_runs": 4,
            "random_seed": 42,
            "parallel_runs": 1,
            "warmup_period": 0,
        },
        headers={"Idempotency-Key": "analyst-p10"},
    )
    assert created.status_code == 202, created.text
    run = created.json()
    settings = Settings(app_env="test", log_json=False)
    worker = LocalProcessJobRunner(
        session_factory,
        settings,
        worker_id="analyst-worker",
    )
    assert worker.process_once() is True
    status = client.get(f"/api/v1/simulations/{run['id']}/status")
    assert status.json()["status"] == "COMPLETED"
    return run


def test_analyst_chat_grounded_on_simulation_metrics(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    system = _create_system(client)
    version = _first_version(client, system["id"])
    model_id = _seed_and_compile(client, version["id"])
    run = _run_simulation(
        client,
        session_factory,
        version["id"],
        model_id,
    )

    response = client.post(
        "/api/v1/ai/chat",
        json={
            "message": (
                "Какие метрики доступности и потерь производства "
                "показывает симуляция?"
            ),
            "context": {
                "system_id": system["id"],
                "version_id": version["id"],
                "simulation_run_id": run["id"],
            },
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["grounded"] is True
    assert body["tool_calls"]
    assert any(
        call["name"] == "simulation.get_metrics" and call["ok"]
        for call in body["tool_calls"]
    )
    allowed = collect_allowed_numbers(body["tool_calls"])
    assert is_grounded(body["answer"], allowed)
    assert body["references"]
    assert "777.7" not in body["answer"]


def test_analyst_chat_stream_events(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    system = _create_system(client)
    version = _first_version(client, system["id"])
    model_id = _seed_and_compile(client, version["id"])
    run = _run_simulation(
        client,
        session_factory,
        version["id"],
        model_id,
    )

    with client.stream(
        "POST",
        "/api/v1/ai/chat/stream",
        json={
            "message": "Покажи доступность Ai",
            "context": {"simulation_run_id": run["id"]},
        },
    ) as stream:
        assert stream.status_code == 200
        text = "".join(stream.iter_text())
    assert "event: started" in text
    assert "event: answer" in text
    assert "grounded" in text


def test_analyst_equipment_search_tool(
    client: TestClient,
) -> None:
    system = _create_system(client)
    version = _first_version(client, system["id"])
    equipment = client.post(
        f"/api/v1/versions/{version['id']}/equipment",
        json={"tag": "P-101", "name": "Feed pump"},
    )
    assert equipment.status_code == 201

    response = client.post(
        "/api/v1/ai/chat",
        json={
            "message": "Какое оборудование P-101 есть в версии?",
            "context": {
                "system_id": system["id"],
                "version_id": version["id"],
            },
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert any(
        call["name"] == "equipment.search" and call["ok"]
        for call in body["tool_calls"]
    )
    assert "P-101" in body["answer"]
