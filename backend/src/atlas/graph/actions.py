"""Action view for one disease (issue #37): partners, reusable assets, next experiment.

Template-based and deterministic, no LLM.

* Partners: patient groups / funders whose ``represents`` or ``funds`` edge lands within
  ``MAX_PARTNER_HOPS`` hops of the disease, walking only through genes, mechanisms, diseases
  (``caused_by``, ``risk_factor_for``, ``participates_in``) and the disease's own studies.
* Assets: studies, publications and assets linked to the disease (tier 0), to diseases that
  share one of its genes (tier 1) or a GO mechanism of its genes (tier 2). Team-curated assets
  rank first, then tier, then confidence; capped at ``MAX_ASSETS``.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from atlas.graph.coverage import coverage_report
from atlas.graph.queries import other_end
from atlas.graph.store import GraphStore
from atlas.models.evidence import Edge, Node, NodeType, Relation
from atlas.models.responses import ActionsResponse, NextExperiment, Partner, ReusableAsset

MAX_PARTNER_HOPS = 3
MAX_ASSETS = 25
BRIDGE_RELATIONS = frozenset(
    {Relation.CAUSED_BY, Relation.RISK_FACTOR_FOR, Relation.PARTICIPATES_IN}
)
GENE_RELATIONS = frozenset({Relation.CAUSED_BY, Relation.RISK_FACTOR_FOR})
PARTNER_RELATIONS = frozenset({Relation.REPRESENTS, Relation.FUNDS})
PARTNER_TYPES = frozenset({NodeType.PATIENT_GROUP, NodeType.FUNDER})
BRIDGE_TYPES = frozenset({NodeType.DISEASE, NodeType.GENE, NodeType.MECHANISM})
LEAF_TYPES = frozenset({NodeType.DISEASE, NodeType.STUDY})
ASSET_TYPES = frozenset({NodeType.STUDY, NodeType.PUBLICATION, NodeType.ASSET})
OPEN_STATUSES = frozenset({"RECRUITING", "ACTIVE_NOT_RECRUITING", "ENROLLING_BY_INVITATION"})
STOPPED_STATUSES = frozenset({"TERMINATED", "WITHDRAWN", "SUSPENDED"})
REVIEW_CHECKLIST = (
    "Open each cited edge's source record and confirm it says what the edge claims.",
    "Re-check every node marked 'needs human check' (team-curated) before sharing.",
    "Confirm study status, eligibility and contacts on ClinicalTrials.gov before outreach.",
    "Confirm each organisation actually covers this disease subtype.",
    "Treat the next experiment as a hypothesis to discuss, not as treatment guidance.",
)


@dataclass(frozen=True)
class _Reach:
    node: Node
    edges: tuple[Edge, ...]


def _walk(store: GraphStore, start: Node, max_depth: int, with_studies: bool) -> list[_Reach]:
    """BFS through genes and mechanisms (other diseases and studies are leaves); first path wins."""
    reached: dict[str, _Reach] = {start.id: _Reach(start, ())}
    queue = deque([start.id])
    while queue:
        current = reached[queue.popleft()]
        is_leaf = current.node.id != start.id and current.node.type in LEAF_TYPES
        if len(current.edges) >= max_depth or is_leaf:
            continue
        for edge in store.edges_for(current.node.id):
            nxt = store.get_node(other_end(edge, current.node.id))
            if nxt is None or nxt.id in reached:
                continue
            bridge = edge.relation in BRIDGE_RELATIONS and nxt.type in BRIDGE_TYPES
            study = (
                with_studies
                and current.node.id == start.id
                and edge.relation is Relation.STUDIES_CONDITION
                and nxt.type is NodeType.STUDY
            )
            if bridge or study:
                reached[nxt.id] = _Reach(nxt, (*current.edges, edge))
                queue.append(nxt.id)
    return list(reached.values())


def _via(store: GraphStore, edges: tuple[Edge, ...], disease_id: str) -> str:
    ids: list[str] = []
    for edge in edges:
        for node_id in (edge.source_id, edge.target_id):
            node = store.get_node(node_id)
            if node and node.type in (NodeType.GENE, NodeType.MECHANISM) and node_id not in ids:
                ids.append(node_id)
    labels = [n.label for n in (store.get_node(i) for i in ids) if n is not None]
    return ", ".join(labels) if labels else disease_id


def find_partners(store: GraphStore, disease: Node) -> tuple[Partner, ...]:
    best: dict[str, tuple[tuple[int, float, tuple[str, ...]], Partner]] = {}
    for reach in _walk(store, disease, MAX_PARTNER_HOPS - 1, with_studies=True):
        for edge in store.edges_for(reach.node.id, relations=PARTNER_RELATIONS):
            org = store.get_node(other_end(edge, reach.node.id))
            if org is None or org.type not in PARTNER_TYPES:
                continue
            path = (*reach.edges, edge)
            verb = "Represents" if edge.relation is Relation.REPRESENTS else "Funds"
            why = f"{verb} {reach.node.label}"
            if reach.node.type is NodeType.STUDY:
                why += f", a study of {disease.label}"
            elif reach.node.id != disease.id:
                why += f", linked to {disease.label} through {_via(store, path, disease.id)}"
            key = (len(path), -min(e.confidence for e in path), tuple(e.id for e in path))
            partner = Partner(node=org, why=why, edge_ids=tuple(e.id for e in path))
            if org.id not in best or key < best[org.id][0]:
                best[org.id] = (key, partner)
    ranked = sorted(best.items(), key=lambda item: (item[1][0][:2], item[0]))
    return tuple(partner for _, (_, partner) in ranked)


def _related_diseases(store: GraphStore, disease: Node) -> list[tuple[int, _Reach]]:
    """(tier, reach) for the disease, gene-sharing diseases and mechanism-sharing diseases."""
    related: list[tuple[int, _Reach]] = []
    for reach in _walk(store, disease, 4, with_studies=False):
        if reach.node.type is not NodeType.DISEASE:
            continue
        uses_mechanism = any(e.relation is Relation.PARTICIPATES_IN for e in reach.edges)
        tier = 0 if not reach.edges else (2 if uses_mechanism else 1)
        related.append((tier, reach))
    return related


def _first_sentence(text: str) -> str:
    head = text.split(". ")[0].strip()
    return head if head.endswith(".") else head + "."


def reusable_text(node: Node) -> str:
    attrs = node.attributes
    notes = attrs.get("curated_notes", "")
    for sentence in notes.split(". "):
        if sentence.strip().lower().startswith("reusable"):
            return _first_sentence(sentence)
    if node.type is NodeType.STUDY:
        parts = [f"{attrs.get('study_type', 'clinical').lower()} study"]
        if attrs.get("phase"):
            parts.append(f"phase {attrs['phase']}")
        if attrs.get("status"):
            parts.append(attrs["status"].lower().replace("_", " "))
        if attrs.get("enrollment"):
            parts.append(f"{attrs['enrollment']} participants")
        text = ", ".join(parts).capitalize()
        if attrs.get("interventions"):
            text += f"; interventions: {attrs['interventions']}"
        return text + ". Protocol, safety data and outcome measures may transfer."
    source = notes or attrs.get("description", "")
    return _first_sentence(source) if source else f"{node.label}: published evidence to reuse."


def differs_text(store: GraphStore, node: Node, disease: Node, tier: int, reach: _Reach) -> str:
    attrs = node.attributes
    if tier == 0:
        text = f"Already linked to {disease.label}; check scope and eligibility before reuse."
    else:
        target = attrs.get("conditions") or reach.node.label
        via = _via(store, reach.edges, disease.id)
        shared = "shared gene" if tier == 1 else "shared pathway only"
        text = (
            f"Studies {target}, not {disease.label} ({shared}: {via}); eligibility, dosing and "
            f"endpoints would need re-checking for {disease.label}."
        )
    status = attrs.get("status", "")
    if status in STOPPED_STATUSES:
        reason = attrs.get("why_stopped")
        text += f" Status {status.lower()}" + (f": {reason}." if reason else ".")
    return text


def find_assets(store: GraphStore, disease: Node) -> tuple[ReusableAsset, ...]:
    best: dict[str, tuple[tuple[object, ...], ReusableAsset]] = {}
    for tier, reach in _related_diseases(store, disease):
        for edge in store.edges_for(reach.node.id):
            node = store.get_node(other_end(edge, reach.node.id))
            if node is None or node.type not in ASSET_TYPES:
                continue
            path = (*reach.edges, edge)
            key: tuple[object, ...] = (
                tier,
                "asset_slug" not in node.attributes,
                -edge.confidence,
                len(path),
                node.id,
                tuple(e.id for e in path),
            )
            if node.id in best and best[node.id][0] <= key:
                continue
            asset = ReusableAsset(
                node=node,
                reusable=reusable_text(node),
                differs=differs_text(store, node, disease, tier, reach),
                edge_ids=tuple(e.id for e in path),
            )
            best[node.id] = (key, asset)
    ranked = sorted(best.values(), key=lambda item: item[0])
    return tuple(asset for _, asset in ranked[:MAX_ASSETS])


def _experiment_rank(asset: ReusableAsset) -> tuple[bool, bool, int]:
    """Open studies first, then team-curated ones, then the largest enrollment."""
    attrs = asset.node.attributes
    enrollment = attrs.get("enrollment", "")
    size = int(enrollment) if enrollment.isdigit() else 0
    return (attrs.get("status") not in OPEN_STATUSES, "asset_slug" not in attrs, -size)


def next_experiment(
    store: GraphStore, disease: Node, assets: tuple[ReusableAsset, ...]
) -> NextExperiment | None:
    cross = [a for a in assets if len(a.edge_ids) > 1 and a.node.type is NodeType.STUDY]
    open_first = sorted(cross, key=_experiment_rank)  # stable: keeps asset rank on ties
    if open_first:
        asset = open_first[0]
        edges = tuple(e for e in (store.get_edge(i) for i in asset.edge_ids) if e is not None)
        via = _via(store, edges, disease.id)
        text = (
            f"Hypothesis: {disease.label} is linked through {via} to the population of "
            f"{asset.node.label}. "
            f"Check whether that study's protocol and biomarker readouts could run in a small "
            f"{disease.label} cohort, starting with a feasibility review of eligibility, dosing "
            f"and endpoints."
        )
        return NextExperiment(text=text, is_hypothesis=True, edge_ids=asset.edge_ids)
    genes = store.edges_for(disease.id, relations=GENE_RELATIONS)
    if genes:
        gene = store.get_node(other_end(genes[0], disease.id))
        label = gene.label if gene else other_end(genes[0], disease.id)
        text = (
            f"Hypothesis: a functional assay of {label} variants seen in {disease.label} "
            f"patients would show which mechanism (and which studies) they share with other "
            f"{label}-linked diseases."
        )
        return NextExperiment(text=text, is_hypothesis=True, edge_ids=(genes[0].id,))
    return None


def build_actions(store: GraphStore, disease: Node) -> ActionsResponse:
    partners = find_partners(store, disease)
    assets = find_assets(store, disease)
    coverage = coverage_report(store, disease) if not partners or not assets else None
    return ActionsResponse(
        disease_id=disease.id,
        partners=partners,
        assets=assets,
        next_experiment=next_experiment(store, disease, assets),
        review_checklist=REVIEW_CHECKLIST,
        coverage=coverage,
    )
