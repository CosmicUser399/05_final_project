"""Tests for health, readiness, request id and error format."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def _client(tmp_path: Path, database_url: str | None = None) -> TestClient:
    url = database_url or f"sqlite:///{tmp_path / 'test.db'}"
    settings = Settings(
        app_env="test",
        database_url=url,
        log_json=False,
    )
    return TestClient(create_app(settings))


def test_health_ok(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_health_under_api_prefix(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/v1/health")

    assert response.status_code == 200


def test_ready_ok_with_sqlite_file(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"database": True},
    }


def test_ready_not_ready_when_database_unavailable(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing_dir" / "app.db"
    client = _client(tmp_path, f"sqlite:///{missing}")

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["checks"] == {"database": False}


def test_request_id_is_generated_and_echoed(tmp_path: Path) -> None:
    client = _client(tmp_path)

    generated = client.get("/health").headers["X-Request-ID"]
    echoed = client.get(
        "/health", headers={"X-Request-ID": "abc-123"}
    ).headers["X-Request-ID"]

    assert generated
    assert echoed == "abc-123"


def test_invalid_request_id_is_replaced(tmp_path: Path) -> None:
    response = _client(tmp_path).get(
        "/health", headers={"X-Request-ID": "bad id!"}
    )

    assert response.headers["X-Request-ID"] != "bad id!"


def test_not_found_uses_unified_error_format(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/nope")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "HTTP_404"
    assert set(error) == {"code", "message", "entity", "entity_id"}
