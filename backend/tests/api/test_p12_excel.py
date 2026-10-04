"""P12 Excel round-trip and demo seed tests."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from fastapi.testclient import TestClient


def test_seed_upp100_and_pf_demo(client: TestClient) -> None:
    response = client.post(
        "/api/v1/demo/upp100",
        json={"write_seed_file": False},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["for_software_testing"] is True
    assert body["equipment_count"] >= 50
    assert body["pf_demo_tag"] == "P-101"

    version_id = body["version_id"]
    model = client.get(f"/api/v1/versions/{version_id}/model")
    assert model.status_code == 200, model.text
    content = model.json()["content"]
    tags = {eq["tag"] for eq in content["equipment"]}
    assert "P-101" in tags
    assert len(tags) >= 50

    modes = [
        fm
        for fm in content["failure_modes"]
        if fm["name"] == "Mechanical seal degradation"
    ]
    assert len(modes) == 1
    assert modes[0]["is_detectable"] is True
    assert modes[0]["pf_interval"]["value"] == 14
    assert modes[0]["pf_interval"]["unit"] == "DAYS"

    diags = [
        d
        for d in content["diagnostic_tasks"]
        if d["name"] == "Vibration/condition monitoring"
    ]
    assert len(diags) == 1
    assert diags[0]["detection_probability"] == 0.85
    assert diags[0]["interval"]["value"] == 7
    assert diags[0]["interval"]["unit"] == "DAYS"

    maint = [
        t
        for t in content["maintenance_tasks"]
        if t["name"] == "Seal replacement"
    ]
    assert len(maint) == 1


def test_excel_round_trip_db_excel_db(client: TestClient) -> None:
    seed = client.post(
        "/api/v1/demo/upp100",
        json={"write_seed_file": False},
    )
    assert seed.status_code == 201, seed.text
    source_version = seed.json()["version_id"]

    export = client.get(f"/api/v1/versions/{source_version}/excel")
    assert export.status_code == 200, export.text
    assert (
        "spreadsheetml" in export.headers.get("content-type", "").lower()
        or export.content[:2] == b"PK"
    )
    workbook = export.content
    assert workbook[:2] == b"PK"

    preview = client.post(
        f"/api/v1/versions/{source_version}/excel/preview",
        files={
            "file": (
                "upp100.xlsx",
                BytesIO(workbook),
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet",
            )
        },
    )
    assert preview.status_code == 200, preview.text
    preview_body: dict[str, Any] = preview.json()
    assert preview_body["is_valid"] is True
    assert preview_body["counts"]["equipment"] >= 50

    system = client.post(
        "/api/v1/systems",
        json={"name": "Excel import target", "description": "round-trip"},
    )
    assert system.status_code == 201, system.text
    versions = client.get(f"/api/v1/systems/{system.json()['id']}/versions")
    assert versions.status_code == 200
    target_version = versions.json()[0]["id"]

    imported = client.post(
        f"/api/v1/versions/{target_version}/excel/import",
        files={
            "file": (
                "upp100.xlsx",
                BytesIO(workbook),
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet",
            )
        },
    )
    assert imported.status_code == 201, imported.text
    assert imported.json()["imported"]["equipment"] >= 50

    source_model = client.get(f"/api/v1/versions/{source_version}/model")
    target_model = client.get(f"/api/v1/versions/{target_version}/model")
    source_tags = sorted(
        eq["tag"] for eq in source_model.json()["content"]["equipment"]
    )
    target_tags = sorted(
        eq["tag"] for eq in target_model.json()["content"]["equipment"]
    )
    assert source_tags == target_tags
    assert len(source_model.json()["content"]["failure_modes"]) == len(
        target_model.json()["content"]["failure_modes"]
    )
    assert len(source_model.json()["content"]["diagnostic_tasks"]) == len(
        target_model.json()["content"]["diagnostic_tasks"]
    )


def test_excel_rejects_non_xlsx(client: TestClient) -> None:
    system = client.post(
        "/api/v1/systems",
        json={"name": "Bad excel", "description": None},
    )
    version_id = client.get(
        f"/api/v1/systems/{system.json()['id']}/versions"
    ).json()[0]["id"]
    response = client.post(
        f"/api/v1/versions/{version_id}/excel/import",
        files={"file": ("bad.txt", BytesIO(b"not-excel"), "text/plain")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "EXCEL_INVALID_FORMAT"
