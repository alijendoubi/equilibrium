"""Application settings loaded from environment variables (and an optional .env file)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]

DEFAULT_CORS_ORIGINS = "http://localhost:3000"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"


class Settings(BaseSettings):
    """Runtime configuration. Secrets are SecretStr so they never leak into logs or reprs."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        populate_by_name=True,
    )

    openai_api_key: SecretStr | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default=DEFAULT_OPENAI_MODEL, alias="OPENAI_MODEL")
    ncbi_api_key: SecretStr | None = Field(default=None, alias="NCBI_API_KEY")
    omim_api_key: SecretStr | None = Field(default=None, alias="OMIM_API_KEY")
    cors_origins: str = Field(default=DEFAULT_CORS_ORIGINS, alias="CORS_ORIGINS")
    log_level: LogLevel = Field(default="INFO", alias="LOG_LEVEL")

    @property
    def cors_origin_list(self) -> tuple[str, ...]:
        """CORS origins parsed from the comma-separated CORS_ORIGINS value."""
        return tuple(origin.strip() for origin in self.cors_origins.split(",") if origin.strip())

    @property
    def has_openai_key(self) -> bool:
        """True when an OpenAI key is configured (without exposing the value)."""
        key = self.openai_api_key
        return key is not None and bool(key.get_secret_value())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance (cached)."""
    return Settings()
