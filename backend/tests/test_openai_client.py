"""The OpenAI client factory (no network)."""

import pytest
from openai import OpenAI

from atlas.config import Settings
from atlas.extract.openai_client import OpenAIKeyMissingError, create_openai_client


def test_factory_returns_client_with_configured_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", " sk-test-secret ")

    client = create_openai_client(Settings())

    assert isinstance(client, OpenAI)
    assert client.api_key == "sk-test-secret"


def test_factory_uses_cached_settings_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")

    assert isinstance(create_openai_client(), OpenAI)


@pytest.mark.parametrize("value", [None, "", "   "])
def test_factory_raises_clear_error_without_key(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    if value is not None:
        monkeypatch.setenv("OPENAI_API_KEY", value)

    with pytest.raises(OpenAIKeyMissingError, match="OPENAI_API_KEY is not set"):
        create_openai_client(Settings())
