"""Graph read API against the real committed snapshot: goldens, encoding, contract keys."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from atlas.api.main import create_app
from atlas.config import Settings

GAUCHER_2 = "MONDO:0009266"
GAUCHER_3 = "MONDO:0009267"
LATE_PD = "MONDO:0008199"
ASPRO_PD = "clinicaltrials:NCT05778617"
SAPOSIN_C = "MONDO:0012517"
GBA1 = "HGNC:4177"

# Key sets of frontend/src/lib/api/types.ts (the contract). Keep in sync with that file.
NODE_KEYS = {"id", "type", "label", "synonyms", "xrefs", "attributes"}
EDGE_KEYS = {
    "id",
    "source_id",
    "target_id",
    "relation",
    "provenance",
    "confidence",
    "confidence_reasons",
    "evidence_type",
    "contradicted_by",
    "qualifiers",
}
PROVENANCE_KEYS = {
    "source",
    "source_record_id",
    "url",
    "retrieved_at",
    "source_version",
    "evidence_quote",
    "extractor",
    "supporting_edge_ids",
}
SEARCH_KEYS = {"query", "results", "searched"}
SEARCH_RESULT_KEYS = {"node", "score", "match_reason", "matched_text"}
NODE_SUMMARY_KEYS = {"node", "counts", "edges", "neighbors", "cluster_id", "coverage_status"}
PATH_RESPONSE_KEYS = {"from", "to", "paths", "coverage"}
PATH_KEYS = {"nodes", "edges", "cost", "has_inferred", "has_contradiction"}
ACTIONS_KEYS = {
    "disease_id",
    "partners",
    "assets",
    "next_experiment",
    "review_checklist",
    "coverage",
    "shared_investigators",  # additive (#38); not in types.ts yet, zod drops unknown keys
}
PARTNER_KEYS = {"node", "why", "edge_ids"}
ASSET_KEYS = {"node", "reusable", "differs", "edge_ids"}
NEXT_EXPERIMENT_KEYS = {"text", "is_hypothesis", "edge_ids"}
COVERAGE_KEYS = {
    "query",
    "result",
    "searched",
    "not_searched",
    "missing_evidence",
    "weak_leads",
    "next_questions",
}
SOURCE_SEARCHED_REQUIRED = {"source", "records_found"}
SOURCE_SEARCHED_OPTIONAL = {"source_version", "query"}
WEAK_LEAD_KEYS = {"path_edge_ids", "min_confidence", "why_weak"}


@pytest.fixture(scope="module")
def api() -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as test_client:
        yield test_client


def _get(api: TestClient, url: str, **params: Any) -> Any:
    response = api.get(url, params=params or None)
    assert response.status_code == 200, response.text
    return response.json()


def _check_node(node: dict[str, Any]) -> None:
    assert set(node) == NODE_KEYS


def _check_edge(edge: dict[str, Any]) -> None:
    assert set(edge) == EDGE_KEYS
    assert set(edge["provenance"]) == PROVENANCE_KEYS


def _check_coverage(report: dict[str, Any]) -> None:
    assert set(report) == COVERAGE_KEYS
    for row in report["searched"]:
        assert set(row) >= SOURCE_SEARCHED_REQUIRED
        assert set(row) <= SOURCE_SEARCHED_REQUIRED | SOURCE_SEARCHED_OPTIONAL
        assert all(value is not None for value in row.values())
    for lead in report["weak_leads"]:
        assert set(lead) == WEAK_LEAD_KEYS


# ---- search ----------------------------------------------------------------------------------


def test_search_contract_and_reasons(api: TestClient) -> None:
    body = _get(api, "/api/v1/search", q="Gaucher disease type II")
    assert set(body) == SEARCH_KEYS
    assert body["searched"]
    top = body["results"][0]
    assert set(top) == SEARCH_RESULT_KEYS
    _check_node(top["node"])
    assert top["node"]["id"] == GAUCHER_2
    assert top["match_reason"] == "exact"


def test_search_synonym_and_types_filter(api: TestClient) -> None:
    body = _get(api, "/api/v1/search", q="ASPro-PD", types="study")
    assert body["results"][0]["node"]["id"] == ASPRO_PD
    assert body["results"][0]["match_reason"] == "synonym"
    assert all(r["node"]["type"] == "study" for r in body["results"])


def test_search_limit_and_validation(api: TestClient) -> None:
    assert len(_get(api, "/api/v1/search", q="gaucher", limit=2)["results"]) <= 2
    assert api.get("/api/v1/search", params={"q": "  "}).status_code == 422
    assert api.get("/api/v1/search").status_code == 422
    assert api.get("/api/v1/search", params={"q": "x", "types": "planet"}).status_code == 422


# ---- nodes / neighbors / edges ---------------------------------------------------------------


@pytest.mark.parametrize("node_id", [GAUCHER_2, "MONDO%3A0009266"])
def test_node_summary_accepts_raw_and_encoded_ids(api: TestClient, node_id: str) -> None:
    body = _get(api, f"/api/v1/nodes/{node_id}")
    assert set(body) == NODE_SUMMARY_KEYS
    assert body["node"]["id"] == GAUCHER_2
    assert set(body["counts"]) == {"edges", "by_relation"}
    assert body["counts"]["edges"] >= len(body["edges"])
    assert body["cluster_id"] is None
    assert body["coverage_status"] == "supported"
    for edge in body["edges"]:
        _check_edge(edge)
        assert GAUCHER_2 in (edge["source_id"], edge["target_id"])
    # non-phenotype edges come first
    assert body["edges"][0]["relation"] != "has_phenotype"
    referenced = {e["source_id"] for e in body["edges"]} | {e["target_id"] for e in body["edges"]}
    assert {n["id"] for n in body["neighbors"]} == referenced - {GAUCHER_2}


def test_node_404_and_gap_status(api: TestClient) -> None:
    assert api.get("/api/v1/nodes/MONDO:9999999").status_code == 404
    assert _get(api, f"/api/v1/nodes/{SAPOSIN_C}")["coverage_status"] == "gap"


def test_neighbors_filters(api: TestClient) -> None:
    body = _get(
        api,
        f"/api/v1/nodes/{GAUCHER_2}/neighbors",
        relations="caused_by,represents",
        min_confidence=0.55,
        evidence="curated",
    )
    assert body["node_id"] == GAUCHER_2
    assert body["edges"]
    assert {e["relation"] for e in body["edges"]} <= {"caused_by", "represents"}
    assert all(e["confidence"] >= 0.55 for e in body["edges"])
    ids = {n["id"] for n in body["nodes"]}
    assert GBA1 in ids
    typed = _get(api, f"/api/v1/nodes/{GAUCHER_2}/neighbors", types="gene")
    assert {n["type"] for n in typed["nodes"]} == {"gene"}
    bad = api.get(f"/api/v1/nodes/{GAUCHER_2}/neighbors", params={"relations": "nope"})
    assert bad.status_code == 422
    assert api.get("/api/v1/nodes/X:1/neighbors").status_code == 404


def test_edge_detail(api: TestClient) -> None:
    edge_id = _get(api, f"/api/v1/nodes/{GAUCHER_2}")["edges"][0]["id"]
    body = _get(api, f"/api/v1/edges/{edge_id}")
    assert set(body) == {"edge", "source", "target", "contradictions", "supporting_edges"}
    _check_edge(body["edge"])
    assert body["edge"]["id"] == edge_id
    assert api.get("/api/v1/edges/E:0000000000000000").status_code == 404


# ---- paths -----------------------------------------------------------------------------------


def test_golden_path_gaucher_to_aspro_pd(api: TestClient) -> None:
    body = _get(api, "/api/v1/paths", **{"from": GAUCHER_2, "to": ASPRO_PD, "k": 3})
    assert set(body) == PATH_RESPONSE_KEYS
    assert body["from"] == GAUCHER_2
    assert body["to"] == ASPRO_PD
    assert body["coverage"] is None
    assert 1 <= len(body["paths"]) <= 3
    best = body["paths"][0]
    assert set(best) == PATH_KEYS
    assert [n["id"] for n in best["nodes"]] == [GAUCHER_2, GBA1, LATE_PD, ASPRO_PD]
    for path in body["paths"]:
        assert path["nodes"][0]["id"] == GAUCHER_2
        assert path["nodes"][-1]["id"] == ASPRO_PD
        assert len(path["edges"]) == len(path["nodes"]) - 1
        for i, edge in enumerate(path["edges"]):
            _check_edge(edge)
            ends = {edge["source_id"], edge["target_id"]}
            assert ends == {path["nodes"][i]["id"], path["nodes"][i + 1]["id"]}
        # no phenotype shortcut while gene routes exist
        assert all(n["type"] != "phenotype" for n in path["nodes"])
    costs = [p["cost"] for p in body["paths"]]
    assert costs == sorted(costs)


def test_paths_validation(api: TestClient) -> None:
    assert api.get("/api/v1/paths", params={"from": GAUCHER_2}).status_code == 422
    same = {"from": GAUCHER_2, "to": GAUCHER_2}
    assert api.get("/api/v1/paths", params=same).status_code == 422
    unknown = {"from": GAUCHER_2, "to": "MONDO:9999999"}
    assert api.get("/api/v1/paths", params=unknown).status_code == 404
    too_many = {"from": GAUCHER_2, "to": ASPRO_PD, "k": 9}
    assert api.get("/api/v1/paths", params=too_many).status_code == 422


# ---- coverage / actions ----------------------------------------------------------------------


def test_coverage_gap_disease(api: TestClient) -> None:
    body = _get(api, f"/api/v1/coverage/{SAPOSIN_C}")
    _check_coverage(body)
    assert body["query"] == SAPOSIN_C
    assert body["result"] == "no_supported_route"
    assert any("patient organisation" in m for m in body["missing_evidence"])
    assert any("International Gaucher Alliance" in q for q in body["next_questions"])
    assert "Orphanet patient-org directory" in body["not_searched"]
    sources = {row["source"]: row for row in body["searched"]}
    assert sources["clinicaltrials"]["records_found"] == 0
    assert sources["monarch"]["records_found"] > 0
    assert "source_version" not in sources["curated"]
    assert body["weak_leads"]


def test_coverage_supported_and_404(api: TestClient) -> None:
    assert _get(api, f"/api/v1/coverage/{GAUCHER_2}")["result"] == "supported"
    assert _get(api, f"/api/v1/coverage/{GBA1}")["result"] == "supported"
    assert api.get("/api/v1/coverage/X:1").status_code == 404


@pytest.mark.parametrize("disease_id", [GAUCHER_2, GAUCHER_3])
def test_actions_golden(api: TestClient, disease_id: str) -> None:
    body = _get(api, f"/api/v1/actions/{disease_id}")
    assert set(body) == ACTIONS_KEYS
    assert body["disease_id"] == disease_id
    partners = {p["node"]["id"]: p for p in body["partners"]}
    assert "org:cure-parkinsons" in partners
    assert "GBA1" in partners["org:cure-parkinsons"]["why"]
    assets = {a["node"]["id"]: a for a in body["assets"]}
    assert ASPRO_PD in assets
    aspro = assets[ASPRO_PD]
    assert set(aspro) == ASSET_KEYS
    assert "Parkinson" in aspro["differs"]
    assert aspro["reusable"]
    for partner in body["partners"]:
        assert set(partner) == PARTNER_KEYS
        _check_node(partner["node"])
        assert partner["edge_ids"]
    experiment = body["next_experiment"]
    assert set(experiment) == NEXT_EXPERIMENT_KEYS
    assert experiment["is_hypothesis"] is True
    assert experiment["edge_ids"]
    assert body["review_checklist"]
    assert body["coverage"] is None
    # every cited edge exists
    for edge_id in aspro["edge_ids"] + experiment["edge_ids"]:
        assert api.get(f"/api/v1/edges/{edge_id}").status_code == 200


def test_actions_gap_and_errors(api: TestClient) -> None:
    body = _get(api, f"/api/v1/actions/{SAPOSIN_C}")
    assert body["partners"] == []
    _check_coverage(body["coverage"])
    assert body["coverage"]["result"] == "no_supported_route"
    assert api.get(f"/api/v1/actions/{GBA1}").status_code == 404
    assert api.get("/api/v1/actions/MONDO:9999999").status_code == 404


def test_responses_are_deterministic(api: TestClient) -> None:
    first = _get(api, f"/api/v1/actions/{GAUCHER_2}")
    assert _get(api, f"/api/v1/actions/{GAUCHER_2}") == first
