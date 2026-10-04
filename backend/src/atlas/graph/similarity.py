"""Disease-disease similarity (issue #20): phenotype, shared gene, shared GO mechanism.

Pure and deterministic; computed from the graph store only.

* **Phenotype**: IC-weighted Jaccard over each disease's ``has_phenotype`` set,
  ``sum(IC(shared)) / sum(IC(union))``. IC comes from the phenotype node's ``attributes["ic"]``
  (string). Terms below ``PHENOTYPE_IC_FLOOR`` are dropped first so broad terms such as
  "Abnormality of the nervous system" cannot make two diseases look alike.
* **Gene**: Jaccard over the genes linked to each disease by ``caused_by`` (disease -> gene)
  or ``risk_factor_for`` (gene -> disease).
* **Mechanism**: Jaccard over the GO terms those genes ``participates_in``.

Combined score: ``W_PHENOTYPE * phenotype + W_GENE * gene + W_MECHANISM * mechanism``
(weights sum to 1). Every pair keeps its components, the shared items and readable reasons.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from itertools import combinations
from types import MappingProxyType

from atlas.graph.store import GraphStore
from atlas.models.evidence import NodeType, Relation

PHENOTYPE_IC_FLOOR = 2.5
W_PHENOTYPE = 0.5
W_GENE = 0.3
W_MECHANISM = 0.2
TOP_SHARED_PHENOTYPES = 5
REASON_ITEMS = 3

_GENE_RELATIONS = (Relation.CAUSED_BY, Relation.RISK_FACTOR_FOR)


@dataclass(frozen=True)
class DiseaseProfile:
    """What a disease is made of for similarity purposes."""

    disease_id: str
    phenotypes: frozenset[str]
    genes: Mapping[str, frozenset[str]]  # gene id -> relation values linking it
    mechanisms: frozenset[str]


@dataclass(frozen=True)
class PairScore:
    """Similarity of two diseases (``a < b``) with its parts and the evidence behind it."""

    a: str
    b: str
    score: float
    phenotype: float
    gene: float
    mechanism: float
    shared_genes: tuple[str, ...]
    shared_mechanisms: tuple[str, ...]
    shared_phenotypes: tuple[str, ...]  # top by IC, then id
    n_shared_phenotypes: int


def _round(value: float) -> float:
    return round(value, 4)


def phenotype_ic(store: GraphStore) -> Mapping[str, float]:
    """IC of every phenotype node with a usable ``ic`` attribute."""
    found: dict[str, float] = {}
    for node in store.nodes(NodeType.PHENOTYPE):
        raw = node.attributes.get("ic")
        try:
            value = float(raw) if raw is not None else math.nan
        except ValueError:
            continue
        if math.isfinite(value) and value > 0:
            found[node.id] = value
    return MappingProxyType(found)


def _profile(store: GraphStore, disease_id: str, ic: Mapping[str, float]) -> DiseaseProfile:
    phenotypes = frozenset(
        edge.target_id
        for edge in store.edges_for(disease_id, "out", (Relation.HAS_PHENOTYPE,))
        if ic.get(edge.target_id, 0.0) >= PHENOTYPE_IC_FLOOR
    )
    genes: dict[str, set[str]] = {}
    for edge in store.edges_for(disease_id, "both", _GENE_RELATIONS):
        other = edge.target_id if edge.source_id == disease_id else edge.source_id
        node = store.get_node(other)
        if node is not None and node.type is NodeType.GENE:
            genes.setdefault(other, set()).add(edge.relation.value)
    mechanisms = frozenset(
        edge.target_id
        for gene_id in genes
        for edge in store.edges_for(gene_id, "out", (Relation.PARTICIPATES_IN,))
    )
    return DiseaseProfile(
        disease_id=disease_id,
        phenotypes=phenotypes,
        genes=MappingProxyType({g: frozenset(r) for g, r in sorted(genes.items())}),
        mechanisms=mechanisms,
    )


def build_profiles(store: GraphStore) -> tuple[Mapping[str, DiseaseProfile], Mapping[str, float]]:
    """Profiles of every disease (sorted by id) and the phenotype IC table used for them."""
    ic = phenotype_ic(store)
    profiles = {node.id: _profile(store, node.id, ic) for node in store.nodes(NodeType.DISEASE)}
    return MappingProxyType(profiles), ic


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _weighted_jaccard(
    left: frozenset[str], right: frozenset[str], ic: Mapping[str, float]
) -> float:
    union = sum(ic[term] for term in left | right)
    return sum(ic[term] for term in left & right) / union if union else 0.0


def score_pair(left: DiseaseProfile, right: DiseaseProfile, ic: Mapping[str, float]) -> PairScore:
    """Similarity of two disease profiles (order-independent)."""
    a, b = sorted((left, right), key=lambda p: p.disease_id)
    shared_ph = a.phenotypes & b.phenotypes
    phenotype = _weighted_jaccard(a.phenotypes, b.phenotypes, ic)
    gene = _jaccard(frozenset(a.genes), frozenset(b.genes))
    mechanism = _jaccard(a.mechanisms, b.mechanisms)
    top = sorted(shared_ph, key=lambda term: (-ic[term], term))[:TOP_SHARED_PHENOTYPES]
    return PairScore(
        a=a.disease_id,
        b=b.disease_id,
        score=_round(W_PHENOTYPE * phenotype + W_GENE * gene + W_MECHANISM * mechanism),
        phenotype=_round(phenotype),
        gene=_round(gene),
        mechanism=_round(mechanism),
        shared_genes=tuple(sorted(set(a.genes) & set(b.genes))),
        shared_mechanisms=tuple(sorted(a.mechanisms & b.mechanisms)),
        shared_phenotypes=tuple(top),
        n_shared_phenotypes=len(shared_ph),
    )


def all_pairs(
    profiles: Mapping[str, DiseaseProfile], ic: Mapping[str, float]
) -> tuple[PairScore, ...]:
    """Every disease pair with a positive score, best first (ties by ids)."""
    pairs = (score_pair(profiles[x], profiles[y], ic) for x, y in combinations(sorted(profiles), 2))
    kept = [pair for pair in pairs if pair.score > 0]
    return tuple(sorted(kept, key=lambda p: (-p.score, p.a, p.b)))


def _labels(store: GraphStore, ids: Iterable[str]) -> list[str]:
    labels = []
    for node_id in ids:
        node = store.get_node(node_id)
        labels.append(node.label if node is not None else node_id)
    return labels


def link_text(left: Iterable[str], right: Iterable[str]) -> str:
    """How two diseases link to one gene: ``caused_by`` or ``caused_by vs risk_factor_for``."""
    rel_a, rel_b = "/".join(sorted(left)), "/".join(sorted(right))
    return rel_a if rel_a == rel_b else f"{rel_a} vs {rel_b}"


def pair_reasons(
    store: GraphStore, pair: PairScore, profiles: Mapping[str, DiseaseProfile]
) -> tuple[str, ...]:
    """Plain-language reasons for a pair score, strongest signal first."""
    reasons: list[str] = []
    for gene_id in pair.shared_genes:
        how = link_text(profiles[pair.a].genes[gene_id], profiles[pair.b].genes[gene_id])
        (label,) = _labels(store, (gene_id,))
        reasons.append(f"shares gene {label} ({how})")
    if pair.shared_mechanisms:
        names = _labels(store, pair.shared_mechanisms[:REASON_ITEMS])
        more = len(pair.shared_mechanisms) - len(names)
        suffix = f" and {more} more" if more > 0 else ""
        reasons.append(f"shares GO mechanism via its genes: {', '.join(names)}{suffix}")
    if pair.n_shared_phenotypes:
        names = _labels(store, pair.shared_phenotypes[:REASON_ITEMS])
        reasons.append(
            f"phenotype similarity {pair.phenotype:.2f} over {pair.n_shared_phenotypes} shared "
            f"informative terms (e.g. {', '.join(names)})"
        )
    return tuple(reasons)
