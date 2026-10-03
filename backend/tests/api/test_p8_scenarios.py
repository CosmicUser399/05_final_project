"""P8 scenarios: create, simulate overlay, compare, baseline intact."""

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
        json={"name": "УПП-100", "description": "Scenario demo"},
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def _first_version(client: TestClient, system_id: str) -> dict[str, Any]:
    response = client.get(f"/api/v1/systems/{system_id}/versions")
    assert response.status_code == 200, response.text
    versions: list[dict[str, Any]] = response.json()
    return versions[0]


def _seed_detectable_model(client: TestClient, version_id: str) -> dict[str, Any]:
    """Seed pump + detectable FM + diagnostic + compile."""
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
            "pf_interval": {"value": 14.0, "unit": "DAYS"},
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
    mode_body = mode.json()
    mode_id = mode_body["id"]

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
                    "value": 1.0,
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

    diagnostic = client.post(
        f"/api/v1/equipment/{equipment_id}/diagnostics",
        json={
            "name": "Vibration monitoring",
            "failure_mode_id": mode_id,
            "interval": {"value": 30.0, "unit": "DAYS"},
            "detection_probability": 0.85,
        },
    )
    assert diagnostic.status_code == 201, diagnostic.text
    diag_body = diagnostic.json()

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

    model = client.get(f"/api/v1/versions/{version_id}/model")
    assert model.status_code == 200, model.text
    model_body = model.json()

    return {
        "equipment_id": equipment_id,
        "mode_id": mode_id,
        "mode_lineage_id": mode_body["lineage_id"],
        "diagnostic_id": diag_body["id"],
        "diagnostic_lineage_id": diag_body["lineage_id"],
        "reliability_model_id": generated.json()["id"],
        "full_model": model_body,
    }


def _run_worker(
    session_factory: sessionmaker[Session],
) -> None:
    settings = Settings(app_env="test", log_json=False)
    worker = LocalProcessJobRunner(
        session_factory,
        settings,
        worker_id="p8-worker",
    )
    assert worker.process_once() is True


def test_create_scenario_does_not_mutate_baseline(
    client: TestClient,
) -> None:
    system = _create_system(client)
    version = _first_version(client, system["id"])
    version_id = version["id"]
    seeded = _seed_detectable_model(client, version_id)

    before = client.get(f"/api/v1/versions/{version_id}/model")
    assert before.status_code == 200
    before_hash = before.json().get("model_hash") or before.json()

    created = client.post(
        f"/api/v1/versions/{version_id}/scenarios",
        json={
            "name": "Diagnostics 14 days",
            "description": "Shorter diagnostic interval",
            "changes": [
                {
                    "change_type": "CHANGE_DIAGNOSTIC_INTERVAL",
                    "target_lineage_id": seeded["diagnostic_lineage_id"],
                    "parameters": {"value": 14.0, "unit": "DAYS"},
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    scenario = created.json()
    assert scenario["name"] == "Diagnostics 14 days"
    assert scenario["current_version"]["scenario_hash"]
    assert len(scenario["current_version"]["changes"]) == 1

    after = client.get(f"/api/v1/versions/{version_id}/model")
    assert after.status_code == 200
    assert after.json() == before.json() or (
        before_hash == after.json().get("model_hash")
    )

    diagnostics = client.get(
        f"/api/v1/equipment/{seeded['equipment_id']}/diagnostics"
    )
    assert diagnostics.status_code == 200
    diag = diagnostics.json()[0]
    assert diag["interval"]["value"] == 30.0
    assert diag["interval"]["unit"] == "DAYS"


def test_invalid_lineage_rejected(client: TestClient) -> None:
    system = _create_system(client)
    version = _first_version(client, system["id"])
    version_id = version["id"]
    _seed_detectable_model(client, version_id)

    response = client.post(
        f"/api/v1/versions/{version_id}/scenarios",
        json={
            "name": "Broken target",
            "changes": [
                {
                    "change_type": "CHANGE_DIAGNOSTIC_INTERVAL",
                    "target_lineage_id": (
                        "00000000-0000-0000-0000-000000000099"
                    ),
                    "parameters": {"value": 14.0, "unit": "DAYS"},
                }
            ],
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SCENARIO_TARGET_NOT_FOUND"


def test_simulate_and_compare_scenarios(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    system = _create_system(client)
    version = _first_version(client, system["id"])
    version_id = version["id"]
    seeded = _seed_detectable_model(client, version_id)
    lineage = seeded["diagnostic_lineage_id"]
    model_id = seeded["reliability_model_id"]

    baseline_body = {
        "version_id": version_id,
        "reliability_model_id": model_id,
        "horizon": 365,
        "horizon_unit": "DAYS",
        "number_of_runs": 4,
        "random_seed": 7,
        "parallel_runs": 1,
    }
    baseline = client.post(
        "/api/v1/simulations",
        json=baseline_body,
        headers={"Idempotency-Key": "p8-baseline"},
    )
    assert baseline.status_code == 202, baseline.text
    baseline_id = baseline.json()["id"]
    assert baseline.json()["scenario_version_id"] is None
    _run_worker(session_factory)

    scenarios: dict[str, str] = {}
    for days in (14, 30, 60):
        created = client.post(
            f"/api/v1/versions/{version_id}/scenarios",
            json={
                "name": f"Diagnostics {days}d",
                "changes": [
                    {
                        "change_type": "CHANGE_DIAGNOSTIC_INTERVAL",
                        "target_lineage_id": lineage,
                        "parameters": {
                            "value": float(days),
                            "unit": "DAYS",
                        },
                    }
                ],
            },
        )
        assert created.status_code == 201, created.text
        scenario_id = created.json()["id"]
        scenarios[str(days)] = scenario_id

        sim = client.post(
            f"/api/v1/scenarios/{scenario_id}/simulate",
            json={
                "reliability_model_id": model_id,
                "horizon": 365,
                "horizon_unit": "DAYS",
                "number_of_runs": 4,
                "random_seed": 7,
                "parallel_runs": 1,
            },
            headers={"Idempotency-Key": f"p8-scen-{days}"},
        )
        assert sim.status_code == 202, sim.text
        assert sim.json()["scenario_version_id"] is not None
        assert sim.json()["scenario_hash"] != baseline.json()["scenario_hash"]
        _run_worker(session_factory)

    compare = client.get(
        f"/api/v1/scenarios/{scenarios['14']}/compare",
        params={"baseline_run_id": baseline_id},
    )
    assert compare.status_code == 200, compare.text
    body = compare.json()
    assert body["baseline_run_id"] == baseline_id
    assert "deltas" in body
    assert "availability" in body["deltas"]
    metrics = {row["metric"]: row for row in body["rows"]}
    assert "production_loss" in metrics
    assert "availability" in metrics

    hashes = set()
    for days, scenario_id in scenarios.items():
        detail = client.get(f"/api/v1/scenarios/{scenario_id}")
        assert detail.status_code == 200
        hashes.add(detail.json()["current_version"]["scenario_hash"])
    assert len(hashes) == 3


def test_list_scenarios(client: TestClient) -> None:
    system = _create_system(client)
    version = _first_version(client, system["id"])
    version_id = version["id"]
    seeded = _seed_detectable_model(client, version_id)

    client.post(
        f"/api/v1/versions/{version_id}/scenarios",
        json={
            "name": "A",
            "changes": [
                {
                    "change_type": "CHANGE_DETECTION_PROBABILITY",
                    "target_lineage_id": seeded["diagnostic_lineage_id"],
                    "parameters": {"detection_probability": 0.95},
                }
            ],
        },
    )
    listed = client.get(f"/api/v1/versions/{version_id}/scenarios")
    assert listed.status_code == 200
    assert len(listed.json()) >= 1
