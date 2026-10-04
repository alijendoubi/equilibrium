"""Curated contradictions: YAML validation, edge building, contradicted_by both ways, API."""

import copy
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from atlas.api.main import create_app
from atlas.config import Settings
from atlas.ingest import curated
from atlas.models.evidence import Edge, EvidenceType, Node, NodeType, Provenance, Relation
from atlas.pipeline.build import SNAPSHOT_DIR, SNAPSHOT_FILE
from atlas.trust.contradictions import ContradictionError, apply, parse

PSAP = "HGNC:9498"
PD24 = "MONDO:0859183"
LETTER = "PMID:33793763"
MOVES_PD = "clinicaltrials:NCT02906020"
LEAP2MONO = "clinicaltrials:NCT05222906"

ENTRY: dict[str, Any] = {
    "id": "x-vs-y",
    "summary": "Y disputes X.",
    "verification": "verified",
    "contradicts": {"source_id": "PMID:2", "target_id": "MONDO:0000001"},
    "bears_on": [
        {"source_id": "HGNC:1", "relation": "risk_factor_for", "target_id": "MONDO:0000001"}
    ],
    "new_nodes": [
        {"id": "PMID:2", "type": "publication", "label": "Y", "url": "https://example.org/y"}
    ],
    "evidence": [
        {"url": "https://example.org/y", "quote": "No association.", "retrieved": "2026-10-04"}
    ],
    "curator": "claude-agent, needs human check",
}


def _doc(**changes: Any) -> dict[str, Any]:
    entry = copy.deepcopy(ENTRY)
    entry.update(changes)
    return {"contradictions": [entry]}


def _graph() -> tuple[list[Node], list[Edge]]:
    nodes = [
        Node(id="HGNC:1", type=NodeType.GENE, label="G"),
        Node(id="MONDO:0000001", type=NodeType.DISEASE, label="D"),
    ]
    edges = [
        Edge(
            source_id="HGNC:1",
            target_id="MONDO:0000001",
            relation=Relation.RISK_FACTOR_FOR,
            provenance=Provenance(
                source="monarch",
                source_record_id=record,
                url="https://example.org/x",  # type: ignore[arg-type]
                retrieved_at=datetime(2026, 10, 4, tzinfo=UTC),
            ),
            confidence=0.9,
            evidence_type=EvidenceType.CURATED,
        )
        for record in ("omim", "orphanet")
    ]
    return nodes, edges


def test_committed_yaml_is_valid_and_cites_urls() -> None:
    items = parse(curated.load_yaml("contradictions"))
    ids = {item.id for item in items}
    assert {"venglustat-gd3-vs-gba-pd", "psap-pd-susceptibility-contested"} <= ids
    for item in items:
        assert item.evidence
        assert all(e.url.startswith("https://") and e.quote for e in item.evidence)
        assert "needs human check" in item.curator


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"evidence": [{"quote": "q", "retrieved": "2026-10-04"}]}, "url"),
        ({"evidence": [{"url": "ftp://x", "quote": "q", "retrieved": "2026-10-04"}]}, "url"),
        ({"evidence": [{"url": "https://x.org", "retrieved": "2026-10-04"}]}, "quote"),
        ({"evidence": [{"url": "https://x.org", "quote": "q", "retrieved": "soon"}]}, "date"),
        ({"evidence": []}, "evidence"),
        ({"id": "Not A Slug"}, "slug"),
        ({"verification": "maybe"}, "verification"),
        ({"contradicts": {"source_id": "PMID:2"}}, "target_id"),
        ({"summary": ""}, "summary"),
        ({"bears_on": [{"source_id": "HGNC:1"}]}, "bears_on"),
        ({"bears_on": [{"source_id": "a:1", "relation": "nope", "target_id": "b:1"}]}, "relation"),
        ({"bears_on": [{"edge_id": "E:xyz"}]}, "edge id"),
        ({"bears_on": ["HGNC:1"]}, "mappings"),
        ({"new_nodes": [{"id": "PMID:2", "type": "publication", "label": "Y"}]}, "url"),
        (
            {"new_nodes": [{"id": "PMID:2", "type": "nope", "label": "Y", "url": "https://x.org"}]},
            "bad new node",
        ),
    ],
)
def test_yaml_validation_rejects(changes: dict[str, Any], message: str) -> None:
    with pytest.raises(ContradictionError, match=message):
        parse(_doc(**changes))


def test_duplicate_ids_rejected() -> None:
    with pytest.raises(ContradictionError, match="unique"):
        parse({"contradictions": [ENTRY, ENTRY]})


def test_apply_fills_contradicted_by_both_ways() -> None:
    nodes, edges = _graph()
    out_nodes, out_edges = apply(parse(_doc()), nodes, edges)
    assert [n.id for n in out_nodes][-1] == "PMID:2"
    contradicts = [e for e in out_edges if e.relation is Relation.CONTRADICTS]
    assert len(contradicts) == 1
    edge = contradicts[0]
    assert edge.evidence_type is EvidenceType.CURATED
    assert str(edge.provenance.url) == "https://example.org/y"
    assert edge.provenance.evidence_quote == "No association."
    assert edge.qualifiers["verification"] == "verified"
    assert edge.contradicted_by == tuple(sorted(e.id for e in edges))
    for disputed in out_edges[:2]:
        assert disputed.contradicted_by == (edge.id,)


def test_apply_by_edge_id_and_unknown_references() -> None:
    nodes, edges = _graph()
    by_id = _doc(bears_on=[{"edge_id": edges[0].id}])
    _, out_edges = apply(parse(by_id), nodes, edges)
    assert out_edges[0].contradicted_by and not out_edges[1].contradicted_by
    with pytest.raises(ContradictionError, match="matches no edge"):
        apply(parse(_doc(bears_on=[{"edge_id": "E:0000000000000000"}])), nodes, edges)
    with pytest.raises(ContradictionError, match="unknown node"):
        apply(parse(_doc(new_nodes=[])), nodes, edges)


# ---- the committed snapshot -------------------------------------------------------------------


@pytest.fixture(scope="module")
def snapshot() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((SNAPSHOT_DIR / SNAPSHOT_FILE).read_text(encoding="utf-8"))
    return data


def test_snapshot_has_both_seed_contradictions(snapshot: dict[str, Any]) -> None:
    by_id = {e["id"]: e for e in snapshot["edges"]}
    pairs = {
        (e["source_id"], e["target_id"]): e
        for e in by_id.values()
        if e["relation"] == "contradicts"
    }
    venglustat = pairs[(MOVES_PD, LEAP2MONO)]
    assert venglustat["confidence"] == 0.80
    letter = pairs[(LETTER, PD24)]
    assert letter["qualifiers"]["verification"] == "unverified"
    assert letter["confidence"] == 0.50
    psap_pd = [
        e
        for e in by_id.values()
        if (e["source_id"], e["relation"], e["target_id"]) == (PSAP, "risk_factor_for", PD24)
    ]
    assert psap_pd
    for edge in psap_pd:
        assert edge["contradicted_by"] == [letter["id"]]
        assert edge["confidence"] < 0.90
        assert any("contradicted by 1 record" in r for r in edge["confidence_reasons"])
    assert letter["contradicted_by"] == sorted(e["id"] for e in psap_pd)
    # every contradicted_by id resolves
    for edge in by_id.values():
        assert all(ref in by_id for ref in edge["contradicted_by"])


@pytest.fixture(scope="module")
def api() -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as client:
        yield client


def test_edge_detail_returns_contradictions(api: TestClient, snapshot: dict[str, Any]) -> None:
    psap_pd = next(
        e
        for e in snapshot["edges"]
        if (e["source_id"], e["relation"], e["target_id"]) == (PSAP, "risk_factor_for", PD24)
    )
    body = api.get(f"/api/v1/edges/{psap_pd['id']}").json()
    assert [e["source_id"] for e in body["contradictions"]] == [LETTER]
    assert body["contradictions"][0]["relation"] == "contradicts"


def test_path_through_contested_edge_is_flagged(api: TestClient) -> None:
    body = api.get("/api/v1/paths", params={"from": PSAP, "to": PD24, "k": 1}).json()
    best = body["paths"][0]
    assert [n["id"] for n in best["nodes"]] == [PSAP, PD24]
    assert best["has_contradiction"] is True


def test_path_through_counterexample_edge_is_flagged(api: TestClient) -> None:
    body = api.get("/api/v1/paths", params={"from": MOVES_PD, "to": LEAP2MONO, "k": 1}).json()
    best = body["paths"][0]
    assert [e["relation"] for e in best["edges"]] == ["contradicts"]
    assert best["has_contradiction"] is True


def test_manifest_records_rubric_version_and_contradictions() -> None:
    manifest = json.loads((SNAPSHOT_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["rubric_version"] == "trust-v1"
    assert manifest["contradictions"] == [
        "venglustat-gd3-vs-gba-pd",
        "psap-pd-susceptibility-contested",
    ]


def test_golden_hero_path_is_not_flagged(api: TestClient) -> None:
    body = api.get(
        "/api/v1/paths", params={"from": "MONDO:0009266", "to": "clinicaltrials:NCT05778617"}
    ).json()
    assert body["paths"][0]["has_contradiction"] is False
