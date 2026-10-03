"""GO mechanisms and ClinVar counts connectors."""

import httpx

from atlas.ingest import clinvar, curated, go
from atlas.models.evidence import NodeType, Relation
from tests._ingest_helpers import (
    assert_provenance,
    assert_sorted_unique,
    assert_valid_ids,
    fake_client,
    load_fixture,
)


def _mechanisms() -> list[dict[str, object]]:
    return curated.mechanisms(curated.load_all())


def test_go_normalize_builds_whitelisted_mechanisms_and_edges() -> None:
    result = go.normalize(load_fixture("go"), _mechanisms())
    assert_valid_ids(result.nodes)
    assert_provenance(result.edges, "ingest:go")
    assert_sorted_unique(result.nodes, result.edges)
    assert {node.type for node in result.nodes} == {NodeType.MECHANISM}
    whitelist = {node.id for node in result.nodes}
    pairs = {(e.source_id, e.target_id) for e in result.edges}
    assert ("HGNC:4177", "GO:0006680") in pairs
    assert all(e.relation is Relation.PARTICIPATES_IN for e in result.edges)
    assert all(e.target_id in whitelist for e in result.edges)


def test_go_confidence_depends_on_evidence_codes() -> None:
    payload = load_fixture("go")
    annotation = {
        "gene": "HGNC:4177",
        "term": "GO:0006914",
        "term_label": "autophagy",
        "matched": ["GO:0006914"],
        "evidence": ["ECO:0000501"],
        "publications": [],
        "knowledge_source": "infores:uniprot",
    }
    iea_only = go.normalize({**payload, "annotations": [annotation]}, _mechanisms())
    assert iea_only.edges[0].confidence == go.CONFIDENCE_IEA_ONLY
    mixed = go.normalize(
        {**payload, "annotations": [annotation, {**annotation, "evidence": ["ECO:0000315"]}]},
        _mechanisms(),
    )
    assert mixed.edges[0].confidence == go.CONFIDENCE_EXPERIMENTAL
    assert mixed.edges[0].qualifiers["annotation_count"] == "2"


def test_go_fetch_keeps_only_whitelisted_closure_matches() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/version"):
            return httpx.Response(200, json={"monarch_kg_version": "v"})
        items = [
            {
                "object": "GO:0006680",
                "object_label": "glucosylceramide catabolic process",
                "object_closure": ["GO:0006680", "GO:0006665"],
                "has_evidence": ["ECO:0000315"],
                "publications": ["PMID:1"],
                "primary_knowledge_source": "infores:uniprot",
            },
            {"object": "GO:9999999", "object_closure": ["GO:9999999"]},
            {"object": "GO:0006680", "object_closure": ["GO:0006680"], "negated": True},
        ]
        return httpx.Response(200, json={"items": items, "total": len(items)})

    with fake_client(handler) as client:
        payload = go.fetch(client, ["GO:0006680", "GO:0006665"])
    assert len(payload["annotations"]) == len(go.SEED_GENES)
    assert payload["annotations"][0]["matched"] == ["GO:0006665", "GO:0006680"]


def test_clinvar_normalize_sets_gene_count_attributes() -> None:
    result = clinvar.normalize(load_fixture("clinvar"))
    assert_valid_ids(result.nodes)
    assert result.edges == ()
    gba1 = next(node for node in result.nodes if node.id == "HGNC:4177")
    assert gba1.label == "GBA1"
    assert int(gba1.attributes["clinvar_pathogenic_or_likely_pathogenic"]) > 0
    assert gba1.attributes["clinvar_url"].startswith("https://www.ncbi.nlm.nih.gov/clinvar/")


def test_clinvar_fetch_counts_and_uses_api_key() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("einfo.fcgi"):
            return httpx.Response(200, json={"einforesult": {"dbinfo": [{"dbbuild": "B1"}]}})
        return httpx.Response(200, json={"esearchresult": {"count": "7"}})

    with fake_client(handler) as client:
        payload = clinvar.fetch(client, api_key="k")
    assert payload["meta"]["source_version"] == "B1"
    assert payload["counts"]["HGNC:4177"]["total"] == 7
    assert all(r.url.params.get("api_key") == "k" for r in seen[1:])
    assert clinvar.min_interval("k") < clinvar.min_interval(None)
