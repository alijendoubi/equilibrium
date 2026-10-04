"""Resolve surface names to node ids and merge duplicate nodes.

Order (cheapest and most certain first): exact label -> xref/id -> normalised synonym ->
embedding similarity -> OpenAI structured choice among the top candidates. Ids are only ever
taken from the given nodes; nothing is invented.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from atlas.models.evidence import CURIE_PATTERN, Node, NodeType
from atlas.reconcile.embeddings import EmbeddingCache, cosine
from atlas.reconcile.llm_choice import Candidate, DecisionCache, choose
from atlas.reconcile.normalize import match_key, normalize_text, token_jaccard
from atlas.reconcile.usage import UsageRecord

Method = Literal["exact", "xref", "synonym", "embedding", "llm", "none"]

EMBED_ACCEPT = 0.85
EMBED_MARGIN = 0.05
CANDIDATE_FLOOR = 0.45
LEXICAL_FLOOR = 0.34
TOP_K = 5

_CURIE = re.compile(CURIE_PATTERN)

# Lower rank = more authoritative id prefix, per node type.
_AUTHORITY: Mapping[NodeType, tuple[str, ...]] = {
    NodeType.DISEASE: ("MONDO", "ORPHA", "OMIM", "DOID", "MESH"),
    NodeType.GENE: ("HGNC", "NCBIGene", "ENSEMBL", "OMIM"),
    NodeType.PHENOTYPE: ("HP",),
    NodeType.MECHANISM: ("GO", "REACT"),
}


@dataclass(frozen=True)
class Resolution:
    """How one mention was resolved."""

    mention: str
    node_id: str | None
    method: Method
    score: float
    candidates: tuple[tuple[str, float], ...] = ()
    rationale: str | None = None


@dataclass(frozen=True)
class ResolveResult:
    resolutions: tuple[Resolution, ...]
    usage: UsageRecord = field(default_factory=UsageRecord)
    decisions: DecisionCache | None = None


def node_texts(node: Node) -> tuple[str, ...]:
    """Label first, then synonyms."""
    return (node.label, *node.synonyms)


def _by_exact(mention: str, nodes: Sequence[Node]) -> list[Node]:
    target = normalize_text(mention)
    return [n for n in nodes if normalize_text(n.label) == target]


def _by_xref(mention: str, nodes: Sequence[Node]) -> list[Node]:
    text = mention.strip()
    if not _CURIE.match(text):
        return []
    upper = text.upper()
    return [n for n in nodes if n.id.upper() == upper or upper in {x.upper() for x in n.xrefs}]


def _by_synonym(mention: str, nodes: Sequence[Node]) -> list[Node]:
    key = match_key(mention)
    if not key:
        return []
    return [n for n in nodes if key in {match_key(t) for t in node_texts(n)}]


def _embedding_scores(
    mention: str, nodes: Sequence[Node], cache: EmbeddingCache
) -> list[tuple[str, float]]:
    query = cache.get(mention)
    if query is None:
        return []
    scored: list[tuple[str, float]] = []
    for node in nodes:
        vectors = [v for v in (cache.get(t) for t in node_texts(node)) if v is not None]
        if vectors:
            scored.append((node.id, max(cosine(query, v) for v in vectors)))
    return sorted(scored, key=lambda item: (-item[1], item[0]))


def _lexical_scores(mention: str, nodes: Sequence[Node]) -> list[tuple[str, float]]:
    scored = [(n.id, max(token_jaccard(mention, t) for t in node_texts(n))) for n in nodes]
    return sorted([s for s in scored if s[1] > 0], key=lambda item: (-item[1], item[0]))


def _candidates(ids: Sequence[str], index: Mapping[str, Node]) -> list[Candidate]:
    return [Candidate(i, index[i].label, str(index[i].type), tuple(index[i].synonyms)) for i in ids]


class _Resolver:
    def __init__(
        self,
        nodes: Sequence[Node],
        embeddings: EmbeddingCache | None,
        decisions: DecisionCache | None,
        client: Any,
        model: str,
    ):
        self.nodes = tuple(nodes)
        self.index = {n.id: n for n in self.nodes}
        self.embeddings = embeddings
        self.decisions = decisions
        self.client = client
        self.model = model
        self.usage = UsageRecord()

    def _ask(self, mention: str, ranked: Sequence[tuple[str, float]], why: str) -> Resolution:
        top = tuple(ranked[:TOP_K])
        if self.decisions is None:
            return Resolution(mention, None, "none", 0.0, top, f"{why}; no decision cache")
        choice, self.decisions, usage = choose(
            mention,
            _candidates([i for i, _ in top], self.index),
            client=self.client,
            model=self.model,
            cache=self.decisions,
        )
        self.usage = self.usage.merge(usage)
        if choice.node_id is None:
            return Resolution(mention, None, "none", 0.0, top, choice.rationale)
        score = dict(top).get(choice.node_id, 0.0)
        return Resolution(mention, choice.node_id, "llm", score, top, choice.rationale)

    def _deterministic(self, mention: str) -> Resolution | None:
        steps: tuple[tuple[Method, Any, float], ...] = (
            ("exact", _by_exact, 1.0),
            ("xref", _by_xref, 1.0),
            ("synonym", _by_synonym, 0.95),
        )
        for method, finder, score in steps:
            found: list[Node] = finder(mention, self.nodes)
            if len(found) == 1:
                return Resolution(mention, found[0].id, method, score)
            if len(found) > 1:
                ranked = [(n.id, score) for n in sorted(found, key=lambda n: n.id)]
                return self._ask(mention, ranked, f"several {method} matches")
        return None

    def resolve_one(self, mention: str) -> Resolution:
        settled = self._deterministic(mention)
        if settled is not None:
            return settled
        ranked = _embedding_scores(mention, self.nodes, self.embeddings) if self.embeddings else []
        if ranked:
            best = ranked[0][1]
            margin = best - ranked[1][1] if len(ranked) > 1 else best
            if best >= EMBED_ACCEPT and margin >= EMBED_MARGIN:
                return Resolution(mention, ranked[0][0], "embedding", best, tuple(ranked[:TOP_K]))
            if best >= CANDIDATE_FLOOR:
                return self._ask(mention, ranked, "ambiguous embedding match")
            return Resolution(mention, None, "none", 0.0, tuple(ranked[:TOP_K]), "no close match")
        lexical = _lexical_scores(mention, self.nodes)
        if lexical and lexical[0][1] >= LEXICAL_FLOOR:
            return self._ask(mention, lexical, "partial lexical match; no embeddings")
        return Resolution(mention, None, "none", 0.0, tuple(lexical[:TOP_K]), "no match")


def resolve(
    mentions: Sequence[str],
    nodes: Sequence[Node],
    *,
    embeddings: EmbeddingCache | None = None,
    decisions: DecisionCache | None = None,
    client: Any = None,
    model: str = "gpt-6-luna",
) -> ResolveResult:
    """Resolve each mention to at most one node id. Embeddings for mentions must be cached
    (use EmbeddingCache.with_fetched first); the LLM is only used for ambiguous cases."""
    resolver = _Resolver(nodes, embeddings, decisions, client, model)
    resolutions = tuple(resolver.resolve_one(m) for m in mentions)
    return ResolveResult(resolutions, resolver.usage, resolver.decisions)


# --- duplicate merging -------------------------------------------------------------------


def _rank(node: Node) -> tuple[int, str]:
    prefixes = _AUTHORITY.get(node.type, ())
    prefix = node.id.split(":", 1)[0]
    rank = prefixes.index(prefix) if prefix in prefixes else len(prefixes)
    return rank, node.id


def _groups(nodes: Sequence[Node]) -> list[list[Node]]:
    parent = list(range(len(nodes)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owner: dict[tuple[str, str], int] = {}
    for i, node in enumerate(nodes):
        keys = {("id", node.id.upper())} | {("id", x.upper()) for x in node.xrefs}
        keys.add(("label", match_key(node.label)))
        for kind, value in sorted(keys):
            slot = (f"{node.type}:{kind}", value)
            if slot in owner:
                parent[find(i)] = find(owner[slot])
            else:
                owner[slot] = i
    grouped: dict[int, list[Node]] = {}
    for i, node in enumerate(nodes):
        grouped.setdefault(find(i), []).append(node)
    return list(grouped.values())


def _merge_group(group: Sequence[Node]) -> Node:
    ordered = sorted(group, key=_rank)
    head = ordered[0]
    synonyms: dict[str, None] = {}
    xrefs: dict[str, None] = {}
    attributes: dict[str, str] = {}
    for node in reversed(ordered):  # the head's attributes win
        attributes.update(node.attributes)
    for node in ordered:
        for text in node_texts(node):
            if text != head.label:
                synonyms.setdefault(text, None)
        for xref in (node.id, *node.xrefs):
            if xref != head.id:
                xrefs.setdefault(xref, None)
    return Node.model_validate(
        {
            "id": head.id,
            "type": head.type,
            "label": head.label,
            "synonyms": tuple(synonyms),
            "xrefs": tuple(xrefs),
            "attributes": attributes,
        }
    )


def merge_duplicates(nodes: Sequence[Node]) -> tuple[tuple[Node, ...], Mapping[str, str]]:
    """Merge nodes of the same type that share an id/xref or a normalised label.

    Returns canonical nodes (sorted by id) and an alias map {old_id: canonical_id}
    covering every merged-away id. Input nodes are never modified.
    """
    canonical: list[Node] = []
    aliases: dict[str, str] = {}
    for group in _groups(nodes):
        merged = _merge_group(group) if len(group) > 1 else group[0]
        canonical.append(merged)
        for node in group:
            if node.id != merged.id:
                aliases[node.id] = merged.id
    return tuple(sorted(canonical, key=lambda n: n.id)), aliases
