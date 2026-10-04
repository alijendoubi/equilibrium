"""NIH RePORTER connector: fetch (recorded fixture, no network), collect, normalize, bridges."""

import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from atlas.api.main import create_app
from atlas.config import Settings
from atlas.graph.investigators import bridges, shared_investigators
from atlas.graph.store import GraphStore
from atlas.ingest import refresh, reporter
from atlas.ingest.common import cache_path, read_cache
from atlas.models.evidence import EvidenceType, Node, NodeType, Relation
from atlas.trust.rubric import score
from tests._ingest_helpers import assert_provenance, assert_sorted_unique, fake_client, load_fixture

GBA1 = "HGNC:4177"
LATE_PD = "MONDO:0008199"
GAUCHER = "MONDO:0018150"
SAPOSIN_C = "MONDO:0012517"
MAX_CACHE_BYTES = 1_500_000


def _handler(requests: list[dict[str, Any]]) -> Any:
    recorded = load_fixture("reporter_search")
    by_text = {text: name for name, text, _ in reporter.QUERIES}

    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        name = by_text[body["criteria"]["advanced_text_search"]["search_text"]]
        page = recorded.get(name, {"meta": {"total": 0}, "results": []})
        return httpx.Response(200, json=page)

    return handle


@pytest.fixture(scope="module")
def payload() -> dict[str, Any]:
    requests: list[dict[str, Any]] = []
    with fake_client(_handler(requests)) as client:
        data = reporter.fetch(client)
    assert len(requests) == len(reporter.QUERIES)
    assert all(r["criteria"]["fiscal_years"] == list(reporter.FISCAL_YEARS) for r in requests)
    data["meta"]["retrieved_at"] = "2026-10-04T11:00:00Z"
    return data


def test_fetch_posts_one_search_per_query_and_dedupes_projects(payload: dict[str, Any]) -> None:
    assert payload["query_totals"]["saposin_c_deficiency"] == 0
    assert payload["query_totals"]["gba_parkinson"] == 22
    projects = payload["projects"]
    # R21NS146759 was returned by both queries: one record, both queries kept
    shared = projects["R21NS146759"]
    assert shared["matched_queries"] == ["gaucher", "gba_parkinson"]
    assert len(projects) == 7
    assert list(projects) == sorted(projects)


def test_search_pages_until_total() -> None:
    calls: list[int] = []

    def handle(request: httpx.Request) -> httpx.Response:
        offset = json.loads(request.content)["offset"]
        calls.append(offset)
        size = reporter.PAGE_SIZE if offset == 0 else 3
        results = [{"appl_id": offset + i} for i in range(size)]
        return httpx.Response(200, json={"meta": {"total": 103}, "results": results})

    with fake_client(handle) as client:
        found, total = reporter.search(client, "x")
    assert calls == [0, reporter.PAGE_SIZE]
    assert (len(found), total) == (103, 103)


def test_collect_keeps_latest_year_and_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    def raw(appl: int, year: int, core: str) -> dict[str, Any]:
        return {
            "appl_id": appl,
            "project_num": f"5{core}-0{year % 10}",
            "core_project_num": core,
            "fiscal_year": year,
            "principal_investigators": [{"profile_id": 1, "full_name": "A"}],
        }

    collected = reporter.collect({"gba1": [raw(1, 2020, "R01X"), raw(2, 2024, "R01X")]})
    assert collected["R01X"]["appl_id"] == 2
    monkeypatch.setattr(reporter, "MAX_PROJECTS", 1)
    capped = reporter.collect(
        {"gba1": [raw(1, 2020, "R01A"), raw(2, 2020, "R01B")], "gaucher": [raw(3, 2025, "R01A")]}
    )
    assert list(capped) == ["R01A"]
    assert capped["R01A"]["matched_queries"] == ["gaucher", "gba1"]
    assert capped["R01A"]["appl_id"] == 3
    assert reporter.collect({"gba1": [{"appl_id": None}]}) == {}


def test_normalize_investigators_funders_and_edges(payload: dict[str, Any]) -> None:
    result = reporter.normalize(payload)
    assert_sorted_unique(result.nodes, result.edges)
    assert_provenance(result.edges, "ingest:reporter")
    nodes = {n.id: n for n in result.nodes}
    ho = next(n for n in nodes.values() if n.label == "Gary P. H. Ho")
    assert ho.type is NodeType.INVESTIGATOR
    assert ho.id.startswith("investigator:")
    assert ho.attributes["organization"]
    ho_edges = [
        e for e in result.edges if e.source_id == ho.id and e.relation is Relation.INVESTIGATES
    ]
    assert {e.target_id for e in ho_edges} == {GBA1, LATE_PD, GAUCHER}
    for edge in ho_edges:
        assert edge.evidence_type is EvidenceType.OBSERVED
        assert str(edge.provenance.url).startswith("https://reporter.nih.gov/project-details/")
        assert edge.provenance.source_record_id == "1R21NS146759-01A1"
        assert score(edge)[0] == 0.75
    funders = [n for n in result.nodes if n.type is NodeType.FUNDER]
    assert funders and all(n.id.startswith("funder:reporter-") for n in funders)
    assert any(e.relation is Relation.FUNDS and e.target_id == ho.id for e in result.edges)
    assert result.notes["projects_by_target"][LATE_PD] == 4
    assert result.notes["query_totals"]["saposin_c_deficiency"] == 0


def test_normalize_drops_targets_missing_from_the_graph(payload: dict[str, Any]) -> None:
    result = reporter.normalize(payload, known_nodes=[GBA1])
    targets = {e.target_id for e in result.edges if e.relation is Relation.INVESTIGATES}
    assert targets == {GBA1}
    assert result.notes["targets_not_in_graph"] == [LATE_PD, GAUCHER]


def test_bridges_from_fixture(payload: dict[str, Any]) -> None:
    result = reporter.normalize(payload)
    targets = [
        Node(id=GBA1, type=NodeType.GENE, label="GBA1"),
        Node(id=LATE_PD, type=NodeType.DISEASE, label="late-onset Parkinson disease"),
        Node(id=GAUCHER, type=NodeType.DISEASE, label="Gaucher disease"),
    ]
    store = GraphStore((*result.nodes, *targets), result.edges)
    found = bridges(store)
    labels = [b.node.label for b in found]
    assert labels[0] == "Gary P. H. Ho"
    assert "Juan Marugan" in labels
    assert all(len(b.communities) >= 2 for b in found)
    assert all(b.edge_ids for b in found)
    assert "Parkinson disease" in found[0].why
    # only investigators without a PD link are not bridges
    assert not any(b.node.label == "Matthew J LaVoie" for b in found)
    assert shared_investigators(store, LATE_PD)
    assert shared_investigators(store, "MONDO:0000001") == ()


def test_refresh_knows_the_source() -> None:
    assert "reporter" in refresh.SOURCES
    assert refresh._interval("reporter") == reporter.MIN_INTERVAL_S


# ---- committed cache and snapshot ---------------------------------------------------------------


def test_committed_cache_is_small_and_has_the_honest_gap() -> None:
    cached = read_cache("reporter", "payload")
    assert 50 <= len(cached["projects"]) <= reporter.MAX_PROJECTS
    assert cached["query_totals"]["saposin_c_deficiency"] == 0
    assert cache_path("reporter", "payload").stat().st_size < MAX_CACHE_BYTES


@pytest.fixture(scope="module")
def api() -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as client:
        yield client


def test_actions_list_shared_investigators(api: TestClient) -> None:
    body = api.get("/api/v1/actions/MONDO:0009266").json()
    shared = body["shared_investigators"]
    assert shared
    for item in shared:
        assert set(item) == {"node", "communities", "target_ids", "why", "edge_ids"}
        assert item["node"]["type"] == "investigator"
        assert len(item["communities"]) >= 2
        for edge_id in item["edge_ids"]:
            assert api.get(f"/api/v1/edges/{edge_id}").status_code == 200
    assert any(set(i["communities"]) >= {"Gaucher disease", "Parkinson disease"} for i in shared)


def test_saposin_c_stays_an_honest_gap_with_zero_reporter_projects(api: TestClient) -> None:
    report = api.get(f"/api/v1/coverage/{SAPOSIN_C}").json()
    assert report["result"] == "no_supported_route"
    rows = {row["source"]: row for row in report["searched"]}
    assert rows["reporter"]["records_found"] == 0
    assert any("RePORTER" in m for m in report["missing_evidence"])
    actions = api.get(f"/api/v1/actions/{SAPOSIN_C}").json()
    assert actions["partners"] == []
