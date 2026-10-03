"""Monarch connector: recorded fixture -> nodes/edges; fetch against a fake API."""

import httpx

from atlas.ingest import monarch
from atlas.models.evidence import NodeType, Relation
from tests._ingest_helpers import (
    assert_provenance,
    assert_sorted_unique,
    assert_valid_ids,
    fake_client,
    load_fixture,
)


def _result() -> monarch.IngestResult:
    return monarch.normalize(load_fixture("monarch"))


def test_normalize_produces_valid_sorted_nodes_and_edges() -> None:
    result = _result()
    assert result.source == "monarch"
    assert result.source_version and result.source_version.startswith("monarch-kg")
    assert_valid_ids(result.nodes)
    assert_provenance(result.edges, "ingest:monarch")
    assert_sorted_unique(result.nodes, result.edges)
    node_ids = {node.id for node in result.nodes}
    for edge in result.edges:
        assert edge.source_id in node_ids and edge.target_id in node_ids


def test_entity_nodes_carry_description_synonyms_and_xrefs() -> None:
    nodes = {node.id: node for node in _result().nodes}
    hero = nodes["MONDO:0009266"]
    assert hero.type is NodeType.DISEASE
    assert hero.label == "Gaucher disease type II"
    assert hero.attributes["slice_role"] == "hero"
    assert "acute neuronopathic Gaucher disease" in hero.synonyms
    assert "ORPHA:77260" in hero.xrefs and "OMIM:230900" in hero.xrefs
    assert hero.attributes["description"].startswith("Gaucher disease type 2")
    gene = nodes["HGNC:4177"]
    assert gene.type is NodeType.GENE and gene.label == "GBA1"
    assert "GBA" in gene.synonyms
    assert gene.attributes["full_name"] == "glucosylceramidase beta 1"


def test_gene_disease_predicates_map_to_relations() -> None:
    edges = _result().edges
    causal = [
        e
        for e in edges
        if e.relation is Relation.CAUSED_BY
        and e.source_id == "MONDO:0009266"
        and e.target_id == "HGNC:4177"
    ]
    assert {e.qualifiers["primary_knowledge_source"] for e in causal} == {
        "infores:omim",
        "infores:orphanet",
    }
    risk = [
        e
        for e in edges
        if e.relation is Relation.RISK_FACTOR_FOR
        and e.source_id == "HGNC:4177"
        and e.target_id == "MONDO:0008199"
    ]
    by_source = {e.qualifiers["primary_knowledge_source"]: e for e in risk}
    assert by_source["infores:omim"].qualifiers["monarch_predicate"] == "biolink:contributes_to"
    assert by_source["infores:orphanet"].qualifiers["association_role"] == "unspecified"
    assert all(e.evidence_type.value == "curated" and e.confidence == 0.9 for e in edges)


def test_gap_disease_has_cause_and_phenotypes() -> None:
    edges = _result().edges
    gap = [e for e in edges if e.source_id == "MONDO:0012517"]
    assert any(e.relation is Relation.CAUSED_BY and e.target_id == "HGNC:9498" for e in gap)
    assert any(e.relation is Relation.HAS_PHENOTYPE for e in gap)


def test_phenotype_edges_keep_frequency() -> None:
    phen = [e for e in _result().edges if e.relation is Relation.HAS_PHENOTYPE]
    assert phen
    with_freq = [e for e in phen if "frequency" in e.qualifiers]
    assert with_freq
    assert with_freq[0].qualifiers["frequency"] in monarch.FREQUENCY_LABELS.values()


def test_normalize_is_deterministic() -> None:
    first, second = _result(), _result()
    assert first.nodes == second.nodes
    assert [e.id for e in first.edges] == [e.id for e in second.edges]


def test_negated_and_unknown_predicates_are_skipped() -> None:
    payload = load_fixture("monarch")
    item = dict(payload["gene_disease"][0])
    payload["gene_disease"] = [
        {**item, "negated": True},
        {**item, "predicate": "biolink:something_else"},
    ]
    payload["disease_phenotype"] = [{**payload["disease_phenotype"][0], "negated": True}]
    result = monarch.normalize(payload)
    assert result.edges == ()


def test_normalize_xref() -> None:
    assert monarch.normalize_xref("Orphanet:77260") == "ORPHA:77260"
    assert monarch.normalize_xref("OMIM:230900") == "OMIM:230900"
    assert monarch.normalize_xref("broken") is None


def test_phenotype_ids_lists_slice_terms() -> None:
    ids = monarch.phenotype_ids(load_fixture("monarch"))
    assert ids == tuple(sorted(set(ids)))
    assert all(term.startswith("HP:") for term in ids)


def test_fetch_pages_and_trims_records() -> None:
    fixture = load_fixture("monarch")

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/version"):
            return httpx.Response(200, json={"monarch_kg_version": "2026-09-04"})
        if "/entity/" in path:
            entity_id = path.rsplit("/", 1)[1]
            return httpx.Response(200, json={"id": entity_id, "name": entity_id, "extra": 1})
        subject = request.url.params["subject"]
        items = [
            {**a, "object_closure": ["X"]}
            for a in fixture["gene_disease"] + fixture["disease_phenotype"]
            if a["subject"] == subject
        ]
        offset = int(request.url.params["offset"])
        return httpx.Response(
            200, json={"items": items[offset : offset + 500], "total": len(items)}
        )

    with fake_client(handler) as client:
        payload = monarch.fetch(client)
    assert payload["meta"]["source_version"] == "monarch-kg 2026-09-04"
    assert set(payload["entities"]) == set(monarch.SEED_DISEASES) | set(monarch.SEED_GENES)
    assert "extra" not in payload["entities"]["HGNC:4177"]
    assert all("object_closure" not in a for a in payload["gene_disease"])
    assert len(payload["gene_disease"]) == len(fixture["gene_disease"])
