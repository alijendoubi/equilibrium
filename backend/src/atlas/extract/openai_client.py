"""Thin factory for the OpenAI client. All model calls in Atlas go through OpenAI."""

from openai import OpenAI

from atlas.config import Settings, get_settings


class OpenAIKeyMissingError(RuntimeError):
    """Raised when an OpenAI client is requested but OPENAI_API_KEY is not configured."""


def create_openai_client(settings: Settings | None = None) -> OpenAI:
    """Return an `openai.OpenAI` client built from settings.

    Raises OpenAIKeyMissingError (never echoing any key material) when no key is set.
    """
    resolved = settings if settings is not None else get_settings()
    key = resolved.openai_api_key
    if key is None or not key.get_secret_value().strip():
        msg = "OPENAI_API_KEY is not set. Add it to backend/.env or the environment."
        raise OpenAIKeyMissingError(msg)
    return OpenAI(api_key=key.get_secret_value().strip())
