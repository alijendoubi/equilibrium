"""Graph read API (issues #22, #37): search, nodes, neighbors, edges, paths, coverage, actions.

All routes are read-only and return 503 when no snapshot is loaded (``StoreDep``). Node ids are
CURIEs (``MONDO:0009266``); send them raw or URL-encoded (``MONDO%3A0009266``).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from atlas.api.cluster_routes import ClusterIndexDep
from atlas.api.deps import StoreDep
from atlas.graph import queries
from atlas.graph.actions import build_actions
from atlas.graph.coverage import coverage_report, coverage_status
from atlas.graph.store import GraphStore
from atlas.models.evidence import EvidenceType, Node, NodeType, Relation
from atlas.models.responses import (
    ActionsResponse,
    CoverageReport,
    EdgeDetail,
    NeighborsResponse,
    NodeSummary,
    PathResponse,
    SearchResponse,
    SearchResult,
)
from atlas.reconcile.search import SearchIndex

MAX_SEARCH_LIMIT = 50
DEFAULT_SEARCH_LIMIT = 10

router = APIRouter(prefix="/api/v1", tags=["graph"])


def get_search_index(request: Request, store: StoreDep) -> SearchIndex:
    """The index built at startup; built lazily if the app state has none yet."""
    index: SearchIndex | None = getattr(request.app.state, "search_index", None)
    if index is None:
        index = SearchIndex.build(store.nodes())
        request.app.state.search_index = index
    return index


SearchIndexDep = Annotated[SearchIndex, Depends(get_search_index)]


def _split(values: list[str] | None) -> list[str]:
    """Accept both ?x=a,b and ?x=a&x=b."""
    return [part.strip() for value in values or [] for part in value.split(",") if part.strip()]


def _enum_set(values: list[str] | None, enum: Any, name: str) -> frozenset[Any] | None:
    parts = _split(values)
    if not parts:
        return None
    try:
        return frozenset(enum(part) for part in parts)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"unknown {name}: {exc}") from exc


def _node_or_404(store: GraphStore, node_id: str) -> Node:
    node = store.get_node(node_id.strip())
    if node is None:
        raise HTTPException(status_code=404, detail=f"unknown node {node_id}")
    return node


@router.get("/search", response_model=SearchResponse)
def search(
    store: StoreDep,
    index: SearchIndexDep,
    q: Annotated[str, Query(max_length=200)] = "",
    types: Annotated[list[str] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_SEARCH_LIMIT)] = DEFAULT_SEARCH_LIMIT,
) -> SearchResponse:
    """Ranked nodes with why they matched (exact / synonym / semantic from cached vectors)."""
    query = q.strip()
    if not query:
        raise HTTPException(status_code=422, detail="q must not be empty")
    wanted = _enum_set(types, NodeType, "node type")
    hits = index.search(query, types=[t.value for t in wanted] if wanted else None, limit=limit)
    results = []
    for hit in hits:
        node = store.get_node(hit.node_id)
        if node is not None:
            results.append(
                SearchResult(
                    node=node,
                    score=hit.score,
                    match_reason=hit.match_reason,
                    matched_text=hit.matched_text,
                )
            )
    return SearchResponse(query=q, results=tuple(results), searched=index.searched)


@router.get("/nodes/{node_id}/neighbors", response_model=NeighborsResponse)
def node_neighbors(
    node_id: str,
    store: StoreDep,
    relations: Annotated[list[str] | None, Query()] = None,
    min_confidence: Annotated[float, Query(ge=0.0, le=1.0)] = 0.0,
    evidence: Annotated[list[str] | None, Query()] = None,
    types: Annotated[list[str] | None, Query()] = None,
) -> NeighborsResponse:
    """Filtered edges touching the node, plus the nodes at their other end."""
    node = _node_or_404(store, node_id)
    return queries.neighbors(
        store,
        node.id,
        relations=_enum_set(relations, Relation, "relation"),
        min_confidence=min_confidence,
        evidence=_enum_set(evidence, EvidenceType, "evidence type"),
        types=_enum_set(types, NodeType, "node type"),
    )


@router.get("/nodes/{node_id}", response_model=NodeSummary)
def node_summary(node_id: str, store: StoreDep, clusters: ClusterIndexDep) -> NodeSummary:
    """Node card: counts, top edges (best first), neighbors, cluster (diseases), coverage."""
    node = _node_or_404(store, node_id)
    edges = queries.top_edges(store, node.id)
    return NodeSummary(
        node=node,
        counts=queries.node_counts(store.edges_for(node.id)),
        edges=edges,
        neighbors=queries.nodes_across(store, node.id, edges),
        cluster_id=clusters.cluster_of(node.id),
        coverage_status=coverage_status(store, node),
    )


@router.get("/edges/{edge_id}", response_model=EdgeDetail)
def edge_detail(edge_id: str, store: StoreDep) -> EdgeDetail:
    """One edge with full provenance, endpoints, contradicting and supporting edges."""
    edge = store.get_edge(edge_id.strip())
    if edge is None:
        raise HTTPException(status_code=404, detail=f"unknown edge {edge_id}")
    return queries.edge_detail(store, edge)


@router.get("/paths", response_model=PathResponse)
def paths(
    store: StoreDep,
    from_id: Annotated[str, Query(alias="from", min_length=1)],
    to_id: Annotated[str, Query(alias="to", min_length=1)],
    k: Annotated[int, Query(ge=1, le=queries.MAX_PATHS)] = 3,
) -> PathResponse:
    """k best evidence paths; a coverage report for `to` (else `from`) when none exist."""
    source = _node_or_404(store, from_id)
    target = _node_or_404(store, to_id)
    if source.id == target.id:
        raise HTTPException(status_code=422, detail="from and to must differ")
    found = queries.find_paths(store, source.id, target.id, k)
    coverage: CoverageReport | None = None
    if not found:
        target_report = coverage_report(store, target)
        source_report = coverage_report(store, source)
        coverage = target_report if target_report.result != "supported" else source_report
    return PathResponse(from_=source.id, to=target.id, paths=found, coverage=coverage)


@router.get("/coverage/{node_id}", response_model=CoverageReport)
def coverage(node_id: str, store: StoreDep) -> CoverageReport:
    """What was searched for this node, what is missing, and what to ask next."""
    return coverage_report(store, _node_or_404(store, node_id))


@router.get("/actions/{disease_id}", response_model=ActionsResponse)
def actions(disease_id: str, store: StoreDep) -> ActionsResponse:
    """Partners, reusable assets, a next-experiment hypothesis, or a coverage report."""
    node = _node_or_404(store, disease_id)
    if node.type is not NodeType.DISEASE:
        raise HTTPException(status_code=404, detail=f"{disease_id} is not a disease")
    return build_actions(store, node)
