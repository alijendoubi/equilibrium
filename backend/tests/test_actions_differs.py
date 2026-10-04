"""The action view's 'what differs' text carries the curated dose/population comparison."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from atlas.api.main import create_app
from atlas.graph.actions import key_facts
from atlas.models.evidence import Node, NodeType

ASPRO_PD = "clinicaltrials:NCT05778617"
NARITA = "PMID:27042680"


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def _asset(client: TestClient, disease: str, node_id: str) -> dict[str, object]:
    assets = client.get(f"/api/v1/actions/{disease}").json()["assets"]
    return next(a for a in assets if a["node"]["id"] == node_id)


def test_aspro_pd_differs_compares_dose_with_the_ngd_pilot(client: TestClient) -> None:
    differs = str(_asset(client, "MONDO%3A0009266", ASPRO_PD)["differs"])

    assert "1260 mg/day" in differs
    assert "104 weeks" in differs
    assert "MDS-UPDRS" in differs
    assert "closest clinical evidence is" in differs
    assert "25 mg/kg/day" in differs


def test_own_pilot_is_listed_with_its_facts(client: TestClient) -> None:
    differs = str(_asset(client, "MONDO%3A0009267", NARITA)["differs"])

    assert differs.startswith("Already linked to")
    assert "5 patients" in differs


def test_key_facts_empty_without_curated_fields() -> None:
    node = Node(id="asset:x", type=NodeType.ASSET, label="x")

    assert key_facts(node) == ""


def test_next_experiment_prefers_the_shared_gene(client: TestClient) -> None:
    body = client.get("/api/v1/actions/MONDO%3A0008199").json()

    assert "GBA1" in body["next_experiment"]["text"]
