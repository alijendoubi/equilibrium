"""OpenAI embedding cache: JSON-backed, keyed by model + normalised text, offline-safe.

The cache file lives at data/cache/embeddings/<model>.json and is committed, so the demo and
`make data-offline` never need the API. `with_fetched` returns a NEW cache (immutable style);
call `save` to persist it.
"""

import hashlib
import json
import logging
import math
import os
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Any

from atlas.reconcile.normalize import normalize_text
from atlas.reconcile.usage import UsageRecord, usage_from_response

logger = logging.getLogger(__name__)

Vector = tuple[float, ...]
DEFAULT_BATCH_SIZE = 100
CACHE_FORMAT_VERSION = 1


def is_offline() -> bool:
    """True when ATLAS_OFFLINE=1: only cached vectors and decisions are used."""
    return os.environ.get("ATLAS_OFFLINE", "").strip() in {"1", "true", "yes"}


def embedding_key(model: str, text: str) -> str:
    """Stable cache key: sha256 of model and normalised text."""
    return hashlib.sha256(f"{model}\n{normalize_text(text)}".encode()).hexdigest()


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    """Cosine similarity; 0.0 for empty, zero or mismatched vectors."""
    if not left or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / norm if norm else 0.0


class EmbeddingCache:
    """Read-only view over cached vectors for one embedding model."""

    def __init__(self, model: str, path: Path, vectors: Mapping[str, Vector] | None = None):
        self.model = model
        self.path = path
        self._vectors: Mapping[str, Vector] = MappingProxyType(dict(vectors or {}))

    @classmethod
    def load(cls, model: str, directory: Path) -> "EmbeddingCache":
        path = directory / f"{model}.json"
        if not path.exists():
            return cls(model, path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        vectors = {key: tuple(float(x) for x in vec) for key, vec in raw.get("vectors", {}).items()}
        return cls(model, path, vectors)

    def __len__(self) -> int:
        return len(self._vectors)

    def get(self, text: str) -> Vector | None:
        return self._vectors.get(embedding_key(self.model, text))

    def missing(self, texts: Iterable[str]) -> tuple[str, ...]:
        """Distinct texts (by key) that have no cached vector, first-occurrence order."""
        seen: dict[str, str] = {}
        for text in texts:
            key = embedding_key(self.model, text)
            if key not in self._vectors and normalize_text(text):
                seen.setdefault(key, text)
        return tuple(seen.values())

    def with_fetched(
        self, texts: Iterable[str], client: Any, batch_size: int = DEFAULT_BATCH_SIZE
    ) -> tuple["EmbeddingCache", UsageRecord]:
        """Embed missing texts via the OpenAI embeddings API; return a new cache + usage.

        Retries and timeouts come from the OpenAI client (max_retries / timeout).
        """
        todo = self.missing(texts)
        if not todo:
            return self, UsageRecord()
        if client is None or is_offline():
            logger.warning("Embeddings missing for %d texts and no client (offline)", len(todo))
            return self, UsageRecord()
        vectors = dict(self._vectors)
        usage = UsageRecord()
        for start in range(0, len(todo), batch_size):
            batch = list(todo[start : start + batch_size])
            response = client.embeddings.create(model=self.model, input=batch)
            usage = usage.merge(UsageRecord.single(self.model, usage_from_response(response)))
            for text, item in zip(batch, response.data, strict=True):
                vectors[embedding_key(self.model, text)] = tuple(float(x) for x in item.embedding)
        return EmbeddingCache(self.model, self.path, vectors), usage

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format_version": CACHE_FORMAT_VERSION,
            "model": self.model,
            "vectors": {key: list(self._vectors[key]) for key in sorted(self._vectors)},
        }
        self.path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
