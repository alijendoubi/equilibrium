"""Request/response models for POST /api/v1/explain."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Audience = Literal["family", "researcher"]
ExplainSource = Literal["cache", "live", "template"]
MAX_EDGES = 12
MAX_EDGE_ID_LENGTH = 64

_FROZEN = ConfigDict(frozen=True, extra="forbid")


class ExplainRequest(BaseModel):
    """Edges to explain (in path order) and who the explanation is for."""

    model_config = _FROZEN

    edge_ids: list[str] = Field(min_length=1, max_length=MAX_EDGES)
    audience: Audience = "family"

    @field_validator("edge_ids")
    @classmethod
    def _clean_ids(cls, value: list[str]) -> list[str]:
        """Strip, reject blanks/overlong ids and drop duplicates (first occurrence wins)."""
        cleaned = [item.strip() for item in value]
        if any(not item or len(item) > MAX_EDGE_ID_LENGTH for item in cleaned):
            raise ValueError("edge ids must be non-empty and at most 64 characters")
        return list(dict.fromkeys(cleaned))


class ExplainStep(BaseModel):
    """One plain-language sentence or short paragraph, citing the edges it rests on."""

    model_config = _FROZEN

    text: str = Field(min_length=1)
    edge_ids: list[str] = Field(min_length=1)
    is_hypothesis: bool = False


class ExplainResponse(BaseModel):
    """A cited explanation; ``source`` says cache, live OpenAI call, or deterministic template."""

    model_config = _FROZEN

    steps: list[ExplainStep]
    summary: str
    caveats: list[str]
    source: ExplainSource
    model: str | None
    prompt_version: str
    ai_generated: bool
