"""Graph queries on small synthetic stores: path ranking, coverage rules, actions edge cases."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from atlas.api.main import build_search_index, create_app
from atlas.config import Settings
from atlas.graph import queries
from atlas.graph.actions import build_actions, next_experiment, reusable_text
from atlas.graph.coverage import coverage_report
from atlas.graph.store import GraphStore
from atlas.models.evidence import Edge, EvidenceType, Node, NodeType, Provenance, Relation
from atlas.reconcile.embeddings import embedding_key

RETRIEVED = datetime(2026, 10, 4, tzinfo=UTC)


def _edge(
    source: str,
    relation: Relation,
    target: str,
    confidence: float = 0.9,
    evidence: EvidenceType = EvidenceType.CURATED,
    record: str = "",
    contradicted_by: tuple[str, ...] = (),
    supporting: tuple[str, ...] = (),
    provenance_source: str = "test",
) -> Edge:
    return Edge(
        source_id=source,
        target_id=target,
        relation=relation,
        provenance=Provenance(
            source=provenance_source,
            source_record_id=record or f"{source}>{target}",
            url="https://example.org/record",  # type: ignore[arg-type]
            retrieved_at=RETRIEVED,
            supporting_edge_ids=supporting,
        ),
        confidence=confidence,
        evidence_type=evidence,
        contradicted_by=contradicted_by,
    )


def _node(node_id: str, node_type: NodeType, label: str, **attrs: str) -> Node:
    return Node(id=node_id, type=node_type, label=label, attributes=attrs)


NODES = (
    _node("D:1", NodeType.DISEASE, "Disease one"),
    _node("D:2", NodeType.DISEASE, "Disease two"),
    _node("D:3", NodeType.DISEASE, "Disease three"),
    _node("D:4", NodeType.DISEASE, "Disease four"),
    _node("D:iso", NodeType.DISEASE, "Isolated disease"),
    _node("G:1", NodeType.GENE, "GENE1"),
    _node("G:2", NodeType.GENE, "GENE2"),
    _node("M:1", NodeType.MECHANISM, "shared pathway"),
    _node("HP:1", NodeType.PHENOTYPE, "Seizure"),
    _node(
        "S:1",
        NodeType.STUDY,
        "Trial in disease two",
        status="TERMINATED",
        why_stopped="sponsor decision",
        phase="2",
        enrollment="40",
        interventions="drug X",
        study_type="INTERVENTIONAL",
        conditions="Disease two",
    ),
    _node("S:2", NodeType.STUDY, "Trial in disease three", status="RECRUITING"),
    _node("PUB:1", NodeType.PUBLICATION, "Case report", curated_notes="One patient. Improved."),
    _node("org:pg", NodeType.PATIENT_GROUP, "Patient group"),
    _node("org:weak", NodeType.PATIENT_GROUP, "Weak group"),
    _node("org:f", NodeType.FUNDER, "Funder"),
    _node("org:closest", NodeType.PATIENT_GROUP, "Closest community"),
)
BASE = _edge("D:1", Relation.CAUSED_BY, "G:1")
DISPUTE = _edge("D:2", Relation.HAS_PHENOTYPE, "HP:1", contradicted_by=(BASE.id,))
INFERRED = _edge(
    "D:3",
    Relation.SHARES_MECHANISM_WITH,
    "D:4",
    confidence=0.5,
    evidence=EvidenceType.INFERRED,
    supporting=(BASE.id,),
)
EDGES = (
    BASE,
    _edge("D:1", Relation.CAUSED_BY, "G:1", confidence=0.5, record="weaker parallel"),
    _edge("G:1", Relation.RISK_FACTOR_FOR, "D:2"),
    _edge("G:1", Relation.PARTICIPATES_IN, "M:1"),
    _edge("G:2", Relation.PARTICIPATES_IN, "M:1"),
    _edge("D:3", Relation.CAUSED_BY, "G:2"),
    _edge("D:1", Relation.HAS_PHENOTYPE, "HP:1"),
    DISPUTE,
    _edge("D:4", Relation.HAS_PHENOTYPE, "HP:1"),
    INFERRED,
    _edge("S:1", Relation.STUDIES_CONDITION, "D:2", confidence=0.7),
    _edge("S:2", Relation.STUDIES_CONDITION, "D:3", confidence=0.7),
    _edge("S:2", Relation.STUDIES_CONDITION, "D:1", confidence=0.7),
    _edge("PUB:1", Relation.MENTIONS, "D:4", confidence=0.8),
    _edge("org:pg", Relation.REPRESENTS, "D:2", confidence=0.6),
    _edge("org:weak", Relation.REPRESENTS, "D:4", confidence=0.2),
    _edge("org:f", Relation.FUNDS, "S:2", confidence=0.8),
)
COVERAGE = {
    "gap_disease": "D:iso",
    "no_dedicated_org_found": [
        {
            "disease_id": "D:iso",
            "closest_communities": ["closest", "missing-slug"],
            "searched": ["web search"],
            "not_searched": ["registry X"],
        }
    ],
    "go_genes_without_whitelisted_terms": ["G:2"],
}
MANIFEST = {
    "sources": [
        {"source": "test", "source_version": "v1"},
        {"source": "test"},
        {"source": "empty", "source_version": None},
    ]
}


@pytest.fixture(scope="module")
def store() -> GraphStore:
    return GraphStore(NODES, EDGES, manifest=MANIFEST, coverage=COVERAGE)


@pytest.fixture
def api(store: GraphStore, tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(Settings(SNAPSHOT_PATH=tmp_path / "missing.json"))  # type: ignore[call-arg]
    with TestClient(app) as test_client:
        app.state.store = store
        yield test_client


# ---- paths -----------------------------------------------------------------------------------


def test_paths_prefer_gene_route_over_phenotype_hub(store: GraphStore) -> None:
    found = queries.find_paths(store, "D:1", "D:2", k=5)
    assert [n.id for n in found[0].nodes] == ["D:1", "G:1", "D:2"]
    assert found[0].edges[0].id == BASE.id  # parallel edges collapse to the cheapest
    hub = [p for p in found if any(n.type is NodeType.PHENOTYPE for n in p.nodes)]
    assert hub and found.index(hub[0]) > 0
    assert hub[0].has_contradiction is True


def test_paths_inferred_penalty_and_limits(store: GraphStore) -> None:
    found = queries.find_paths(store, "D:3", "D:4", k=1)
    assert len(found) == 1
    path = found[0]
    assert path.has_inferred is True
    assert path.cost == pytest.approx(queries.edge_cost(INFERRED), abs=1e-3)
    assert queries.edge_cost(INFERRED) > 1.0
    assert queries.find_paths(store, "D:1", "D:1") == ()
    assert queries.find_paths(store, "D:1", "D:iso") == ()


def test_api_no_path_returns_coverage(api: TestClient) -> None:
    body = api.get("/api/v1/paths", params={"from": "D:1", "to": "D:iso"}).json()
    assert body["paths"] == []
    assert body["coverage"]["query"] == "D:iso"
    assert body["coverage"]["result"] == "no_supported_route"
    reverse = api.get("/api/v1/paths", params={"from": "D:iso", "to": "D:1"}).json()
    assert reverse["coverage"]["query"] == "D:iso"


# ---- neighbors / edges -----------------------------------------------------------------------


def test_neighbors_and_edge_detail(store: GraphStore, api: TestClient) -> None:
    result = queries.neighbors(store, "D:4", evidence=frozenset({EvidenceType.INFERRED}))
    assert [e.id for e in result.edges] == [INFERRED.id]
    assert [n.id for n in result.nodes] == ["D:3"]
    body = api.get(f"/api/v1/edges/{DISPUTE.id}").json()
    assert [e["id"] for e in body["contradictions"]] == [BASE.id]
    inferred = api.get(f"/api/v1/edges/{INFERRED.id}").json()
    assert [e["id"] for e in inferred["supporting_edges"]] == [BASE.id]


# ---- coverage --------------------------------------------------------------------------------


def test_coverage_rules(store: GraphStore) -> None:
    def node(i: str) -> Node:
        found = store.get_node(i)
        assert found is not None
        return found

    assert coverage_report(store, node("D:2")).result == "supported"
    weak = coverage_report(store, node("D:4"))
    assert weak.result == "weak_routes_only"
    assert {lead.why_weak for lead in weak.weak_leads} >= {"low confidence"}
    gap = coverage_report(store, node("D:iso"))
    assert gap.result == "no_supported_route"
    assert "registry X" in gap.not_searched
    assert any("Closest community, missing-slug" in q for q in gap.next_questions)
    assert any("gene" in m for m in gap.missing_evidence)
    gene = coverage_report(store, node("G:2"))
    assert gene.result == "supported"
    assert any("GO" in m for m in gene.missing_evidence)
    searched = {row.source: row for row in gap.searched}
    assert list(searched) == ["test", "empty"]
    assert searched["empty"].source_version is None
    assert "source_version" not in searched["empty"].model_dump()


def test_coverage_for_unlinked_and_weak_non_disease() -> None:
    lonely = _node("G:9", NodeType.GENE, "LONELY")
    weakly = _node("G:8", NodeType.GENE, "WEAK")
    other = _node("D:9", NodeType.DISEASE, "Other")
    edge = _edge("D:9", Relation.CAUSED_BY, "G:8", confidence=0.1)
    small = GraphStore((lonely, weakly, other), (edge,))
    assert coverage_report(small, lonely).result == "no_supported_route"
    assert coverage_report(small, weakly).result == "weak_routes_only"
    searched = coverage_report(small, weakly).searched
    assert [(row.source, row.records_found) for row in searched] == [("test", 1)]


# ---- actions ---------------------------------------------------------------------------------


def test_actions_partners_assets_and_templates(store: GraphStore) -> None:
    disease = store.get_node("D:1")
    assert disease is not None
    actions = build_actions(store, disease)
    partners = {p.node.id: p for p in actions.partners}
    assert "GENE1" in partners["org:pg"].why
    assert "a study of Disease one" in partners["org:f"].why
    assets = {a.node.id: a for a in actions.assets}
    assert "Already linked" in assets["S:2"].differs
    assert "shared gene" in assets["S:1"].differs
    assert "terminated: sponsor decision" in assets["S:1"].differs
    assert "phase 2" in assets["S:1"].reusable
    assert actions.coverage is None
    assert actions.next_experiment is not None
    assert actions.next_experiment.edge_ids[-1] in {e.id for e in EDGES}


def test_actions_pathway_tier_and_gene_only_experiment(store: GraphStore) -> None:
    disease = store.get_node("D:3")
    assert disease is not None
    actions = build_actions(store, disease)
    s1 = next(a for a in actions.assets if a.node.id == "S:1")
    assert "shared pathway only" in s1.differs
    gene_only = GraphStore(
        (_node("D:5", NodeType.DISEASE, "Five"), _node("G:5", NodeType.GENE, "G5")),
        (_edge("D:5", Relation.CAUSED_BY, "G:5"),),
    )
    five = gene_only.get_node("D:5")
    assert five is not None
    experiment = next_experiment(gene_only, five, ())
    assert experiment is not None and "G5" in experiment.text
    lone = _node("D:6", NodeType.DISEASE, "Six")
    assert next_experiment(GraphStore((lone,), ()), lone, ()) is None
    assert build_actions(GraphStore((lone,), ()), lone).coverage is not None


def test_reusable_text_fallbacks() -> None:
    assert reusable_text(_node("PUB:2", NodeType.PUBLICATION, "Paper")).startswith("Paper")
    described = _node("A:1", NodeType.ASSET, "Asset", description="Useful marker. More")
    assert reusable_text(described) == "Useful marker."
    curated = _node("S:9", NodeType.STUDY, "Trial", curated_notes="UK. Reusable for X: data")
    assert reusable_text(curated) == "Reusable for X: data."


# ---- app wiring ------------------------------------------------------------------------------


def test_lazy_search_index_on_synthetic_store(api: TestClient) -> None:
    body = api.get("/api/v1/search", params={"q": "GENE1"}).json()
    assert body["results"][0]["node"]["id"] == "G:1"


def test_build_search_index_uses_embedding_cache(store: GraphStore, tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot" / "atlas-snapshot.json"
    settings = Settings(SNAPSHOT_PATH=snapshot)  # type: ignore[call-arg]
    assert build_search_index(None, settings) is None
    lexical = build_search_index(store, settings)
    assert lexical is not None and "semantic" not in lexical.searched[0]
    cache_dir = tmp_path / "cache" / "embeddings"
    cache_dir.mkdir(parents=True)
    model = settings.openai_embed_model
    vectors = {
        embedding_key(model, "Seizure"): [1.0, 0.0],
        embedding_key(model, "fits"): [1.0, 0.0],
    }
    (cache_dir / f"{model}.json").write_text(json.dumps({"vectors": vectors}), encoding="utf-8")
    semantic = build_search_index(store, settings)
    assert semantic is not None and "semantic" in semantic.searched[0]
    hits = semantic.search("fits")
    assert hits and hits[0].node_id == "HP:1" and hits[0].match_reason == "semantic"
    (cache_dir / f"{model}.json").write_text("{not json", encoding="utf-8")
    assert build_search_index(store, settings) is not None


@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/search?q=x",
        "/api/v1/nodes/D:1",
        "/api/v1/nodes/D:1/neighbors",
        "/api/v1/edges/E:0000000000000000",
        "/api/v1/paths?from=D:1&to=D:2",
        "/api/v1/coverage/D:1",
        "/api/v1/actions/D:1",
    ],
)
def test_503_without_snapshot(tmp_path: Path, url: str) -> None:
    app = create_app(Settings(SNAPSHOT_PATH=tmp_path / "missing.json"))  # type: ignore[call-arg]
    with TestClient(app) as test_client:
        assert test_client.get(url).status_code == 503
