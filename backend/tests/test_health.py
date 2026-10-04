"""GET /health."""

from pathlib import Path

from fastapi.testclient import TestClient

from atlas import __version__
from atlas.api.main import app, create_app
from atlas.config import Settings


def test_health_returns_ok_and_version(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0", "snapshot": "loaded"}
    assert __version__ == "0.1.0"


def test_module_level_app_is_importable() -> None:
    with TestClient(app) as test_client:
        assert test_client.get("/health").status_code == 200


def test_health_reports_missing_snapshot_and_app_still_starts(tmp_path: Path) -> None:
    settings = Settings(SNAPSHOT_PATH=tmp_path / "nope.json")
    with TestClient(create_app(settings)) as test_client:
        response = test_client.get("/health")

    assert response.status_code == 200
    assert response.json()["snapshot"] == "missing"


def test_health_reports_broken_snapshot(tmp_path: Path) -> None:
    broken = tmp_path / "atlas-snapshot.json"
    broken.write_text("{not json", encoding="utf-8")
    with TestClient(create_app(Settings(SNAPSHOT_PATH=broken))) as test_client:
        assert test_client.get("/health").json()["snapshot"] == "error"


def test_health_before_lifespan_reports_not_loaded() -> None:
    test_client = TestClient(create_app(Settings()))  # no context manager: lifespan not run

    assert test_client.get("/health").json()["snapshot"] == "not_loaded"
