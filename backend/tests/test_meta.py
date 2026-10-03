"""GET /api/v1/meta and CORS behaviour."""

from fastapi.testclient import TestClient

from atlas.api.main import create_app
from atlas.config import Settings

EXPECTED_SOURCES = [
    "omim",
    "hpo",
    "mondo",
    "clinvar",
    "pubmed",
    "clinicaltrials",
    "nih_reporter",
    "orphanet",
]


def test_meta_returns_name_and_sources(client: TestClient) -> None:
    response = client.get("/api/v1/meta")

    assert response.status_code == 200
    assert response.json() == {"name": "Equilibrium Atlas", "sources": EXPECTED_SOURCES}


def test_cors_allows_default_frontend_origin(client: TestClient) -> None:
    response = client.get("/api/v1/meta", headers={"Origin": "http://localhost:3000"})

    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_rejects_unknown_origin(client: TestClient) -> None:
    response = client.get("/api/v1/meta", headers={"Origin": "https://evil.example"})

    assert "access-control-allow-origin" not in response.headers


def test_cors_uses_configured_origins() -> None:
    settings = Settings(CORS_ORIGINS="https://atlas.example")
    with TestClient(create_app(settings)) as test_client:
        response = test_client.get("/health", headers={"Origin": "https://atlas.example"})

    assert response.headers["access-control-allow-origin"] == "https://atlas.example"
