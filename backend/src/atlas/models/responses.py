"""API response models: mirror frontend/src/lib/api/types.ts (the frontend contract).

Nodes and edges are the evidence-model objects themselves, so their JSON is exactly what
``atlas-snapshot.json`` holds. Every model is frozen; lists are tuples.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer

from atlas.models.evidence import Edge, Node

_FROZEN = ConfigDict(frozen=True)

MatchReason = Literal["exact", "synonym", "semantic"]
CoverageStatus = Literal["supported", "weak", "gap"]
CoverageResult = Literal["supported", "weak_routes_only", "no_supported_route"]


class SearchResult(BaseModel):
    model_config = _FROZEN

    node: Node
    score: float
    match_reason: MatchReason
    matched_text: str


class SearchResponse(BaseModel):
    model_config = _FROZEN

    query: str
    results: tuple[SearchResult, ...]
    searched: tuple[str, ...]


class NodeCounts(BaseModel):
    model_config = _FROZEN

    edges: int
    by_relation: dict[str, int]


class NodeSummary(BaseModel):
    model_config = _FROZEN

    node: Node
    counts: NodeCounts
    edges: tuple[Edge, ...]
    neighbors: tuple[Node, ...]
    cluster_id: str | None
    coverage_status: CoverageStatus


class NeighborsResponse(BaseModel):
    """Not in types.ts yet: the node's (filtered) edges and the nodes at their other end."""

    model_config = _FROZEN

    node_id: str
    edges: tuple[Edge, ...]
    nodes: tuple[Node, ...]


class EdgeDetail(BaseModel):
    """Not in types.ts yet: an edge, its endpoints, the edges it cites or is contradicted by."""

    model_config = _FROZEN

    edge: Edge
    source: Node
    target: Node
    contradictions: tuple[Edge, ...]
    supporting_edges: tuple[Edge, ...]


class SourceSearched(BaseModel):
    """`source_version` and `query` are optional (never null) in the frontend schema."""

    model_config = _FROZEN

    source: str
    source_version: str | None = None
    query: str | None = None
    records_found: int = Field(ge=0)

    @model_serializer(mode="wrap")
    def _drop_none(self, handler: Any) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        return {key: value for key, value in data.items() if value is not None}


class WeakLead(BaseModel):
    model_config = _FROZEN

    path_edge_ids: tuple[str, ...]
    min_confidence: float = Field(ge=0.0, le=1.0)
    why_weak: str


class CoverageReport(BaseModel):
    model_config = _FROZEN

    query: str
    result: CoverageResult
    searched: tuple[SourceSearched, ...]
    not_searched: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    weak_leads: tuple[WeakLead, ...]
    next_questions: tuple[str, ...]


class PathOut(BaseModel):
    """nodes[i] and nodes[i + 1] are joined by edges[i] (in either direction)."""

    model_config = _FROZEN

    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    cost: float = Field(ge=0.0)
    has_inferred: bool
    has_contradiction: bool


class PathResponse(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    paths: tuple[PathOut, ...]
    coverage: CoverageReport | None


class Partner(BaseModel):
    model_config = _FROZEN

    node: Node
    why: str
    edge_ids: tuple[str, ...]


class ReusableAsset(BaseModel):
    model_config = _FROZEN

    node: Node
    reusable: str
    differs: str
    edge_ids: tuple[str, ...]


class NextExperiment(BaseModel):
    model_config = _FROZEN

    text: str
    is_hypothesis: bool = True
    edge_ids: tuple[str, ...]


class SharedInvestigator(BaseModel):
    """An investigator whose RePORTER projects span two communities (network overlap, #38)."""

    model_config = _FROZEN

    node: Node
    communities: tuple[str, ...]
    target_ids: tuple[str, ...]
    why: str
    edge_ids: tuple[str, ...]


class ActionsResponse(BaseModel):
    model_config = _FROZEN

    disease_id: str
    partners: tuple[Partner, ...]
    assets: tuple[ReusableAsset, ...]
    next_experiment: NextExperiment | None
    review_checklist: tuple[str, ...]
    coverage: CoverageReport | None
    # Additive and optional (#38): not in frontend types.ts yet; zod drops unknown keys.
    shared_investigators: tuple[SharedInvestigator, ...] = ()
