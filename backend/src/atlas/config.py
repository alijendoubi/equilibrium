"""Application settings loaded from environment variables (and an optional .env file)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]

DEFAULT_CORS_ORIGINS = "http://localhost:3000"
DEFAULT_OPENAI_MODEL_EXTRACT = "gpt-6.1-sol"
DEFAULT_OPENAI_MODEL_EXPLAIN = "gpt-6.1-sol"
DEFAULT_OPENAI_MODEL_RECONCILE = "gpt-6-luna"
DEFAULT_OPENAI_EMBED_MODEL = "text-embedding-3-small"
# Repo checkout default; the Docker image sets SNAPSHOT_PATH explicitly.
DEFAULT_SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "snapshot" / "atlas-snapshot.json"
)


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
    openai_model_extract: str = Field(
        default=DEFAULT_OPENAI_MODEL_EXTRACT, min_length=1, alias="OPENAI_MODEL_EXTRACT"
    )
    openai_model_explain: str = Field(
        default=DEFAULT_OPENAI_MODEL_EXPLAIN, min_length=1, alias="OPENAI_MODEL_EXPLAIN"
    )
    openai_model_reconcile: str = Field(
        default=DEFAULT_OPENAI_MODEL_RECONCILE, min_length=1, alias="OPENAI_MODEL_RECONCILE"
    )
    openai_embed_model: str = Field(
        default=DEFAULT_OPENAI_EMBED_MODEL, min_length=1, alias="OPENAI_EMBED_MODEL"
    )
    ncbi_api_key: SecretStr | None = Field(default=None, alias="NCBI_API_KEY")
    omim_api_key: SecretStr | None = Field(default=None, alias="OMIM_API_KEY")
    cors_origins: str = Field(default=DEFAULT_CORS_ORIGINS, alias="CORS_ORIGINS")
    log_level: LogLevel = Field(default="INFO", alias="LOG_LEVEL")
    snapshot_path: Path = Field(default=DEFAULT_SNAPSHOT_PATH, alias="SNAPSHOT_PATH")
    # Live OpenAI calls from the public /explain endpoint cost money: off by default, so
    # production serves the committed cache, then the template. Precompute with the CLI.
    explain_live: bool = Field(default=False, alias="EXPLAIN_LIVE")
    explain_rate_per_minute: int = Field(default=10, ge=1, le=600, alias="EXPLAIN_RATE_PER_MINUTE")
    query_rate_per_minute: int = Field(default=60, ge=1, le=600, alias="QUERY_RATE_PER_MINUTE")
    trusted_proxy_hops: int = Field(default=0, ge=0, le=5, alias="TRUSTED_PROXY_HOPS")
    frontend_api_token: SecretStr | None = Field(default=None, alias="FRONTEND_API_TOKEN")

    @property
    def cache_dir(self) -> Path:
        """data/cache next to the snapshot (works in the repo and in the Docker image)."""
        return self.snapshot_path.parent.parent / "cache"

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalise_log_level(cls, value: object) -> object:
        """Accept `info`, `Info`, etc. so a lowercase env value does not crash startup."""
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("cors_origins")
    @classmethod
    def _reject_wildcard_origin(cls, value: str) -> str:
        """Refuse `*`: list explicit origins so CORS stays safe if credentials are added later."""
        if any(origin.strip() == "*" for origin in value.split(",")):
            raise ValueError("CORS_ORIGINS must list explicit origins, not '*'")
        return value

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
