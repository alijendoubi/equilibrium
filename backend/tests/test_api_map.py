"""GET /api/v1/graph (evidence map) against the committed snapshot: goldens, caps, filters."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from atlas.api.main import create_app
from atlas.config import Settings
from atlas.graph.evidence_map import MAX_EDGES, MAX_NODES, TYPE_CAP, TYPE_CAPS

GAUCHER_2 = "MONDO:0009266"
LATE_PD = "MONDO:0008199"
PD24 = "MONDO:0859183"
GBA1 = "HGNC:4177"
PSAP = "HGNC:9498"
ASPRO_PD = "clinicaltrials:NCT05778617"
PSAP_LETTER = "PMID:33793763"

MAP_KEYS = {
    "center",
    "depth",
    "nodes",
    "edges",
    "contradiction_edge_ids",
    "truncated",
    "legend",
}
MAP_NODE_KEYS = {"node", "degree", "total_degree", "cluster_id", "distance"}


@pytest.fixture(scope="module")
def api() -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as test_client:
        yield test_client


def _map(api: TestClient, **params: Any) -> Any:
    response = api.get("/api/v1/graph", params=params or None)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == MAP_KEYS
    return body


def _ids(body: Any) -> list[str]:
    return [item["node"]["id"] for item in body["nodes"]]


def _types(body: Any) -> set[str]:
    return {item["node"]["type"] for item in body["nodes"]}


def _assert_consistent(body: Any) -> None:
    ids = set(_ids(body))
    assert len(ids) == len(body["nodes"])
    edge_ids = [edge["id"] for edge in body["edges"]]
    assert len(set(edge_ids)) == len(edge_ids)
    for edge in body["edges"]:
        assert edge["source_id"] in ids and edge["target_id"] in ids
        assert edge["provenance"]["source"]
    assert set(body["contradiction_edge_ids"]) <= set(edge_ids)
    assert len(body["nodes"]) <= MAX_NODES
    assert len(body["edges"]) <= MAX_EDGES
    for item in body["nodes"]:
        assert set(item) == MAP_NODE_KEYS
        assert item["total_degree"] >= item["degree"]
    assert sum(body["legend"]["node_types"].values()) == len(body["nodes"])
    assert sum(body["legend"]["relations"].values()) == len(body["edges"])
    assert body["truncated"]["nodes_hidden"] == sum(body["truncated"]["by_type"].values())


# ---- centered --------------------------------------------------------------------------------


@pytest.mark.parametrize("center", [GAUCHER_2, "MONDO%3A0009266"])
def test_center_gaucher2_includes_gba1_and_caused_by(api: TestClient, center: str) -> None:
    # Raw and URL-encoded ids in the query string decode to the same CURIE.
    response = api.get(f"/api/v1/graph?center={center}")
    assert response.status_code == 200, response.text
    body = response.json()
    _assert_consistent(body)
    assert body["center"] == GAUCHER_2
    assert body["depth"] == 1
    assert _ids(body)[0] == GAUCHER_2
    assert body["nodes"][0]["distance"] == 0
    assert GBA1 in _ids(body)
    caused_by = [
        e
        for e in body["edges"]
        if e["relation"] == "caused_by" and {e["source_id"], e["target_id"]} == {GAUCHER_2, GBA1}
    ]
    assert caused_by, "the GBA1 caused_by edge must be drawn"
    assert caused_by[0]["provenance"]["url"]
    assert caused_by[0]["confidence_reasons"]


def test_center_collapses_phenotypes_and_counts_them(api: TestClient) -> None:
    body = _map(api, center=GAUCHER_2)
    assert "phenotype" not in _types(body)
    assert body["truncated"]["by_type"]["phenotype"] > 0
    disease = body["nodes"][0]
    assert disease["cluster_id"] is not None
    assert disease["total_degree"] > disease["degree"]


def test_phenotypes_on_request_are_capped_per_type(api: TestClient) -> None:
    body = _map(api, center=GAUCHER_2, types="phenotype,gene")
    _assert_consistent(body)
    types = _types(body)
    assert "phenotype" in types and "gene" in types
    assert types <= {"phenotype", "gene", "disease"}
    shown = sum(1 for item in body["nodes"] if item["node"]["type"] == "phenotype")
    assert shown <= TYPE_CAP
    assert (
        sum(1 for i in _map(api, center=GBA1)["nodes"] if i["node"]["type"] == "investigator")
        <= TYPE_CAPS["investigator"]
    )
    assert body["truncated"]["by_type"].get("phenotype", 0) >= 0


def test_depth_two_reaches_further_and_respects_caps(api: TestClient) -> None:
    one = _map(api, center=GBA1)
    two = _map(api, center=GBA1, depth=2)
    _assert_consistent(two)
    assert len(two["nodes"]) >= len(one["nodes"])
    assert max(item["distance"] for item in two["nodes"]) >= 2
    small = _map(api, center=GBA1, depth=2, limit=20)
    _assert_consistent(small)
    assert len(small["nodes"]) <= 20
    assert small["truncated"]["nodes_hidden"] > 0


def test_relation_and_confidence_filters(api: TestClient) -> None:
    body = _map(api, center=GAUCHER_2, relations="caused_by")
    assert {e["relation"] for e in body["edges"]} <= {"caused_by"}
    strict = _map(api, center=GAUCHER_2, min_confidence=0.95)
    assert all(e["confidence"] >= 0.95 for e in strict["edges"])


def test_contradictions_are_included_and_flagged(api: TestClient) -> None:
    body = _map(api, center=PD24)
    _assert_consistent(body)
    contradicts = [e for e in body["edges"] if e["relation"] == "contradicts"]
    assert contradicts and contradicts[0]["source_id"] == PSAP_LETTER
    flagged = set(body["contradiction_edge_ids"])
    assert contradicts[0]["id"] in flagged
    risk = [e for e in body["edges"] if e["relation"] == "risk_factor_for" and e["contradicted_by"]]
    assert risk and risk[0]["id"] in flagged


def test_contradicting_edge_is_pulled_onto_a_gene_map(api: TestClient) -> None:
    body = _map(api, center=PSAP)
    assert PSAP_LETTER in _ids(body), "the contradicting publication must be surfaced"
    assert any(e["relation"] == "contradicts" for e in body["edges"])


def test_map_is_deterministic(api: TestClient) -> None:
    assert _map(api, center=LATE_PD, depth=2) == _map(api, center=LATE_PD, depth=2)
    assert _map(api) == _map(api)


# ---- overview --------------------------------------------------------------------------------


def test_overview_is_the_curated_slice(api: TestClient) -> None:
    body = _map(api)
    _assert_consistent(body)
    assert body["center"] is None
    assert body["depth"] == 0
    ids = set(_ids(body))
    assert {GBA1, PSAP, LATE_PD, GAUCHER_2, ASPRO_PD} <= ids
    assert 40 <= len(ids) <= 90
    types = _types(body)
    assert "phenotype" not in types and "investigator" not in types
    studies = [i["node"] for i in body["nodes"] if i["node"]["type"] == "study"]
    assert all("asset_slug" in s["attributes"] for s in studies)
    funders = [i["node"]["id"] for i in body["nodes"] if i["node"]["type"] == "funder"]
    assert "org:cure-parkinsons" in funders
    assert not any(f.startswith("funder:reporter-") for f in funders)
    hidden = body["truncated"]["by_type"]
    assert hidden["phenotype"] == 424 and hidden["investigator"] == 124
    assert body["contradiction_edge_ids"]
    assert all(item["distance"] is None for item in body["nodes"])


def test_overview_type_filter(api: TestClient) -> None:
    body = _map(api, types="disease,gene")
    assert _types(body) == {"disease", "gene"}
    assert {e["relation"] for e in body["edges"]} <= {"caused_by", "risk_factor_for"}


# ---- errors ----------------------------------------------------------------------------------


def test_unknown_center_is_404(api: TestClient) -> None:
    response = api.get("/api/v1/graph", params={"center": "MONDO:0000000"})
    assert response.status_code == 404


@pytest.mark.parametrize(
    "params",
    [
        {"depth": 3},
        {"depth": 0},
        {"limit": MAX_NODES + 1},
        {"types": "planet"},
        {"relations": "loves"},
        {"min_confidence": 2},
    ],
)
def test_invalid_params_are_422(api: TestClient, params: dict[str, Any]) -> None:
    assert api.get("/api/v1/graph", params=params).status_code == 422


def test_no_snapshot_is_503(tmp_path: Any) -> None:
    settings = Settings(snapshot_path=tmp_path / "missing.json")
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/graph").status_code == 503
