"""Read-only graph queries behind the API: node summary, neighbors, edge detail, paths.

Pure functions over a ``GraphStore``; every result is deterministically ordered.

Path ranking (GET /api/v1/paths):

* Traversal treats the graph as undirected. Parallel edges between the same pair collapse to
  the lowest-cost one (ties broken by edge id).
* Reported ``cost`` = sum over edges of ``-log(max(confidence, 0.01))`` plus ``INFERRED_PENALTY``
  per inferred edge.
* Ranking weight = cost + a hub penalty: every edge touching a phenotype node carries
  ``PHENOTYPE_HUB_PENALTY / 2`` per phenotype endpoint, so routing *through* a phenotype costs
  ``PHENOTYPE_HUB_PENALTY`` extra. Phenotypes are shared by hundreds of diseases, so without it
  disease -> phenotype -> disease shortcuts would dominate every query; with it they appear only
  when no gene/mechanism/study route exists. Paths are returned in ranking order.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from functools import lru_cache
from itertools import islice
from typing import Any

import networkx as nx

from atlas.graph.store import GraphStore
from atlas.models.evidence import Edge, EvidenceType, Node, NodeType, Relation
from atlas.models.responses import EdgeDetail, NeighborsResponse, NodeCounts, PathOut

CONFIDENCE_FLOOR = 0.01
INFERRED_PENALTY = 1.0
PHENOTYPE_HUB_PENALTY = 3.0
MAX_PATHS = 5
MAX_PATH_EDGES = 8
MAX_CANDIDATE_PATHS = 200
MAX_TOP_EDGES = 25


def edge_cost(edge: Edge) -> float:
    """-log(confidence) with a floor, plus the inferred-edge penalty."""
    cost = -math.log(max(edge.confidence, CONFIDENCE_FLOOR))
    if edge.evidence_type is EvidenceType.INFERRED:
        cost += INFERRED_PENALTY
    return cost


def other_end(edge: Edge, node_id: str) -> str:
    return edge.target_id if edge.source_id == node_id else edge.source_id


def top_edge_key(edge: Edge) -> tuple[bool, float, str]:
    """Best first: non-phenotype edges, then higher confidence, then id."""
    return (edge.relation is Relation.HAS_PHENOTYPE, -edge.confidence, edge.id)


# ---- node summary / neighbors / edge detail -----------------------------------------------


def node_counts(edges: Iterable[Edge]) -> NodeCounts:
    edge_list = tuple(edges)
    by_relation = Counter(edge.relation.value for edge in edge_list)
    return NodeCounts(edges=len(edge_list), by_relation=dict(sorted(by_relation.items())))


def top_edges(store: GraphStore, node_id: str, limit: int = MAX_TOP_EDGES) -> tuple[Edge, ...]:
    return tuple(sorted(store.edges_for(node_id), key=top_edge_key)[:limit])


def nodes_across(store: GraphStore, node_id: str, edges: Iterable[Edge]) -> tuple[Node, ...]:
    """Distinct nodes at the other end of ``edges``, sorted by id."""
    ids = sorted({other_end(edge, node_id) for edge in edges} - {node_id})
    return tuple(node for node in (store.get_node(i) for i in ids) if node is not None)


def neighbors(
    store: GraphStore,
    node_id: str,
    relations: frozenset[Relation] | None = None,
    min_confidence: float = 0.0,
    evidence: frozenset[EvidenceType] | None = None,
    types: frozenset[NodeType] | None = None,
) -> NeighborsResponse:
    """Edges touching the node that pass every filter, plus the nodes at their other end."""
    kept: list[Edge] = []
    for edge in store.edges_for(node_id, relations=relations):
        if edge.confidence < min_confidence:
            continue
        if evidence is not None and edge.evidence_type not in evidence:
            continue
        other = store.get_node(other_end(edge, node_id))
        if types is not None and (other is None or other.type not in types):
            continue
        kept.append(edge)
    edges = tuple(sorted(kept, key=top_edge_key))
    return NeighborsResponse(
        node_id=node_id, edges=edges, nodes=nodes_across(store, node_id, edges)
    )


def edge_detail(store: GraphStore, edge: Edge) -> EdgeDetail:
    """The edge, its endpoints, resolved contradicting / supporting edges (unknown ids skipped)."""

    def resolve(ids: Iterable[str]) -> tuple[Edge, ...]:
        found = (store.get_edge(i) for i in sorted(set(ids)))
        return tuple(e for e in found if e is not None)

    source = store.get_node(edge.source_id)
    target = store.get_node(edge.target_id)
    if source is None or target is None:  # pragma: no cover - the store rejects dangling edges
        raise ValueError(f"edge {edge.id} has a dangling endpoint")
    return EdgeDetail(
        edge=edge,
        source=source,
        target=target,
        contradictions=resolve(edge.contradicted_by),
        supporting_edges=resolve(edge.provenance.supporting_edge_ids),
    )


# ---- paths ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Hop:
    edge: Edge
    cost: float


def _hub_penalty(node: Node | None) -> float:
    return (
        PHENOTYPE_HUB_PENALTY / 2 if node is not None and node.type is NodeType.PHENOTYPE else 0.0
    )


@lru_cache(maxsize=4)
def routing_graph(store: GraphStore) -> Any:
    """Simple undirected weighted graph: one (cheapest) edge per node pair. Cached per store."""
    best: dict[tuple[str, str], _Hop] = {}
    for _, _, edge in store.graph.edges(data="edge"):
        if edge.source_id == edge.target_id:
            continue
        pair = (min(edge.source_id, edge.target_id), max(edge.source_id, edge.target_id))
        hop = _Hop(edge, edge_cost(edge))
        current = best.get(pair)
        if current is None or (hop.cost, edge.id) < (current.cost, current.edge.id):
            best[pair] = hop
    graph = nx.Graph()
    graph.add_nodes_from(sorted(node.id for node in store.nodes()))
    for (left, right), hop in sorted(best.items()):
        penalty = _hub_penalty(store.get_node(left)) + _hub_penalty(store.get_node(right))
        graph.add_edge(left, right, weight=hop.cost + penalty, hop=hop)
    return nx.freeze(graph)


def _iter_node_paths(graph: Any, source: str, target: str) -> Iterator[list[str]]:
    try:
        yield from nx.shortest_simple_paths(graph, source, target, weight="weight")
    except nx.NetworkXNoPath:
        return


def _build_path(store: GraphStore, graph: Any, node_ids: list[str]) -> PathOut:
    hops: list[_Hop] = [graph[a][b]["hop"] for a, b in zip(node_ids, node_ids[1:], strict=False)]
    nodes = tuple(store.get_node(i) for i in node_ids)
    edges = tuple(hop.edge for hop in hops)
    return PathOut(
        nodes=tuple(n for n in nodes if n is not None),
        edges=edges,
        cost=round(sum(hop.cost for hop in hops), 4),
        has_inferred=any(e.evidence_type is EvidenceType.INFERRED for e in edges),
        has_contradiction=any(e.contradicted_by for e in edges),
    )


def find_paths(store: GraphStore, source: str, target: str, k: int = 3) -> tuple[PathOut, ...]:
    """Up to ``k`` (<= MAX_PATHS) best simple paths of at most MAX_PATH_EDGES edges."""
    graph = routing_graph(store)
    if source not in graph or target not in graph or source == target:
        return ()
    wanted = max(1, min(k, MAX_PATHS))
    found: list[PathOut] = []
    for node_ids in islice(_iter_node_paths(graph, source, target), MAX_CANDIDATE_PATHS):
        if len(node_ids) - 1 > MAX_PATH_EDGES:
            continue
        found.append(_build_path(store, graph, node_ids))
        if len(found) >= wanted:
            break
    return tuple(found)
