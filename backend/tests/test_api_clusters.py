"""Cluster API against the real committed snapshot (issue #20).

Where the seed diseases land is asserted as the data has it today, not as we hoped: the gene
signal dominates, so saposin C deficiency groups with the other PSAP diseases (with a bridge
to Gaucher type I), and late-onset PD groups with the GBA1 Gaucher types via GBA1 risk.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from atlas.api.main import create_app
from atlas.config import Settings

GAUCHER_TYPES = ("MONDO:0009265", "MONDO:0009266", "MONDO:0009267")
LATE_PD = "MONDO:0008199"
SAPOSIN_C = "MONDO:0012517"
GBA1 = "HGNC:4177"

SUMMARY_KEYS = {"id", "label", "size", "member_ids"}
DETAIL_KEYS = {
    "id",
    "label",
    "size",
    "member_ids",
    "nodes",
    "features",
    "edges",
    "bridges",
    "counterexamples",
}
EDGE_KEYS = {
    "source_id",
    "target_id",
    "kind",
    "score",
    "phenotype_score",
    "gene_score",
    "mechanism_score",
    "reasons",
}


@pytest.fixture(scope="module")
def api() -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as test_client:
        yield test_client


def _get(api: TestClient, url: str) -> Any:
    response = api.get(url)
    assert response.status_code == 200, response.text
    return response.json()


def _cluster_of(api: TestClient, node_id: str) -> str:
    cluster_id = _get(api, f"/api/v1/nodes/{node_id}")["cluster_id"]
    assert isinstance(cluster_id, str)
    return cluster_id


def test_list_clusters_partitions_every_disease(api: TestClient) -> None:
    body = _get(api, "/api/v1/clusters")
    assert set(body) == {"clusters", "method"}
    assert body["method"]["seed"] == 42
    ids = [c["id"] for c in body["clusters"]]
    assert ids == [f"C{i}" for i in range(1, len(ids) + 1)]
    members = [m for c in body["clusters"] for m in c["member_ids"]]
    assert len(members) == len(set(members))
    for cluster in body["clusters"]:
        assert set(cluster) == SUMMARY_KEYS
        assert cluster["size"] == len(cluster["member_ids"])
    diseases = _get(api, "/api/v1/search?q=disease&types=disease&limit=50")["results"]
    assert {r["node"]["id"] for r in diseases} <= set(members)


def test_gaucher_types_and_late_pd_share_the_gba1_cluster(api: TestClient) -> None:
    cluster_id = _cluster_of(api, GAUCHER_TYPES[0])
    assert {_cluster_of(api, d) for d in GAUCHER_TYPES} == {cluster_id}
    assert _cluster_of(api, LATE_PD) == cluster_id
    detail = _get(api, f"/api/v1/clusters/{cluster_id}")
    assert detail["label"].startswith("GBA1")
    assert detail["features"]["genes"][0]["node"]["id"] == GBA1
    assert any(
        f["node"]["label"] == "glucosylceramide catabolic process"
        for f in detail["features"]["mechanisms"]
    )
    assert detail["features"]["phenotypes"], "expected informative shared phenotypes"
    assert all(f["ic"] >= 2.5 for f in detail["features"]["phenotypes"])


def test_saposin_c_groups_with_psap_and_bridges_to_gaucher(api: TestClient) -> None:
    cluster_id = _cluster_of(api, SAPOSIN_C)
    assert cluster_id != _cluster_of(api, GAUCHER_TYPES[0])
    detail = _get(api, f"/api/v1/clusters/{cluster_id}")
    assert detail["label"].startswith("PSAP")
    bridge = next(b for b in detail["bridges"] if b["other_id"] == GAUCHER_TYPES[0])
    assert bridge["member_id"] == SAPOSIN_C
    assert any("phenotype similarity" in r for r in bridge["reasons"])


def test_detail_shape_edges_and_counterexamples(api: TestClient) -> None:
    detail = _get(api, f"/api/v1/clusters/{_cluster_of(api, LATE_PD)}")
    assert set(detail) == DETAIL_KEYS
    assert set(detail["features"]) == {"genes", "mechanisms", "phenotypes"}
    node_ids = {n["node"]["id"] for n in detail["nodes"]}
    assert set(detail["member_ids"]) <= node_ids
    for edge in detail["edges"]:
        assert set(edge) == EDGE_KEYS
        assert edge["source_id"] in node_ids and edge["target_id"] in node_ids
        assert edge["reasons"]
    assert {e["kind"] for e in detail["edges"]} == {"within", "bridge"}
    genes = {c["gene"]["label"] for c in detail["counterexamples"]}
    assert "SCARB2" in genes  # Gaucher type I (risk) vs AMRF / ULS in another cluster
    for item in detail["counterexamples"]:
        assert item["other_id"] not in detail["member_ids"]
        assert item["other_cluster_id"] != detail["id"]


@pytest.mark.parametrize("cluster_id", ["C999", "nope", "%20"])
def test_unknown_cluster_404(api: TestClient, cluster_id: str) -> None:
    assert api.get(f"/api/v1/clusters/{cluster_id}").status_code == 404


def test_cluster_id_only_for_diseases(api: TestClient) -> None:
    assert _get(api, f"/api/v1/nodes/{GBA1}")["cluster_id"] is None
    encoded = _get(api, "/api/v1/nodes/MONDO%3A0012517")["cluster_id"]
    assert encoded == _cluster_of(api, SAPOSIN_C)


def test_cluster_responses_are_deterministic(api: TestClient) -> None:
    first = api.get("/api/v1/clusters").content
    detail = api.get("/api/v1/clusters/C1").content
    with TestClient(create_app(Settings())) as fresh:
        assert fresh.get("/api/v1/clusters").content == first
        assert fresh.get("/api/v1/clusters/C1").content == detail
