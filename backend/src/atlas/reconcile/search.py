"""Global search index: lexical first (exact, synonym, prefix), then semantic via embeddings.

Hits match the frontend contract (frontend/src/lib/api/types.ts SearchResult): the API layer
wraps each hit's node_id with the node itself. `searched` lists what was looked at, so an
empty result can say so honestly.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from atlas.models.evidence import Node
from atlas.reconcile.embeddings import EmbeddingCache, Vector, cosine
from atlas.reconcile.normalize import match_key, normalize_text, token_jaccard
from atlas.reconcile.resolver import node_texts

MatchReason = Literal["exact", "synonym", "semantic"]

SCORE_EXACT = 1.0
SCORE_SYNONYM = 0.95
SCORE_PREFIX = 0.8
SCORE_TOKENS_BASE = 0.4
TOKEN_FLOOR = 0.5
SEMANTIC_FLOOR = 0.45


@dataclass(frozen=True)
class SearchHit:
    node_id: str
    score: float
    match_reason: MatchReason
    matched_text: str


def _lexical(query: str, node: Node) -> SearchHit | None:
    q_norm, q_key = normalize_text(query), match_key(query)
    if not q_norm:
        return None
    ids = {node.id.upper(), *(x.upper() for x in node.xrefs)}
    if normalize_text(node.label) == q_norm or query.strip().upper() in ids:
        return SearchHit(node.id, SCORE_EXACT, "exact", node.label)
    best: SearchHit | None = None
    for text in node_texts(node):
        key = match_key(text)
        if key == q_key:
            return SearchHit(node.id, SCORE_SYNONYM, "synonym", text)
        if key.startswith(q_key) and len(q_key) >= 3:
            hit = SearchHit(node.id, SCORE_PREFIX, "synonym", text)
        else:
            overlap = token_jaccard(query, text)
            if overlap < TOKEN_FLOOR:
                continue
            hit = SearchHit(node.id, SCORE_TOKENS_BASE + 0.3 * overlap, "synonym", text)
        if best is None or hit.score > best.score:
            best = hit
    return best


def _semantic(query_vector: Vector, node: Node, cache: EmbeddingCache) -> SearchHit | None:
    best: SearchHit | None = None
    for text in node_texts(node):
        vector = cache.get(text)
        if vector is None:
            continue
        score = cosine(query_vector, vector)
        if score >= SEMANTIC_FLOOR and (best is None or score > best.score):
            best = SearchHit(node.id, round(score * SCORE_PREFIX, 4), "semantic", text)
    return best


class SearchIndex:
    """Immutable search index over a fixed node set."""

    def __init__(self, nodes: Sequence[Node], embeddings: EmbeddingCache | None = None):
        self._nodes = tuple(sorted(nodes, key=lambda n: n.id))
        self._embeddings = embeddings

    @classmethod
    def build(
        cls, nodes: Iterable[Node], embeddings: EmbeddingCache | None = None
    ) -> "SearchIndex":
        return cls(tuple(nodes), embeddings)

    @property
    def searched(self) -> tuple[str, ...]:
        scopes = ["labels", "synonyms", "identifiers and cross-references"]
        if self._embeddings is not None and len(self._embeddings):
            scopes.append(f"semantic similarity ({self._embeddings.model})")
        return (f"{len(self._nodes)} atlas nodes: " + ", ".join(scopes),)

    def search(
        self,
        query: str,
        types: Iterable[str] | None = None,
        limit: int = 10,
        query_vector: Vector | None = None,
    ) -> tuple[SearchHit, ...]:
        """Best hit per node, sorted by score then id. `query_vector` enables semantic hits;
        if omitted, the cached vector for the query text is used when present."""
        wanted = set(types) if types else None
        vector = query_vector
        if vector is None and self._embeddings is not None:
            vector = self._embeddings.get(query)
        hits: list[SearchHit] = []
        for node in self._nodes:
            if wanted is not None and str(node.type) not in wanted:
                continue
            hit = _lexical(query, node)
            if hit is None and vector is not None and self._embeddings is not None:
                hit = _semantic(vector, node, self._embeddings)
            if hit is not None:
                hits.append(hit)
        hits.sort(key=lambda h: (-h.score, h.node_id))
        return tuple(hits[: max(limit, 0)])
