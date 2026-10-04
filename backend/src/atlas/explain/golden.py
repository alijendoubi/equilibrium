"""The golden demo path (PROJECT_PLAN 3.2): neuronopathic Gaucher -> GBA1 -> lysosome ->
late-onset Parkinson disease -> ASPro-PD (NCT05778617, ambroxol) -> Cure Parkinson's.
"""

import logging
from collections.abc import Iterable, Mapping

from atlas.graph.store import GraphStore
from atlas.models.evidence import Edge, Node, Relation

logger = logging.getLogger(__name__)

GBA1 = "HGNC:4177"
GAUCHER_TYPE_2 = "MONDO:0009266"
GAUCHER_TYPE_3 = "MONDO:0009267"
LATE_ONSET_PD = "MONDO:0008199"
ASPRO_PD = "clinicaltrials:NCT05778617"
CURE_PARKINSONS = "org:cure-parkinsons"
GLUCOSYLCERAMIDE_CATABOLISM = "GO:0006680"
LYSOSOME_ORGANIZATION = "GO:0007040"

# (source, relation, target) hops in path order.
GOLDEN_HOPS: tuple[tuple[str, Relation, str], ...] = (
    (GAUCHER_TYPE_2, Relation.CAUSED_BY, GBA1),
    (GAUCHER_TYPE_3, Relation.CAUSED_BY, GBA1),
    (GBA1, Relation.PARTICIPATES_IN, GLUCOSYLCERAMIDE_CATABOLISM),
    (GBA1, Relation.PARTICIPATES_IN, LYSOSOME_ORGANIZATION),
    (GBA1, Relation.RISK_FACTOR_FOR, LATE_ONSET_PD),
    (ASPRO_PD, Relation.STUDIES_CONDITION, LATE_ONSET_PD),
    (CURE_PARKINSONS, Relation.FUNDS, ASPRO_PD),
)


def best_edge(store: GraphStore, source: str, relation: Relation, target: str) -> Edge | None:
    """Highest-confidence edge for one hop (ties broken by edge id, so it is deterministic)."""
    candidates = [e for e in store.edges_for(source, "out", [relation]) if e.target_id == target]
    if not candidates:
        return None
    return min(candidates, key=lambda e: (-e.confidence, e.id))


def golden_edges(store: GraphStore) -> tuple[Edge, ...]:
    """The golden chain's edges in path order; missing hops are skipped with a warning."""
    found: list[Edge] = []
    for source, relation, target in GOLDEN_HOPS:
        edge = best_edge(store, source, relation, target)
        if edge is None:
            logger.warning("golden hop missing: %s %s %s", source, relation.value, target)
            continue
        found.append(edge)
    return tuple(found)


def nodes_for(store: GraphStore, edges: Iterable[Edge]) -> Mapping[str, Node]:
    """Endpoint nodes of ``edges`` keyed by id."""
    result: dict[str, Node] = {}
    for edge in edges:
        for node_id in (edge.source_id, edge.target_id):
            node = store.get_node(node_id)
            if node is not None:
                result[node_id] = node
    return result
