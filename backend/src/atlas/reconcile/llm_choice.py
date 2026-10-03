"""OpenAI structured choice for ambiguous mentions (gpt-6-luna by default).

The model may only answer with an id from the candidate list or "none": the JSON schema
enumerates the allowed ids, and the answer is validated again here. Every decision is cached
in data/cache/reconcile/decisions.json so reruns are deterministic and work offline.
"""

import hashlib
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from atlas.reconcile.embeddings import is_offline
from atlas.reconcile.usage import UsageRecord, usage_from_response

logger = logging.getLogger(__name__)

PROMPT_VERSION = "reconcile-v1"
NONE_ANSWER = "none"
CACHE_FORMAT_VERSION = 1
INSTRUCTIONS = (
    "You map a biomedical name to exactly one entity from a fixed candidate list. "
    "Choose the candidate that denotes the same disease, gene, phenotype or concept. "
    "If none of them is the same entity, answer 'none'. Never answer with an id that is "
    "not in the list. Give a one-sentence rationale."
)


@dataclass(frozen=True)
class Candidate:
    """A node offered to the model."""

    node_id: str
    label: str
    node_type: str
    synonyms: tuple[str, ...] = ()


@dataclass(frozen=True)
class Choice:
    """The model's (or cache's) decision."""

    node_id: str | None
    rationale: str
    model: str
    prompt_version: str = PROMPT_VERSION


def decision_key(model: str, mention: str, candidate_ids: Sequence[str]) -> str:
    material = json.dumps([model, PROMPT_VERSION, mention, sorted(candidate_ids)])
    return hashlib.sha256(material.encode()).hexdigest()


class DecisionCache:
    """Read-only map of cached decisions; `with_choice` returns a new cache."""

    def __init__(self, path: Path, decisions: Mapping[str, Choice] | None = None):
        self.path = path
        self._decisions: Mapping[str, Choice] = MappingProxyType(dict(decisions or {}))

    @classmethod
    def load(cls, path: Path) -> "DecisionCache":
        if not path.exists():
            return cls(path)
        raw = json.loads(path.read_text(encoding="utf-8")).get("decisions", {})
        return cls(path, {key: Choice(**value) for key, value in raw.items()})

    def __len__(self) -> int:
        return len(self._decisions)

    def get(self, key: str) -> Choice | None:
        return self._decisions.get(key)

    def with_choice(self, key: str, choice: Choice) -> "DecisionCache":
        return DecisionCache(self.path, {**self._decisions, key: choice})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format_version": CACHE_FORMAT_VERSION,
            "decisions": {
                key: {
                    "node_id": c.node_id,
                    "rationale": c.rationale,
                    "model": c.model,
                    "prompt_version": c.prompt_version,
                }
                for key, c in sorted(self._decisions.items())
            },
        }
        self.path.write_text(json.dumps(payload, indent=1), encoding="utf-8")


def _schema(candidate_ids: Sequence[str]) -> dict[str, Any]:
    return {
        "format": {
            "type": "json_schema",
            "name": "reconcile_choice",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "node_id": {"type": "string", "enum": [*candidate_ids, NONE_ANSWER]},
                    "rationale": {"type": "string"},
                },
                "required": ["node_id", "rationale"],
                "additionalProperties": False,
            },
        }
    }


def _prompt(mention: str, candidates: Sequence[Candidate]) -> str:
    lines = [f"Name to resolve: {mention!r}", "Candidates:"]
    for c in candidates:
        synonyms = "; ".join(c.synonyms[:8]) or "-"
        lines.append(f"- {c.node_id} [{c.node_type}] {c.label} (synonyms: {synonyms})")
    return "\n".join(lines)


def parse_choice(output_text: str, candidate_ids: Sequence[str], model: str) -> Choice:
    """Validate the model output; anything outside the candidate list becomes 'none'."""
    try:
        data = json.loads(output_text)
        answer = str(data["node_id"])
        rationale = str(data.get("rationale", ""))
    except (ValueError, KeyError, TypeError):
        return Choice(None, "unparseable model output", model)
    if answer not in candidate_ids:
        return Choice(None, rationale or "model chose none", model)
    return Choice(answer, rationale, model)


def choose(
    mention: str,
    candidates: Sequence[Candidate],
    *,
    client: Any,
    model: str,
    cache: DecisionCache,
) -> tuple[Choice, DecisionCache, UsageRecord]:
    """Pick one candidate id (or None). Uses the cache first; never calls the API offline."""
    ids = [c.node_id for c in candidates]
    key = decision_key(model, mention, ids)
    cached = cache.get(key)
    if cached is not None:
        return cached, cache, UsageRecord()
    if client is None or is_offline():
        return Choice(None, "ambiguous; OpenAI unavailable (offline)", model), cache, UsageRecord()
    response = client.responses.create(
        model=model,
        instructions=INSTRUCTIONS,
        input=_prompt(mention, candidates),
        text=_schema(ids),
    )
    choice = parse_choice(response.output_text, ids, model)
    usage = UsageRecord.single(model, usage_from_response(response))
    logger.info("Reconcile choice for %r -> %s", mention, choice.node_id)
    return choice, cache.with_choice(key, choice), usage
