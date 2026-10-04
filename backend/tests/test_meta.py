"""GET /api/v1/meta and CORS behaviour."""

from pathlib import Path

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
    body = response.json()
    assert body["name"] == "Equilibrium Atlas"
    assert body["sources"] == EXPECTED_SOURCES


def test_meta_reports_loaded_snapshot_from_manifest(client: TestClient) -> None:
    snapshot = client.get("/api/v1/meta").json()["snapshot"]

    assert snapshot["status"] == "loaded"
    assert snapshot["snapshot_id"].startswith("sha256:")
    assert snapshot["slice"] == "gba1"
    assert snapshot["counts"]["nodes"] > 0 and snapshot["counts"]["edges"] > 0
    assert "disease" in snapshot["counts"]["nodes_by_type"]
    assert {s["source"] for s in snapshot["sources"]} >= {"monarch", "clinicaltrials", "curated"}
    assert snapshot["openai_usage"]["calls"] == 0


def test_meta_without_snapshot(tmp_path: Path) -> None:
    settings = Settings(SNAPSHOT_PATH=tmp_path / "missing.json")
    with TestClient(create_app(settings)) as test_client:
        snapshot = test_client.get("/api/v1/meta").json()["snapshot"]

    assert snapshot["status"] == "missing"
    assert snapshot["snapshot_id"] is None
    assert snapshot["counts"] == {}
    assert snapshot["detail"]


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
