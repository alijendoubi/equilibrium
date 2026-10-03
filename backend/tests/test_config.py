"""Settings loading from the environment."""

import pytest
from pydantic import ValidationError

from atlas.config import Settings, get_settings


def test_defaults_work_without_any_secrets() -> None:
    settings = Settings()

    assert settings.openai_api_key is None
    assert settings.ncbi_api_key is None
    assert settings.omim_api_key is None
    assert settings.openai_model == "gpt-4.1-mini"
    assert settings.cors_origin_list == ("http://localhost:3000",)
    assert settings.log_level == "INFO"
    assert settings.has_openai_key is False


def test_reads_values_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1")
    monkeypatch.setenv("NCBI_API_KEY", "ncbi-secret")
    monkeypatch.setenv("OMIM_API_KEY", "omim-secret")
    monkeypatch.setenv("CORS_ORIGINS", " https://a.example , ,https://b.example ")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    settings = Settings()

    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "sk-test-secret"
    assert settings.has_openai_key is True
    assert settings.openai_model == "gpt-4.1"
    assert settings.cors_origin_list == ("https://a.example", "https://b.example")
    assert settings.log_level == "DEBUG"


def test_empty_openai_key_is_not_considered_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")

    assert Settings().has_openai_key is False


def test_secrets_are_not_exposed_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")
    monkeypatch.setenv("OMIM_API_KEY", "omim-secret")

    rendered = repr(Settings()) + str(Settings().model_dump())

    assert "sk-test-secret" not in rendered
    assert "omim-secret" not in rendered


def test_invalid_log_level_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "LOUD")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_are_immutable() -> None:
    settings = Settings()

    with pytest.raises(ValidationError):
        settings.openai_model = "other"  # type: ignore[misc]


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
