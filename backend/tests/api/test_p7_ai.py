"""P7 AI generation API: proposal review and Domain DB commit."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


def test_openai_generate_review_commit(client: TestClient) -> None:
    created = client.post(
        "/api/v1/ai/generate-system",
        json={
            "description": (
                "Установка производства полистирола "
                "мощностью 100 тысяч тонн в год"
            ),
            "provider": "openai",
            "process_inline": True,
        },
    )
    assert created.status_code == 202, created.text
    job = created.json()
    assert job["status"] == "READY_FOR_REVIEW"
    assert job["proposal_id"] is not None

    proposal = client.get(f"/api/v1/ai/proposals/{job['proposal_id']}")
    assert proposal.status_code == 200
    body = proposal.json()
    items = body["items"]
    assert items
    assert body["provenance"]["source_type"] == "AI_ESTIMATE"

    for item in items:
        if item["item_type"] in {"equipment", "connection"}:
            decided = client.post(
                f"/api/v1/ai/proposals/items/{item['id']}/decide",
                json={"decision": "ACCEPTED"},
            )
            assert decided.status_code == 200

    commit = client.post(
        f"/api/v1/ai/proposals/{job['proposal_id']}/commit",
        json={"system_name": "УПП-100", "create_system": True},
    )
    assert commit.status_code == 200, commit.text
    result = commit.json()
    assert result["created_equipment"] >= 1
    version_id = result["version_id"]

    equipment = client.get(f"/api/v1/versions/{version_id}/equipment")
    assert equipment.status_code == 200
    tags = {row["tag"] for row in equipment.json()}
    assert "P-101" in tags


def test_fabricate_generate_ready_for_review(client: TestClient) -> None:
    created = client.post(
        "/api/v1/ai/generate-system",
        json={
            "description": "Demo plant",
            "provider": "fabricate",
            "process_inline": True,
        },
    )
    assert created.status_code == 202, created.text
    job = created.json()
    assert job["status"] == "READY_FOR_REVIEW"
    assert job["conversation_id"]
    proposal = client.get(f"/api/v1/ai/proposals/{job['proposal_id']}")
    body = proposal.json()
    assert body["provider"] == "fabricate"
    assert body["provenance"]["generated_by"] == "fabricate"


def test_cancel_queued_job(client: TestClient) -> None:
    created = client.post(
        "/api/v1/ai/generate-system",
        json={
            "description": "queued only",
            "provider": "openai",
            "process_inline": False,
        },
    )
    job_id = created.json()["id"]
    cancelled = client.post(f"/api/v1/ai/generation-jobs/{job_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"


def test_invalid_provider(client: TestClient) -> None:
    response = client.post(
        "/api/v1/ai/generate-system",
        json={"description": "x", "provider": "unknown"},
    )
    assert response.status_code == 422
    error: dict[str, Any] = response.json()["error"]
    assert error["code"] == "INVALID_PROVIDER"
