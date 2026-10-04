"""API-level Package §101 acceptance flow (P12 E2E core)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.infrastructure.jobs.runner import LocalProcessJobRunner


def test_package_101_mvp_acceptance_flow(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    """Cover Package §101 steps via API with Mock AI/Petri."""
    # 1-7: seed demo plant (stand-in for AI generate + review accept).
    seed = client.post(
        "/api/v1/demo/upp100",
        json={"write_seed_file": False},
    )
    assert seed.status_code == 201, seed.text
    system_id = seed.json()["system_id"]
    version_id = seed.json()["version_id"]

    system = client.get(f"/api/v1/systems/{system_id}")
    assert system.status_code == 200
    assert "100" in system.json()["name"]

    # 8: edit equipment.
    equipment = client.get(f"/api/v1/versions/{version_id}/equipment")
    assert equipment.status_code == 200
    p101 = next(eq for eq in equipment.json() if eq["tag"] == "P-101")
    patched = client.patch(
        f"/api/v1/equipment/{p101['id']}",
        json={"description": "Edited feed pump for acceptance"},
    )
    assert patched.status_code == 200

    # 9-12: failure modes / PF / maintenance already in seed.
    model = client.get(f"/api/v1/versions/{version_id}/model").json()
    assert model["content"]["failure_modes"]
    assert model["content"]["diagnostic_tasks"]
    assert model["content"]["maintenance_tasks"]
    pf_modes = [
        fm
        for fm in model["content"]["failure_modes"]
        if fm["name"] == "Mechanical seal degradation"
    ]
    assert pf_modes and pf_modes[0]["pf_interval"]["value"] == 14

    # 13: topology.
    connections = client.get(f"/api/v1/versions/{version_id}/connections")
    assert connections.status_code == 200
    assert len(connections.json()) >= 1

    # 14: reliability model.
    rel = client.post(f"/api/v1/versions/{version_id}/reliability/generate")
    assert rel.status_code == 201, rel.text
    model_id = rel.json()["id"]

    # 15-16: Petri generate + validate (mock).
    petri = client.post(f"/api/v1/versions/{version_id}/petri/generate")
    assert petri.status_code == 201, petri.text
    petri_id = petri.json()["id"]
    validated = client.post(f"/api/v1/petri/{petri_id}/validate")
    assert validated.status_code == 200, validated.text

    # 17-20: Monte Carlo (short horizon for CI).
    sim = client.post(
        "/api/v1/simulations",
        headers={"Idempotency-Key": "p12-acceptance-1"},
        json={
            "version_id": version_id,
            "reliability_model_id": model_id,
            "horizon": 1000,
            "horizon_unit": "HOURS",
            "number_of_runs": 4,
            "random_seed": 42,
            "parallel_runs": 1,
            "warmup_period": 0,
        },
    )
    assert sim.status_code == 202, sim.text
    run_id = sim.json()["id"]
    settings = Settings(app_env="test", log_json=False)
    worker = LocalProcessJobRunner(
        session_factory,
        settings,
        worker_id="p12-acceptance",
    )
    assert worker.process_once() is True
    status = client.get(f"/api/v1/simulations/{run_id}/status")
    assert status.status_code == 200
    assert status.json()["status"] == "COMPLETED"

    # 21-23: results + events.
    results = client.get(f"/api/v1/simulations/{run_id}/results")
    assert results.status_code == 200, results.text
    metrics = results.json()["metrics"]
    assert metrics["completed_runs"] == 4

    events = client.get(
        f"/api/v1/simulations/{run_id}/events",
        params={"limit": 10},
    )
    assert events.status_code == 200, events.text

    # 24-27: scenario with diagnostic interval change.
    diags = client.get(f"/api/v1/equipment/{p101['id']}/diagnostics")
    assert diags.status_code == 200
    diag = diags.json()[0]
    scenario = client.post(
        f"/api/v1/versions/{version_id}/scenarios",
        json={
            "name": "Diagnostics 14 days",
            "description": "acceptance scenario",
            "changes": [
                {
                    "change_type": "CHANGE_DIAGNOSTIC_INTERVAL",
                    "target_lineage_id": diag["lineage_id"],
                    "parameters": {"value": 14.0, "unit": "DAYS"},
                }
            ],
        },
    )
    assert scenario.status_code == 201, scenario.text

    # 28-29: AI analyst grounded answer.
    chat = client.post(
        "/api/v1/ai/chat",
        json={
            "message": (
                "Какие единицы оборудования дали наибольший вклад "
                "в потерю производства?"
            ),
            "context": {
                "system_id": system_id,
                "version_id": version_id,
                "simulation_run_id": run_id,
            },
        },
    )
    assert chat.status_code == 200, chat.text
    body: dict[str, Any] = chat.json()
    assert body.get("answer")
    assert body.get("grounded") is True

    # 30: provenance on failure distributions.
    dists = model["content"]["failure_distributions"]
    assert dists
    assert dists[0]["provenance"]["source_type"]
