"""JSON cache of validated explanations: data/cache/explain/explanations.json (committed).

Key = sha256(model, prompt_version, audience, sorted edge ids, hash of the edge content), so a
changed edge (new confidence, quote, ...) or a new prompt never serves a stale explanation.
``with_entry`` returns a NEW cache; call ``save`` to persist.
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Any

from atlas.explain.models import Audience
from atlas.explain.prompt import PROMPT_VERSION
from atlas.models.evidence import Edge, Node

CACHE_FORMAT_VERSION = 1
# backend/src/atlas/explain/cache.py -> repo root is parents[4].
DEFAULT_CACHE_PATH = (
    Path(__file__).resolve().parents[4] / "data" / "cache" / "explain" / "explanations.json"
)


def edge_content_hash(edges: Sequence[Edge], nodes: Mapping[str, Node]) -> str:
    """Hash of everything the prompt shows: edge payloads plus endpoint labels."""
    material = []
    for edge in sorted(edges, key=lambda e: e.id):
        labels = [nodes[i].label if i in nodes else i for i in (edge.source_id, edge.target_id)]
        material.append([edge.model_dump(mode="json"), labels])
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def explanation_key(
    model: str, audience: Audience, edges: Sequence[Edge], nodes: Mapping[str, Node]
) -> str:
    """Deterministic cache key for one (model, prompt, audience, edge set) combination."""
    material = json.dumps(
        [
            model,
            PROMPT_VERSION,
            audience,
            sorted(e.id for e in edges),
            edge_content_hash(edges, nodes),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class ExplanationCache:
    """Read-only map of cached explanation payloads (plain JSON dicts)."""

    def __init__(self, path: Path, entries: Mapping[str, Mapping[str, Any]] | None = None):
        self.path = path
        self._entries: Mapping[str, Mapping[str, Any]] = MappingProxyType(dict(entries or {}))

    @classmethod
    def load(cls, path: Path = DEFAULT_CACHE_PATH) -> "ExplanationCache":
        if not path.is_file():
            return cls(path)
        raw = json.loads(path.read_text(encoding="utf-8")).get("explanations", {})
        return cls(path, raw)

    def __len__(self) -> int:
        return len(self._entries)

    def get(self, key: str) -> Mapping[str, Any] | None:
        return self._entries.get(key)

    def with_entry(self, key: str, entry: Mapping[str, Any]) -> "ExplanationCache":
        return ExplanationCache(self.path, {**self._entries, key: dict(entry)})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format_version": CACHE_FORMAT_VERSION,
            "explanations": {key: self._entries[key] for key in sorted(self._entries)},
        }
        self.path.write_text(
            json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
        )
