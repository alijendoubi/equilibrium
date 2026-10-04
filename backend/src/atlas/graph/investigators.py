"""Shared-investigator bridges (issue #38): people whose funded work spans two communities.

An investigator is a bridge when their observed ``investigates`` edges (NIH RePORTER) reach
seed genes/diseases in at least two different communities of ``COMMUNITIES``, for example
Gaucher disease / GBA1 and Parkinson disease. This is the brief's "network overlap": a person
who could carry a protocol, samples or a question from one community to the other.

``COMMUNITIES`` is a fixed grouping of the RePORTER targets for this slice (not the analytics
clusters): the Gaucher core, Parkinson disease, and the lysosomal neighbours (PSAP, SCARB2 and
saposin C deficiency).
"""

from __future__ import annotations

from collections.abc import Mapping

from atlas.graph.store import GraphStore
from atlas.models.evidence import Edge, NodeType, Relation
from atlas.models.responses import SharedInvestigator

COMMUNITIES: Mapping[str, str] = {
    "MONDO:0018150": "Gaucher disease",
    "HGNC:4177": "Gaucher disease",
    "MONDO:0008199": "Parkinson disease",
    "HGNC:9498": "lysosomal neighbours",
    "HGNC:1665": "lysosomal neighbours",
    "MONDO:0012517": "lysosomal neighbours",
}
GENE_RELATIONS = frozenset({Relation.CAUSED_BY, Relation.RISK_FACTOR_FOR})
MAX_SHARED = 10


def _project_count(edges: tuple[Edge, ...]) -> int:
    numbers = {p for e in edges for p in e.qualifiers.get("projects", "").split(",") if p}
    return len(numbers)


def bridges(store: GraphStore) -> tuple[SharedInvestigator, ...]:
    """Every investigator linked to targets in >= 2 communities, strongest first."""
    found: list[tuple[tuple[int, int, int, str], SharedInvestigator]] = []
    for node in store.nodes(NodeType.INVESTIGATOR):
        edges = tuple(
            e
            for e in store.edges_for(node.id, "out", (Relation.INVESTIGATES,))
            if e.target_id in COMMUNITIES
        )
        communities = sorted({COMMUNITIES[e.target_id] for e in edges})
        if len(communities) < 2:
            continue
        targets = sorted({e.target_id for e in edges})
        labels = [n.label for n in (store.get_node(t) for t in targets) if n is not None]
        projects = _project_count(edges)
        org = node.attributes.get("organization", "")
        why = (
            f"NIH-funded work on {', '.join(labels)} ({' + '.join(communities)}; "
            f"{projects} RePORTER project{'s' if projects != 1 else ''}"
            f"{', ' + org if org else ''})"
        )
        item = SharedInvestigator(
            node=node,
            communities=tuple(communities),
            target_ids=tuple(targets),
            why=why,
            edge_ids=tuple(sorted(e.id for e in edges)),
        )
        found.append(((-len(communities), -len(targets), -projects, node.id), item))
    return tuple(item for _, item in sorted(found, key=lambda pair: pair[0]))


def shared_investigators(
    store: GraphStore, disease_id: str, limit: int = MAX_SHARED
) -> tuple[SharedInvestigator, ...]:
    """Bridges that touch the disease itself or one of its causal / risk genes."""
    relevant = {disease_id} | {
        e.target_id if e.source_id == disease_id else e.source_id
        for e in store.edges_for(disease_id, relations=GENE_RELATIONS)
    }
    return tuple(b for b in bridges(store) if relevant & set(b.target_ids))[:limit]
