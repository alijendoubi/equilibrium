"""Disease clusters, bridges and counterexamples (issue #20).

Computed once at startup from the store (``build_cluster_index``) and kept on ``app.state``.
Pure and deterministic: same snapshot in, same clusters out.

1. Pairwise similarity from ``atlas.graph.similarity`` (phenotype + gene + GO mechanism).
2. Pairs scoring at least ``EDGE_THRESHOLD`` become weighted edges of a disease graph;
   ``networkx`` Louvain (``seed=SEED``) splits it into communities. Diseases with no edge above
   the threshold form their own one-member cluster.
3. Ids ``C1..Cn`` by size (largest first), then smallest member id. Each cluster is labelled by
   its most shared gene and its most specific shared GO mechanism.
4. Bridges: the strongest pairs (score >= ``BRIDGE_FLOOR``) from a member to another cluster.
   Counterexamples: a member and a non-member linked to the same gene, which is evidence that
   the gene alone does not decide the grouping. Only what the snapshot shows is reported.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

import networkx as nx

from atlas.graph import similarity as sim
from atlas.graph.store import GraphStore
from atlas.models.clusters import (
    Bridge,
    ClusterDetail,
    ClusterEdge,
    ClusterEdgeKind,
    ClusterFeatures,
    ClusterMethod,
    ClusterNode,
    ClusterSummary,
    Counterexample,
    SharedFeature,
)
from atlas.models.evidence import Node

SEED = 42
EDGE_THRESHOLD = 0.15
BRIDGE_FLOOR = 0.05
MAX_BRIDGES = 6
MAX_COUNTEREXAMPLES = 8
TOP_FEATURES = 5
MIN_SHARED = 2

METHOD = ClusterMethod(
    description=(
        "Disease similarity = 0.5 x IC-weighted phenotype Jaccard (HPO terms with IC >= "
        f"{sim.PHENOTYPE_IC_FLOOR}) + 0.3 x shared causal/risk gene (Jaccard) + 0.2 x shared GO "
        f"mechanism of those genes (Jaccard). Pairs >= {EDGE_THRESHOLD} are linked and grouped "
        f"with Louvain community detection (seed {SEED}). Small curated graph: memberships are "
        "explained, not claimed as discoveries."
    ),
    weights={"phenotype": sim.W_PHENOTYPE, "gene": sim.W_GENE, "mechanism": sim.W_MECHANISM},
    phenotype_ic_floor=sim.PHENOTYPE_IC_FLOOR,
    edge_threshold=EDGE_THRESHOLD,
    seed=SEED,
)


@dataclass(frozen=True)
class _Context:
    store: GraphStore
    profiles: Mapping[str, sim.DiseaseProfile]
    ic: Mapping[str, float]
    pairs: Mapping[tuple[str, str], sim.PairScore]
    cluster_of: Mapping[str, str]
    degree: Mapping[str, int]
    mechanism_frequency: Mapping[str, int]


@dataclass(frozen=True)
class ClusterIndex:
    """All clusters of one snapshot; read-only."""

    summaries: tuple[ClusterSummary, ...]
    details: Mapping[str, ClusterDetail]
    by_disease: Mapping[str, str]

    def get(self, cluster_id: str) -> ClusterDetail | None:
        return self.details.get(cluster_id)

    def cluster_of(self, disease_id: str) -> str | None:
        return self.by_disease.get(disease_id)


def _key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def _communities(diseases: Iterable[str], pairs: Iterable[sim.PairScore]) -> list[list[str]]:
    graph = nx.Graph()
    graph.add_nodes_from(sorted(diseases))
    for pair in sorted(pairs, key=lambda p: (p.a, p.b)):
        if pair.score >= EDGE_THRESHOLD:
            graph.add_edge(pair.a, pair.b, weight=pair.score)
    found = nx.community.louvain_communities(graph, weight="weight", seed=SEED)
    groups = [sorted(group) for group in found]
    return sorted(groups, key=lambda g: (-len(g), g[0]))


def _context(store: GraphStore) -> tuple[_Context, list[list[str]]]:
    profiles, ic = sim.build_profiles(store)
    pair_list = sim.all_pairs(profiles, ic)
    groups = _communities(profiles, pair_list)
    cluster_of = {d: f"C{i}" for i, group in enumerate(groups, start=1) for d in group}
    degree: Counter[str] = Counter()
    for pair in pair_list:
        if pair.score >= EDGE_THRESHOLD:
            degree.update((pair.a, pair.b))
    mech_freq = Counter(m for p in profiles.values() for m in p.mechanisms)
    ctx = _Context(
        store=store,
        profiles=profiles,
        ic=ic,
        pairs=MappingProxyType({(p.a, p.b): p for p in pair_list}),
        cluster_of=MappingProxyType(cluster_of),
        degree=MappingProxyType(dict(degree)),
        mechanism_frequency=MappingProxyType(dict(mech_freq)),
    )
    return ctx, groups


def _shared(
    members: list[str], items_of: Mapping[str, Iterable[str]]
) -> dict[str, tuple[str, ...]]:
    holders: dict[str, list[str]] = {}
    for member in members:
        for item in sorted(set(items_of[member])):
            holders.setdefault(item, []).append(member)
    return {item: tuple(ids) for item, ids in holders.items() if len(ids) >= MIN_SHARED}


def _feature(ctx: _Context, node_id: str, member_ids: tuple[str, ...]) -> SharedFeature | None:
    node = ctx.store.get_node(node_id)
    if node is None:
        return None
    return SharedFeature(node=node, member_ids=member_ids, ic=ctx.ic.get(node_id))


def _features(ctx: _Context, members: list[str]) -> ClusterFeatures:
    prof = ctx.profiles
    genes = _shared(members, {m: prof[m].genes for m in members})
    mechs = _shared(members, {m: prof[m].mechanisms for m in members})
    phenos = _shared(members, {m: prof[m].phenotypes for m in members})
    gene_ids = sorted(genes, key=lambda g: (-len(genes[g]), g))
    mech_ids = sorted(mechs, key=lambda m: (-len(mechs[m]), ctx.mechanism_frequency.get(m, 0), m))
    pheno_ids = sorted(phenos, key=lambda p: (-ctx.ic[p], -len(phenos[p]), p))

    def build(ids: list[str], holders: dict[str, tuple[str, ...]]) -> tuple[SharedFeature, ...]:
        found = (_feature(ctx, i, holders[i]) for i in ids[:TOP_FEATURES])
        return tuple(f for f in found if f is not None)

    return ClusterFeatures(
        genes=build(gene_ids, genes),
        mechanisms=build(mech_ids, mechs),
        phenotypes=build(pheno_ids, phenos),
    )


def _label(ctx: _Context, members: list[str], features: ClusterFeatures) -> str:
    parts = [f.node.label for f in (features.genes[:1] + features.mechanisms[:1])]
    if parts:
        return " · ".join(parts)
    if features.phenotypes:
        return f"shared phenotype: {features.phenotypes[0].node.label}"
    node = ctx.store.get_node(members[0])
    return node.label if node is not None else members[0]


def _edge(ctx: _Context, pair: sim.PairScore, kind: ClusterEdgeKind) -> ClusterEdge:
    return ClusterEdge(
        source_id=pair.a,
        target_id=pair.b,
        kind=kind,
        score=pair.score,
        phenotype_score=pair.phenotype,
        gene_score=pair.gene,
        mechanism_score=pair.mechanism,
        reasons=sim.pair_reasons(ctx.store, pair, ctx.profiles),
    )


def _bridges(ctx: _Context, cluster_id: str) -> list[sim.PairScore]:
    crossing = [
        pair
        for pair in ctx.pairs.values()
        if pair.score >= BRIDGE_FLOOR
        and (ctx.cluster_of[pair.a] == cluster_id) != (ctx.cluster_of[pair.b] == cluster_id)
    ]
    return sorted(crossing, key=lambda p: (-p.score, p.a, p.b))[:MAX_BRIDGES]


def _counterexample(ctx: _Context, gene: Node, member: str, other: str) -> Counterexample:
    pair = ctx.pairs.get(_key(member, other))
    score = pair.score if pair is not None else 0.0
    phenotype = pair.phenotype if pair is not None else 0.0
    how = sim.link_text(ctx.profiles[member].genes[gene.id], ctx.profiles[other].genes[gene.id])
    return Counterexample(
        gene=gene,
        member_id=member,
        other_id=other,
        other_cluster_id=ctx.cluster_of[other],
        score=score,
        note=(
            f"Both linked to {gene.label} ({how}) but grouped apart: "
            f"similarity {score:.2f}, phenotype similarity {phenotype:.2f}."
        ),
    )


def _counterexamples(ctx: _Context, cluster_id: str, members: list[str]) -> list[Counterexample]:
    outside = [d for d in ctx.profiles if ctx.cluster_of[d] != cluster_id]
    found = [
        _counterexample(ctx, gene, member, other)
        for member in members
        for gene in (ctx.store.get_node(g) for g in ctx.profiles[member].genes)
        if gene is not None
        for other in outside
        if gene.id in ctx.profiles[other].genes
    ]
    found.sort(key=lambda c: (c.gene.label, -c.score, c.member_id, c.other_id))
    return found[:MAX_COUNTEREXAMPLES]


def _detail(ctx: _Context, cluster_id: str, members: list[str]) -> ClusterDetail:
    features = _features(ctx, members)
    member_set = set(members)
    within = [
        _edge(ctx, pair, "within")
        for (a, b), pair in sorted(ctx.pairs.items())
        if a in member_set and b in member_set and pair.score >= EDGE_THRESHOLD
    ]
    bridge_pairs = _bridges(ctx, cluster_id)
    bridges = []
    for pair in bridge_pairs:
        member, other = (pair.a, pair.b) if pair.a in member_set else (pair.b, pair.a)
        bridges.append(
            Bridge(
                member_id=member,
                other_id=other,
                other_cluster_id=ctx.cluster_of[other],
                score=pair.score,
                reasons=sim.pair_reasons(ctx.store, pair, ctx.profiles),
            )
        )
    counterexamples = _counterexamples(ctx, cluster_id, members)
    external = sorted({b.other_id for b in bridges} | {c.other_id for c in counterexamples})
    nodes = []
    for node_id in members + external:
        node = ctx.store.get_node(node_id)
        if node is not None:
            nodes.append(
                ClusterNode(
                    node=node,
                    cluster_id=ctx.cluster_of[node_id],
                    is_member=node_id in member_set,
                    degree=ctx.degree.get(node_id, 0),
                )
            )
    return ClusterDetail(
        id=cluster_id,
        label=_label(ctx, members, features),
        size=len(members),
        member_ids=tuple(members),
        nodes=tuple(nodes),
        features=features,
        edges=tuple(within + [_edge(ctx, pair, "bridge") for pair in bridge_pairs]),
        bridges=tuple(bridges),
        counterexamples=tuple(counterexamples),
    )


def build_cluster_index(store: GraphStore) -> ClusterIndex:
    """Cluster every disease in the store (deterministic for a given snapshot)."""
    ctx, groups = _context(store)
    details = {}
    for index, members in enumerate(groups, start=1):
        cluster_id = f"C{index}"
        details[cluster_id] = _detail(ctx, cluster_id, members)
    summaries = tuple(
        ClusterSummary(id=d.id, label=d.label, size=d.size, member_ids=d.member_ids)
        for d in details.values()
    )
    return ClusterIndex(
        summaries=summaries,
        details=MappingProxyType(details),
        by_disease=ctx.cluster_of,
    )
