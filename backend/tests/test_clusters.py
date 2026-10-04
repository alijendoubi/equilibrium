"""Disease similarity and clustering on a small synthetic store (issue #20)."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from atlas.api.main import create_app
from atlas.config import Settings
from atlas.graph import similarity as sim
from atlas.graph.clusters import EDGE_THRESHOLD, build_cluster_index
from atlas.graph.store import GraphStore
from atlas.models.evidence import Edge, EvidenceType, Node, NodeType, Provenance, Relation

RETRIEVED = datetime(2026, 10, 4, tzinfo=UTC)


def _edge(source: str, relation: Relation, target: str) -> Edge:
    return Edge(
        source_id=source,
        target_id=target,
        relation=relation,
        provenance=Provenance(
            source="test",
            source_record_id=f"{source}>{target}",
            url="https://example.org/record",  # type: ignore[arg-type]
            retrieved_at=RETRIEVED,
        ),
        confidence=0.9,
        evidence_type=EvidenceType.CURATED,
    )


def _node(node_id: str, node_type: NodeType, label: str, **attrs: str) -> Node:
    return Node(id=node_id, type=node_type, label=label, attributes=attrs)


DISEASES = ("D:A", "D:B", "D:C", "D:D", "D:iso")
NODES = (
    *(_node(d, NodeType.DISEASE, f"Disease {d[2:]}") for d in DISEASES),
    _node("G:1", NodeType.GENE, "GENE1"),
    _node("G:2", NodeType.GENE, "GENE2"),
    _node("GO:1", NodeType.MECHANISM, "pathway one"),
    _node("GO:2", NodeType.MECHANISM, "pathway two"),
    _node("HP:r1", NodeType.PHENOTYPE, "Rare one", ic="8.0"),
    _node("HP:r2", NodeType.PHENOTYPE, "Rare two", ic="6.0"),
    _node("HP:r3", NodeType.PHENOTYPE, "Rare three", ic="7.0"),
    _node("HP:r4", NodeType.PHENOTYPE, "Rare four", ic="5.0"),
    _node("HP:c", NodeType.PHENOTYPE, "Broad term", ic="0.5"),
    _node("HP:bad", NodeType.PHENOTYPE, "No usable IC", ic="n/a"),
)
EDGES = (
    _edge("D:A", Relation.CAUSED_BY, "G:1"),
    _edge("D:B", Relation.CAUSED_BY, "G:1"),
    _edge("D:C", Relation.CAUSED_BY, "G:2"),
    _edge("D:D", Relation.CAUSED_BY, "G:2"),
    _edge("G:1", Relation.RISK_FACTOR_FOR, "D:D"),
    _edge("G:1", Relation.PARTICIPATES_IN, "GO:1"),
    _edge("G:2", Relation.PARTICIPATES_IN, "GO:2"),
    *(_edge(d, Relation.HAS_PHENOTYPE, "HP:c") for d in DISEASES),
    *(_edge(d, Relation.HAS_PHENOTYPE, "HP:bad") for d in DISEASES),
    _edge("D:A", Relation.HAS_PHENOTYPE, "HP:r1"),
    _edge("D:B", Relation.HAS_PHENOTYPE, "HP:r1"),
    _edge("D:B", Relation.HAS_PHENOTYPE, "HP:r2"),
    _edge("D:C", Relation.HAS_PHENOTYPE, "HP:r3"),
    _edge("D:D", Relation.HAS_PHENOTYPE, "HP:r3"),
    _edge("D:C", Relation.HAS_PHENOTYPE, "HP:r4"),
    _edge("D:D", Relation.HAS_PHENOTYPE, "HP:r4"),
)


@pytest.fixture
def store() -> GraphStore:
    return GraphStore(NODES, EDGES)


def test_phenotype_ic_skips_unusable_values(store: GraphStore) -> None:
    ic = sim.phenotype_ic(store)
    assert ic["HP:r1"] == 8.0
    assert "HP:bad" not in ic


def test_profiles_drop_broad_terms_and_collect_genes(store: GraphStore) -> None:
    profiles, _ = sim.build_profiles(store)
    assert "HP:c" not in profiles["D:A"].phenotypes  # IC 0.5 < floor
    assert profiles["D:D"].genes == {"G:1": {"risk_factor_for"}, "G:2": {"caused_by"}}
    assert profiles["D:D"].mechanisms == {"GO:1", "GO:2"}
    assert profiles["D:iso"].phenotypes == frozenset()


def test_score_pair_components(store: GraphStore) -> None:
    profiles, ic = sim.build_profiles(store)
    pair = sim.score_pair(profiles["D:B"], profiles["D:A"], ic)
    assert (pair.a, pair.b) == ("D:A", "D:B")
    assert pair.phenotype == pytest.approx(8.0 / 14.0, abs=1e-4)
    assert pair.gene == 1.0 and pair.mechanism == 1.0
    expected = sim.W_PHENOTYPE * 8.0 / 14.0 + sim.W_GENE + sim.W_MECHANISM
    assert pair.score == pytest.approx(expected, abs=1e-4)
    assert pair.shared_phenotypes == ("HP:r1",)
    assert sim.score_pair(profiles["D:A"], profiles["D:B"], ic) == pair


def test_broad_shared_terms_alone_score_zero(store: GraphStore) -> None:
    profiles, ic = sim.build_profiles(store)
    assert sim.score_pair(profiles["D:A"], profiles["D:iso"], ic).score == 0.0
    pairs = sim.all_pairs(profiles, ic)
    assert all("D:iso" not in (p.a, p.b) for p in pairs)
    assert [p.score for p in pairs] == sorted((p.score for p in pairs), reverse=True)


def test_pair_reasons_name_gene_mechanism_and_phenotypes(store: GraphStore) -> None:
    profiles, ic = sim.build_profiles(store)
    reasons = sim.pair_reasons(
        store, sim.score_pair(profiles["D:A"], profiles["D:D"], ic), profiles
    )
    assert reasons[0] == "shares gene GENE1 (caused_by vs risk_factor_for)"
    assert "pathway one" in reasons[1]
    pheno = sim.pair_reasons(store, sim.score_pair(profiles["D:C"], profiles["D:D"], ic), profiles)
    assert any("Rare three" in r and "2 shared" in r for r in pheno)


def test_link_text() -> None:
    assert sim.link_text({"caused_by"}, {"caused_by"}) == "caused_by"
    assert sim.link_text({"caused_by"}, {"risk_factor_for"}) == "caused_by vs risk_factor_for"


def test_clusters_partition_and_ids(store: GraphStore) -> None:
    index = build_cluster_index(store)
    members = [m for s in index.summaries for m in s.member_ids]
    assert sorted(members) == sorted(DISEASES)
    assert [s.id for s in index.summaries] == [f"C{i}" for i in range(1, len(index.summaries) + 1)]
    sizes = [s.size for s in index.summaries]
    assert sizes == sorted(sizes, reverse=True)
    assert index.cluster_of("D:A") == index.cluster_of("D:B")
    assert index.cluster_of("D:C") == index.cluster_of("D:D")
    assert index.cluster_of("D:A") != index.cluster_of("D:C")
    iso = index.get(index.cluster_of("D:iso") or "")
    assert iso is not None and iso.size == 1 and iso.edges == () and iso.label == "Disease iso"
    assert index.cluster_of("G:1") is None
    assert index.get("C99") is None


def test_cluster_detail_features_bridges_counterexamples(store: GraphStore) -> None:
    index = build_cluster_index(store)
    detail = index.get(index.cluster_of("D:A") or "")
    assert detail is not None
    assert detail.label == "GENE1 · pathway one"
    assert [f.node.id for f in detail.features.genes] == ["G:1"]
    assert detail.features.phenotypes[0].node.id == "HP:r1"
    assert detail.features.phenotypes[0].ic == 8.0
    within = [e for e in detail.edges if e.kind == "within"]
    assert [(e.source_id, e.target_id) for e in within] == [("D:A", "D:B")]
    assert all(e.score >= EDGE_THRESHOLD for e in within)
    assert detail.bridges and {b.other_id for b in detail.bridges} == {"D:D"}
    assert {e.kind for e in detail.edges} == {"within", "bridge"}
    (first, *_) = detail.counterexamples
    assert first.gene.id == "G:1" and first.other_id == "D:D"
    assert "grouped apart" in first.note
    external = [n for n in detail.nodes if not n.is_member]
    assert [n.node.id for n in external] == ["D:D"]
    assert external[0].cluster_id == index.cluster_of("D:D")
    member = next(n for n in detail.nodes if n.node.id == "D:A")
    assert member.degree >= 1


def test_clusters_are_deterministic(store: GraphStore) -> None:
    first = build_cluster_index(store)
    second = build_cluster_index(GraphStore(tuple(reversed(NODES)), tuple(reversed(EDGES))))
    assert first.summaries == second.summaries
    assert dict(first.details) == dict(second.details)


def test_cluster_routes_need_a_snapshot(tmp_path: Path) -> None:
    app = create_app(Settings(SNAPSHOT_PATH=tmp_path / "missing.json"))  # type: ignore[call-arg]
    with TestClient(app) as client:
        assert app.state.cluster_index is None
        assert client.get("/api/v1/clusters").status_code == 503
        assert client.get("/api/v1/clusters/C1").status_code == 503


def test_cluster_index_built_lazily_when_missing(store: GraphStore) -> None:
    app = create_app(Settings())
    with TestClient(app) as client:
        app.state.store = store
        app.state.cluster_index = None
        body = client.get("/api/v1/clusters").json()
        assert sorted(m for c in body["clusters"] for m in c["member_ids"]) == sorted(DISEASES)
        assert app.state.cluster_index is not None
