"""API + worker integration tests for Monte Carlo jobs."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

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
    model_id: str = generated.json()["id"]
    return model_id


def test_simulation_idempotency_and_results(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    system = _create_system(client)
    version = _first_version(client, system["id"])
    version_id = version["id"]
    model_id = _seed_and_compile(client, version_id)

    body = {
        "version_id": version_id,
        "reliability_model_id": model_id,
        "horizon": 2000,
        "horizon_unit": "HOURS",
        "number_of_runs": 6,
        "random_seed": 42,
        "parallel_runs": 1,
        "warmup_period": 0,
    }
    first = client.post(
        "/api/v1/simulations",
        json=body,
        headers={"Idempotency-Key": "demo-key-1"},
    )
    assert first.status_code == 202, first.text
    run = first.json()
    assert run["status"] == "QUEUED"
    assert run["total_runs"] == 6
    assert len(run["simulation_fingerprint"]) == 64

    again = client.post(
        "/api/v1/simulations",
        json=body,
        headers={"Idempotency-Key": "demo-key-1"},
    )
    assert again.status_code == 202, again.text
    assert again.json()["id"] == run["id"]

    settings = Settings(app_env="test", log_json=False)
    worker = LocalProcessJobRunner(
        session_factory,
        settings,
        worker_id="test-worker",
    )
    assert worker.process_once() is True

    status = client.get(f"/api/v1/simulations/{run['id']}/status")
    assert status.status_code == 200, status.text
    assert status.json()["status"] == "COMPLETED"
    assert status.json()["progress"] == 1.0

    results = client.get(f"/api/v1/simulations/{run['id']}/results")
    assert results.status_code == 200, results.text
    metrics = results.json()["metrics"]
    assert metrics["completed_runs"] == 6
    assert metrics["ai"]["mean"] is not None

    events = client.get(
        f"/api/v1/simulations/{run['id']}/events",
        params={"limit": 50},
    )
    assert events.status_code == 200, events.text
    assert events.json()["count"] >= 0


def test_cancel_queued_simulation(client: TestClient) -> None:
    system = _create_system(client)
    version = _first_version(client, system["id"])
    version_id = version["id"]
    _seed_and_compile(client, version_id)

    created = client.post(
        "/api/v1/simulations",
        json={
            "version_id": version_id,
            "horizon": 1000,
            "horizon_unit": "HOURS",
            "number_of_runs": 3,
            "random_seed": 1,
        },
    )
    assert created.status_code == 202, created.text
    run_id = created.json()["id"]

    cancelled = client.post(f"/api/v1/simulations/{run_id}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELLED"

    results = client.get(f"/api/v1/simulations/{run_id}/results")
    assert results.status_code == 409


def test_sse_stream_completed(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    system = _create_system(client)
    version = _first_version(client, system["id"])
    version_id = version["id"]
    _seed_and_compile(client, version_id)

    created = client.post(
        "/api/v1/simulations",
        json={
            "version_id": version_id,
            "horizon": 1000,
            "horizon_unit": "HOURS",
            "number_of_runs": 4,
            "random_seed": 9,
            "parallel_runs": 1,
        },
    )
    assert created.status_code == 202, created.text
    run_id = created.json()["id"]

    settings = Settings(
        app_env="test",
        log_json=False,
        simulation_sse_poll_seconds=0.05,
    )
    LocalProcessJobRunner(
        session_factory,
        settings,
        worker_id="sse-worker",
    ).process_once()

    with client.stream(
        "GET",
        f"/api/v1/simulations/{run_id}/stream",
    ) as response:
        assert response.status_code == 200
        text = "".join(response.iter_text())
    assert "event: progress" in text
    assert "event: done" in text
    assert "COMPLETED" in text


def test_rejects_too_many_runs(client: TestClient) -> None:
    system = _create_system(client)
    version = _first_version(client, system["id"])
    version_id = version["id"]
    _seed_and_compile(client, version_id)

    response = client.post(
        "/api/v1/simulations",
        json={
            "version_id": version_id,
            "horizon": 1,
            "horizon_unit": "HOURS",
            "number_of_runs": 10_000_000,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SIMULATION_LIMIT"
