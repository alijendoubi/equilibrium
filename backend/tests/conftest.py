"""Shared fixtures: a hermetic environment and a test client."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from atlas.api.main import create_app
from atlas.config import Settings, get_settings

_ENV_VARS = (
    "OPENAI_API_KEY",
    "OPENAI_MODEL_EXTRACT",
    "OPENAI_MODEL_EXPLAIN",
    "OPENAI_MODEL_RECONCILE",
    "OPENAI_EMBED_MODEL",
    "NCBI_API_KEY",
    "OMIM_API_KEY",
    "CORS_ORIGINS",
    "LOG_LEVEL",
    "SNAPSHOT_PATH",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Remove atlas env vars and run from an empty dir so no local .env leaks into tests."""
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Test client built from default settings."""
    with TestClient(create_app(Settings())) as test_client:
        yield test_client
