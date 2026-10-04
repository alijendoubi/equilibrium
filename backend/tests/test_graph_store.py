"""Read-only graph store: loading, validation, immutable accessors, API dependency."""

import json
from datetime import UTC, datetime
from pathlib import Path

import networkx as nx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from atlas.api.deps import get_store
from atlas.config import DEFAULT_SNAPSHOT_PATH
from atlas.graph.store import GraphStore, SnapshotError, load_store, thaw
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


NODES = (
    Node(id="MONDO:0009266", type=NodeType.DISEASE, label="Gaucher disease type II"),
    Node(id="HGNC:4177", type=NodeType.GENE, label="GBA1"),
    Node(id="MONDO:0008199", type=NodeType.DISEASE, label="late-onset Parkinson disease"),
    Node(id="HP:0001250", type=NodeType.PHENOTYPE, label="Seizure", attributes={"ic": "3.1"}),
)
EDGES = (
    _edge("MONDO:0009266", Relation.CAUSED_BY, "HGNC:4177"),
    _edge("HGNC:4177", Relation.RISK_FACTOR_FOR, "MONDO:0008199"),
    _edge("MONDO:0009266", Relation.HAS_PHENOTYPE, "HP:0001250"),
)


def _store() -> GraphStore:
    return GraphStore(NODES, EDGES, manifest={"snapshot_id": "sha256:x", "counts": {"nodes": 4}})


def test_accessors_return_sorted_immutable_results() -> None:
    store = _store()
    assert store.snapshot_id == "sha256:x"
    assert (store.node_count, store.edge_count) == (4, 3)
    gene = store.get_node("HGNC:4177")
    assert gene is not None and gene.label == "GBA1"
    assert store.get_node("nope") is None
    assert store.get_edge(EDGES[0].id) == EDGES[0]
    assert [n.id for n in store.nodes(NodeType.DISEASE)] == ["MONDO:0008199", "MONDO:0009266"]
    assert len(store.nodes()) == 4


def test_edges_for_respects_direction_and_relations() -> None:
    store = _store()
    both = store.edges_for("HGNC:4177")
    assert {e.relation for e in both} == {Relation.CAUSED_BY, Relation.RISK_FACTOR_FOR}
    assert [e.relation for e in store.edges_for("HGNC:4177", "out")] == [Relation.RISK_FACTOR_FOR]
    assert [e.relation for e in store.edges_for("HGNC:4177", "in")] == [Relation.CAUSED_BY]
    phen = store.edges_for("MONDO:0009266", relations=[Relation.HAS_PHENOTYPE])
    assert [e.target_id for e in phen] == ["HP:0001250"]
    assert store.edges_for("unknown") == ()


def test_neighbors_are_distinct_and_sorted() -> None:
    store = _store()
    assert [n.id for n in store.neighbors("HGNC:4177")] == ["MONDO:0008199", "MONDO:0009266"]
    assert [n.id for n in store.neighbors("HGNC:4177", direction="out")] == ["MONDO:0008199"]


def test_graph_and_manifest_are_read_only() -> None:
    store = _store()
    with pytest.raises(nx.NetworkXError):
        store.graph.add_node("X:1")
    with pytest.raises(TypeError):
        store.manifest["snapshot_id"] = "other"  # type: ignore[index]
    assert thaw(store.manifest) == {"snapshot_id": "sha256:x", "counts": {"nodes": 4}}
    assert thaw((1, {"a": (2,)})) == [1, {"a": [2]}]


def test_store_rejects_dangling_and_duplicate_ids() -> None:
    with pytest.raises(SnapshotError, match="dangling"):
        GraphStore(NODES[:1], EDGES[:1])
    with pytest.raises(SnapshotError, match="duplicate node"):
        GraphStore((*NODES, NODES[0]), ())
    with pytest.raises(SnapshotError, match="duplicate edge"):
        GraphStore(NODES, (*EDGES, EDGES[0]))


def _write_snapshot(path: Path, nodes: object, edges: object) -> Path:
    path.write_text(json.dumps({"nodes": nodes, "edges": edges}), encoding="utf-8")
    return path


def test_from_snapshot_round_trip_and_errors(tmp_path: Path) -> None:
    good = _write_snapshot(
        tmp_path / "atlas-snapshot.json",
        [n.model_dump(mode="json") for n in NODES],
        [e.model_dump(mode="json") for e in EDGES],
    )
    (tmp_path / "manifest.json").write_text('{"snapshot_id": "sha256:y"}', encoding="utf-8")
    store = GraphStore.from_snapshot(good)
    assert store.snapshot_id == "sha256:y" and store.edge_count == 3

    with pytest.raises(SnapshotError, match="not found"):
        GraphStore.from_snapshot(tmp_path / "missing.json")
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{", encoding="utf-8")
    with pytest.raises(SnapshotError, match="unreadable"):
        GraphStore.from_snapshot(bad_json)
    tampered = [e.model_dump(mode="json") for e in EDGES]
    tampered[0]["id"] = "E:0000000000000000"
    bad_edge = _write_snapshot(
        tmp_path / "t.json", [n.model_dump(mode="json") for n in NODES], tampered
    )
    with pytest.raises(SnapshotError, match="invalid"):
        GraphStore.from_snapshot(bad_edge)


def test_load_store_never_raises(tmp_path: Path) -> None:
    store, status = load_store(tmp_path / "none.json")
    assert store is None and status.status == "missing"
    broken = tmp_path / "b.json"
    broken.write_text("[]", encoding="utf-8")
    store, status = load_store(broken)
    assert store is None and status.status == "error"


def test_committed_snapshot_loads_with_hero_path() -> None:
    store, status = load_store(DEFAULT_SNAPSHOT_PATH)
    assert status.status == "loaded" and store is not None
    assert store.snapshot_id and store.snapshot_id.startswith("sha256:")
    gene = store.get_node("HGNC:4177")
    assert gene is not None and gene.type is NodeType.GENE
    hero_causes = store.edges_for("MONDO:0009266", "out", [Relation.CAUSED_BY])
    assert "HGNC:4177" in {e.target_id for e in hero_causes}
    pd = {n.id for n in store.neighbors("HGNC:4177", relations=[Relation.RISK_FACTOR_FOR])}
    assert "MONDO:0008199" in pd
    trial = store.get_node("clinicaltrials:NCT05778617")
    assert trial is not None and trial.type is NodeType.STUDY
    assert "org:cure-parkinsons" in {n.id for n in store.neighbors(trial.id)}
    gap_studies = store.edges_for("MONDO:0012517", "in", [Relation.STUDIES_CONDITION])
    assert gap_studies == ()
    assert store.coverage["gap_disease"] == "MONDO:0012517"


def _request(store: GraphStore | None) -> Request:
    from fastapi import FastAPI

    app = FastAPI()
    app.state.store = store
    return Request({"type": "http", "app": app})


def test_get_store_dependency() -> None:
    store = _store()
    assert get_store(_request(store)) is store
    with pytest.raises(HTTPException) as excinfo:
        get_store(_request(None))
    assert excinfo.value.status_code == 503
