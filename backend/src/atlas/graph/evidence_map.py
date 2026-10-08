"""The evidence map (GET /api/v1/graph): a readable, capped subgraph for drawing.

The snapshot has ~830 nodes and ~1500 edges, more than half of them symptoms, so a full render
is unreadable. This module picks what to draw and says what it left out:

* With a ``center``: nodes up to ``depth`` hops away (traversal ignores edge direction and
  only follows edges that pass the relation / confidence filters). Phenotypes are collapsed by
  default (ask for them with ``types``). Each type keeps at most ``TYPE_CAP`` nodes (fewer
  investigators and studies, see ``TYPE_CAPS``), best first.
* Without a center: an overview of the slice: diseases, genes, variants, mechanisms, patient
  groups, assets, publications, studies that are curated assets (they carry ``asset_slug``,
  ASPro-PD among them) and funders linked to any of those. No phenotypes, no investigators.
* Every hidden node is counted per type in ``truncated.by_type`` ("+41 phenotypes").
* Edges are the induced subgraph among drawn nodes; contradictions are kept first when the edge
  cap bites, and an edge that contradicts a drawn edge pulls its endpoints onto the map.

Pure functions over a ``GraphStore``; results are deterministically ordered.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from atlas.graph.store import GraphStore
from atlas.models.evidence import Edge, Node, NodeType, Relation
from atlas.models.graph_map import GraphMapResponse, MapLegend, MapNode, MapTruncation

MAX_NODES = 150
MAX_EDGES = 400
MAX_DEPTH = 2
TYPE_CAP = 30
# Tighter caps for the bulk types, so people and trials do not crowd out the disease story.
TYPE_CAPS = {NodeType.INVESTIGATOR: 12, NodeType.STUDY: 24}
DEFAULT_COLLAPSED = frozenset({NodeType.PHENOTYPE})
OVERVIEW_TYPES = frozenset(
    {
        NodeType.DISEASE,
        NodeType.GENE,
        NodeType.VARIANT,
        NodeType.MECHANISM,
        NodeType.PATIENT_GROUP,
        NodeType.ASSET,
        NodeType.PUBLICATION,
    }
)
CURATED_ASSET_ATTRIBUTE = "asset_slug"
# Drawing priority when a cap bites: the disease story first, people and symptoms last.
TYPE_ORDER: tuple[NodeType, ...] = (
    NodeType.DISEASE,
    NodeType.GENE,
    NodeType.VARIANT,
    NodeType.MECHANISM,
    NodeType.PATIENT_GROUP,
    NodeType.FUNDER,
    NodeType.ASSET,
    NodeType.STUDY,
    NodeType.PUBLICATION,
    NodeType.INVESTIGATOR,
    NodeType.PHENOTYPE,
)
TYPE_RANK = {node_type: rank for rank, node_type in enumerate(TYPE_ORDER)}


@dataclass(frozen=True)
class MapQuery:
    """Filters of one map request (already validated by the route)."""

    center: str | None = None
    depth: int = 1
    types: frozenset[NodeType] | None = None
    relations: frozenset[Relation] | None = None
    min_confidence: float = 0.0
    limit: int = MAX_NODES

    def edge_ok(self, edge: Edge) -> bool:
        if edge.confidence < self.min_confidence:
            return False
        return self.relations is None or edge.relation in self.relations

    def type_visible(self, node_type: NodeType) -> bool:
        if self.types is not None:
            return node_type in self.types
        return node_type not in DEFAULT_COLLAPSED


@dataclass(frozen=True)
class _Candidate:
    node: Node
    distance: int | None
    best_confidence: float


def is_contradiction(edge: Edge) -> bool:
    return edge.relation is Relation.CONTRADICTS or bool(edge.contradicted_by)


def _other_end(edge: Edge, node_id: str) -> str:
    return edge.target_id if edge.source_id == node_id else edge.source_id


def _ic(node: Node) -> float:
    try:
        return float(node.attributes.get("ic", "0"))
    except ValueError:
        return 0.0


def _candidate_key(candidate: _Candidate) -> tuple[int, int, float, float, str, str]:
    node = candidate.node
    return (
        candidate.distance if candidate.distance is not None else 0,
        TYPE_RANK[node.type],
        -candidate.best_confidence,
        -_ic(node),
        node.label.lower(),
        node.id,
    )


# ---- candidate pools ---------------------------------------------------------------------------


def _neighbourhood(
    store: GraphStore, center: Node, query: MapQuery
) -> tuple[list[_Candidate], dict[str, NodeType]]:
    """Visible nodes within ``depth`` hops (best edge confidence kept) and hidden-type counts."""
    distance: dict[str, int] = {center.id: 0}
    best: dict[str, float] = {center.id: 1.0}
    hidden: dict[str, NodeType] = {}
    frontier = [center.id]
    for hop in range(1, query.depth + 1):
        reached: list[str] = []
        for node_id in frontier:
            for edge in store.edges_for(node_id):
                if not query.edge_ok(edge):
                    continue
                other_id = _other_end(edge, node_id)
                if other_id in distance:
                    if distance[other_id] == hop:
                        best[other_id] = max(best[other_id], edge.confidence)
                    continue
                other = store.get_node(other_id)
                if other is None:  # pragma: no cover - the store rejects dangling edges
                    continue
                if not query.type_visible(other.type):
                    hidden[other_id] = other.type
                    continue
                distance[other_id] = hop
                best[other_id] = edge.confidence
                reached.append(other_id)
        frontier = sorted(reached)
    candidates = []
    for node_id, hops in distance.items():
        node = store.get_node(node_id)
        if node is not None and node_id != center.id:
            candidates.append(_Candidate(node, hops, best[node_id]))
    return candidates, hidden


def _in_overview(store: GraphStore, node: Node, base: frozenset[str]) -> bool:
    if node.type in OVERVIEW_TYPES:
        return True
    if node.type is NodeType.STUDY:
        return CURATED_ASSET_ATTRIBUTE in node.attributes
    if node.type is NodeType.FUNDER:
        return any(_other_end(edge, node.id) in base for edge in store.edges_for(node.id))
    return False


def _overview(store: GraphStore, query: MapQuery) -> tuple[list[_Candidate], dict[str, NodeType]]:
    """The slice at a glance: the disease story without symptoms, people or bulk trials."""
    base = frozenset(
        node.id
        for node in store.nodes()
        if node.type in OVERVIEW_TYPES
        or (node.type is NodeType.STUDY and CURATED_ASSET_ATTRIBUTE in node.attributes)
    )
    candidates: list[_Candidate] = []
    hidden: dict[str, NodeType] = {}
    for node in store.nodes():
        if _in_overview(store, node, base) and (query.types is None or node.type in query.types):
            candidates.append(_Candidate(node, None, 1.0))
        else:
            hidden[node.id] = node.type
    return candidates, hidden


# ---- selection ---------------------------------------------------------------------------------


def _select(
    candidates: Iterable[_Candidate], room: int, per_type_caps: bool = True
) -> list[_Candidate]:
    """Best first, at most ``room`` overall and (optionally) the per-type caps."""
    chosen: list[_Candidate] = []
    per_type: Counter[NodeType] = Counter()
    for candidate in sorted(candidates, key=_candidate_key):
        node_type = candidate.node.type
        cap = TYPE_CAPS.get(node_type, TYPE_CAP) if per_type_caps else room
        if per_type[node_type] >= cap or len(chosen) >= room:
            continue
        per_type[node_type] += 1
        chosen.append(candidate)
    return chosen


def _induced_edges(store: GraphStore, ids: set[str], query: MapQuery) -> list[Edge]:
    found: dict[str, Edge] = {}
    for node_id in sorted(ids):
        for edge in store.edges_for(node_id):
            if edge.source_id in ids and edge.target_id in ids and query.edge_ok(edge):
                found[edge.id] = edge
    return list(found.values())


def _pull_in_contradictions(
    store: GraphStore, chosen: list[_Candidate], query: MapQuery, room: int
) -> list[_Candidate]:
    """Endpoints of edges that contradict a drawn edge: contradictions are surfaced, not hidden."""
    ids = {candidate.node.id for candidate in chosen}
    extra: list[_Candidate] = []
    for edge in sorted(_induced_edges(store, ids, query), key=lambda e: e.id):
        for contradicting_id in edge.contradicted_by:
            other = store.get_edge(contradicting_id)
            if other is None or not query.edge_ok(other):
                continue
            for node_id in (other.source_id, other.target_id):
                node = store.get_node(node_id)
                if node is None or node_id in ids or not query.type_visible(node.type):
                    continue
                if len(chosen) + len(extra) >= room:
                    return extra
                ids.add(node_id)
                distance = query.depth + 1 if query.center is not None else None
                extra.append(_Candidate(node, distance, other.confidence))
    return extra


def _edge_priority(edge: Edge) -> tuple[bool, float, str]:
    return (not is_contradiction(edge), -edge.confidence, edge.id)


def _edge_order(edge: Edge) -> tuple[str, str, str, str]:
    return (edge.source_id, edge.relation.value, edge.target_id, edge.id)


def build_map(
    store: GraphStore,
    query: MapQuery,
    cluster_of: Callable[[str], str | None] = lambda _id: None,
) -> GraphMapResponse:
    """The map for ``query``. Raises KeyError when the center is unknown."""
    limit = max(1, min(query.limit, MAX_NODES))
    center = store.get_node(query.center) if query.center is not None else None
    if query.center is not None and center is None:
        raise KeyError(query.center)

    if center is not None:
        pool, hidden = _neighbourhood(store, center, query)
        chosen = _select(pool, limit - 1)
        chosen = [_Candidate(center, 0, 1.0), *chosen]
    else:
        pool, hidden = _overview(store, query)
        chosen = _select(pool, limit, per_type_caps=False)
    chosen = chosen + _pull_in_contradictions(store, chosen, query, limit)
    ids = {candidate.node.id for candidate in chosen}
    left_out = {c.node.id: c.node.type for c in pool} | hidden
    hidden_by_type = Counter(t.value for node_id, t in left_out.items() if node_id not in ids)
    induced = _induced_edges(store, ids, query)
    kept = sorted(sorted(induced, key=_edge_priority)[:MAX_EDGES], key=_edge_order)
    kept_ids = {edge.id for edge in kept}
    touching = {
        edge.id for node_id in ids for edge in store.edges_for(node_id) if query.edge_ok(edge)
    }
    degree: Counter[str] = Counter()
    for edge in kept:
        degree[edge.source_id] += 1
        degree[edge.target_id] += 1
    contradicted = {cid for edge in kept for cid in edge.contradicted_by}
    contradiction_ids = tuple(
        edge.id for edge in kept if is_contradiction(edge) or edge.id in contradicted
    )

    def order(candidate: _Candidate) -> tuple[int, int, str, str]:
        node = candidate.node
        hops = candidate.distance if candidate.distance is not None else 0
        return (hops, TYPE_RANK[node.type], node.label.lower(), node.id)

    nodes = tuple(
        MapNode(
            node=c.node,
            degree=degree[c.node.id],
            total_degree=len(store.edges_for(c.node.id)),
            cluster_id=cluster_of(c.node.id) if c.node.type is NodeType.DISEASE else None,
            distance=c.distance,
        )
        for c in sorted(chosen, key=order)
    )
    by_type = {key: count for key, count in sorted(hidden_by_type.items()) if count > 0}
    return GraphMapResponse(
        center=center.id if center is not None else None,
        depth=query.depth if center is not None else 0,
        nodes=nodes,
        edges=tuple(kept),
        contradiction_edge_ids=tuple(sorted(set(contradiction_ids) & kept_ids)),
        truncated=MapTruncation(
            by_type=by_type,
            nodes_hidden=sum(by_type.values()),
            edges_hidden=len(touching - kept_ids),
        ),
        legend=MapLegend(
            node_types=dict(sorted(Counter(n.node.type.value for n in nodes).items())),
            relations=dict(sorted(Counter(e.relation.value for e in kept).items())),
            evidence_types=dict(sorted(Counter(e.evidence_type.value for e in kept).items())),
        ),
    )
