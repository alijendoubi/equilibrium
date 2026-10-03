"""GET /health."""

from fastapi.testclient import TestClient

from atlas import __version__
from atlas.api.main import app


def test_health_returns_ok_and_version(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}
    assert __version__ == "0.1.0"


def test_module_level_app_is_importable() -> None:
    with TestClient(app) as test_client:
        assert test_client.get("/health").status_code == 200
