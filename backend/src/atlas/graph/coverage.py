"""Honest-gap coverage reports (docs/EVIDENCE_MODEL.md, "Honest gaps").

Template-based, no LLM. Inputs: the node's own edges, the manifest sources, and the coverage
seeds the snapshot build recorded (``gap_disease``, ``no_dedicated_org_found``,
``seed_diseases_without_studies``, ``seed_diseases_without_patient_group``,
``go_genes_without_whitelisted_terms``).

Result rules:

* disease: ``supported`` when at least one study or partner organisation (patient group /
  funder) is linked by a non-inferred edge with confidence >= ``SUPPORTED_CONFIDENCE``;
  ``weak_routes_only`` when such links exist but all are weak; otherwise
  ``no_supported_route`` (publications and genes alone are listed as weak leads / context).
* any other node: ``supported`` when it has a strong edge, ``weak_routes_only`` when it only
  has weak ones, ``no_supported_route`` when it has none.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from atlas.graph.queries import other_end
from atlas.graph.store import GraphStore, thaw
from atlas.models.evidence import Edge, EvidenceType, Node, NodeType, Relation
from atlas.models.responses import CoverageReport, CoverageStatus, SourceSearched, WeakLead

SUPPORTED_CONFIDENCE = 0.4
NOT_SEARCHED = (
    "omim (license not obtained)",
    "orphanet (not ingested in this snapshot)",
    "nih_reporter (only the slice's text searches, fiscal years 2019-2026)",
    "pubmed (only team-curated citations, no systematic search)",
)
PARTNER_TYPES = frozenset({NodeType.PATIENT_GROUP, NodeType.FUNDER})
GENE_RELATIONS = frozenset({Relation.CAUSED_BY, Relation.RISK_FACTOR_FOR})
STATUS_BY_RESULT: Mapping[str, CoverageStatus] = {
    "supported": "supported",
    "weak_routes_only": "weak",
    "no_supported_route": "gap",
}


def is_strong(edge: Edge) -> bool:
    return (
        edge.evidence_type is not EvidenceType.INFERRED and edge.confidence >= SUPPORTED_CONFIDENCE
    )


def _seed_entry(coverage: Mapping[str, Any], node_id: str) -> dict[str, Any] | None:
    for entry in thaw(coverage.get("no_dedicated_org_found") or ()):
        if isinstance(entry, dict) and entry.get("disease_id") == node_id:
            return entry
    return None


def _seed_ids(coverage: Mapping[str, Any], key: str) -> frozenset[str]:
    return frozenset(str(item) for item in coverage.get(key) or ())


def sources_searched(store: GraphStore, edges: Iterable[Edge]) -> tuple[SourceSearched, ...]:
    per_source: dict[str, int] = {}
    for edge in edges:
        per_source[edge.provenance.source] = per_source.get(edge.provenance.source, 0) + 1
    rows: list[SourceSearched] = []
    seen: set[str] = set()
    for source in thaw(store.manifest.get("sources") or ()):
        name = str(source.get("source") or "")
        if not name or name in seen:
            continue
        seen.add(name)
        version = source.get("source_version")
        rows.append(
            SourceSearched(
                source=name,
                source_version=str(version) if version else None,
                records_found=per_source.get(name, 0),
            )
        )
    for name in sorted(set(per_source) - seen):
        rows.append(SourceSearched(source=name, records_found=per_source[name]))
    return tuple(rows)


def _reporter_searched(store: GraphStore) -> bool:
    return any(
        isinstance(source, Mapping) and source.get("source") == "reporter"
        for source in store.manifest.get("sources") or ()
    )


def _community_labels(store: GraphStore, seed: Mapping[str, Any]) -> list[str]:
    """Seed slugs (``international-gaucher-alliance``) -> org labels when in the graph."""
    labels = []
    for slug in seed.get("closest_communities") or ():
        node = store.get_node(f"org:{slug}")
        labels.append(node.label if node is not None else str(slug))
    return labels


def _labels(store: GraphStore, ids: Iterable[str]) -> list[str]:
    nodes = (store.get_node(i) for i in sorted(set(ids)))
    return [n.label for n in nodes if n is not None]


def _linked(
    store: GraphStore, node_id: str, edges: Iterable[Edge], types: frozenset[NodeType]
) -> list[Edge]:
    found = []
    for edge in edges:
        other = store.get_node(other_end(edge, node_id))
        if other is not None and other.type in types:
            found.append(edge)
    return found


def _disease_report(
    store: GraphStore, node: Node, edges: tuple[Edge, ...]
) -> tuple[str, list[str], list[WeakLead], list[str]]:
    seeds = store.coverage
    studies = _linked(store, node.id, edges, frozenset({NodeType.STUDY, NodeType.ASSET}))
    partners = _linked(store, node.id, edges, PARTNER_TYPES)
    genes = _linked(store, node.id, edges, frozenset({NodeType.GENE}))
    pubs = _linked(store, node.id, edges, frozenset({NodeType.PUBLICATION}))
    gene_labels = _labels(store, (other_end(e, node.id) for e in genes))
    missing: list[str] = []
    questions: list[str] = []
    seed = _seed_entry(seeds, node.id)
    if not studies or node.id in _seed_ids(seeds, "seed_diseases_without_studies"):
        missing.append(f"No ClinicalTrials.gov study or reusable asset is linked to {node.label}")
        if gene_labels:
            questions.append(
                f"Would a study on another {', '.join(gene_labels)}-linked disease accept "
                f"{node.label} patients, samples or natural-history data?"
            )
    if not partners:
        closest = ", ".join(_community_labels(store, seed)) if seed else ""
        searched = ", ".join(seed.get("searched") or ()) if seed else ""
        text = f"No patient organisation or funder is linked to {node.label}"
        if searched:
            text += f" (searched: {searched})"
        missing.append(text)
        questions.append(
            f"Is there a registry or family network for {node.label}?"
            + (f" Closest communities: {closest}." if closest else "")
        )
    investigators = [e for e in edges if e.relation is Relation.INVESTIGATES]
    if not investigators and _reporter_searched(store):
        missing.append(f"No NIH RePORTER project or investigator is linked to {node.label}")
    if not genes:
        missing.append(f"No causal or risk gene is annotated for {node.label}")
        questions.append(f"Which gene or variant explains {node.label}?")
    leads = [
        WeakLead(
            path_edge_ids=(edge.id,),
            min_confidence=edge.confidence,
            why_weak="single publication, not a study or a partner",
        )
        for edge in sorted(pubs, key=lambda e: e.id)
    ]
    route_edges = studies + partners
    if any(is_strong(e) for e in route_edges) and node.id != seeds.get("gap_disease"):
        result = "supported"
    elif route_edges:
        result = "weak_routes_only"
        leads.extend(
            WeakLead(path_edge_ids=(e.id,), min_confidence=e.confidence, why_weak="low confidence")
            for e in sorted(route_edges, key=lambda e: e.id)
        )
    else:
        result = "no_supported_route"
    return result, missing, leads, questions


def _other_report(
    store: GraphStore, node: Node, edges: tuple[Edge, ...]
) -> tuple[str, list[str], list[WeakLead], list[str]]:
    missing: list[str] = []
    questions: list[str] = []
    if node.id in _seed_ids(store.coverage, "go_genes_without_whitelisted_terms"):
        missing.append(f"No whitelisted GO mechanism term for {node.label}")
        questions.append(f"Which lysosomal or autophagy process does {node.label} act through?")
    if not edges:
        missing.append(f"{node.label} is unmapped: no edges in this snapshot")
        questions.append(f"Which source would connect {node.label} to a disease?")
        return "no_supported_route", missing, [], questions
    if any(is_strong(e) for e in edges):
        return "supported", missing, [], questions
    leads = [
        WeakLead(path_edge_ids=(e.id,), min_confidence=e.confidence, why_weak="low confidence")
        for e in edges
    ]
    return "weak_routes_only", missing, leads, questions


def coverage_report(store: GraphStore, node: Node) -> CoverageReport:
    """Coverage report for one node (deterministic)."""
    edges = store.edges_for(node.id)
    if node.type is NodeType.DISEASE:
        result, missing, leads, questions = _disease_report(store, node, edges)
    else:
        result, missing, leads, questions = _other_report(store, node, edges)
    seed = _seed_entry(store.coverage, node.id)
    not_searched = list(NOT_SEARCHED)
    for item in (seed.get("not_searched") or ()) if seed else ():
        if item not in not_searched:
            not_searched.append(str(item))
    return CoverageReport(
        query=node.id,
        result=result,  # type: ignore[arg-type]
        searched=sources_searched(store, edges),
        not_searched=tuple(not_searched),
        missing_evidence=tuple(missing),
        weak_leads=tuple(leads),
        next_questions=tuple(questions),
    )


def coverage_status(store: GraphStore, node: Node) -> CoverageStatus:
    return STATUS_BY_RESULT[coverage_report(store, node).result]
