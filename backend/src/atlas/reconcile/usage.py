"""OpenAI usage accounting for reconcile calls (feeds the snapshot manifest's openai_usage)."""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True)
class ModelUsage:
    """Calls and tokens for one model."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def plus(self, other: "ModelUsage") -> "ModelUsage":
        return ModelUsage(
            calls=self.calls + other.calls,
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )


@dataclass(frozen=True)
class UsageRecord:
    """Immutable per-model usage totals. Combine records with `merge`."""

    by_model: MappingProxyType[str, ModelUsage] = field(
        default_factory=lambda: MappingProxyType({})
    )

    @classmethod
    def single(cls, model: str, usage: ModelUsage) -> "UsageRecord":
        return cls(MappingProxyType({model: usage}))

    def merge(self, other: "UsageRecord") -> "UsageRecord":
        combined = dict(self.by_model)
        for model, usage in other.by_model.items():
            combined[model] = combined.get(model, ModelUsage()).plus(usage)
        return UsageRecord(MappingProxyType(combined))

    @property
    def total_calls(self) -> int:
        return sum(u.calls for u in self.by_model.values())

    def as_dict(self) -> dict[str, dict[str, int]]:
        return {
            model: {
                "calls": u.calls,
                "input_tokens": u.input_tokens,
                "output_tokens": u.output_tokens,
            }
            for model, u in sorted(self.by_model.items())
        }


def usage_from_response(response: Any) -> ModelUsage:
    """Read token counts from a Responses or Embeddings API response, defensively."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return ModelUsage(calls=1)
    input_tokens = getattr(usage, "input_tokens", None)
    if input_tokens is None:
        input_tokens = getattr(usage, "prompt_tokens", 0)
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    return ModelUsage(
        calls=1, input_tokens=int(input_tokens or 0), output_tokens=int(output_tokens)
    )
