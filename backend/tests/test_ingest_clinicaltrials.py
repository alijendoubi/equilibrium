"""ClinicalTrials.gov connector: condition mapping, study nodes, fetch paging."""

from typing import Any

import httpx

from atlas.ingest import clinicaltrials, curated, monarch
from atlas.models.evidence import Node, NodeType, Relation
from tests._ingest_helpers import (
    assert_provenance,
    assert_sorted_unique,
    assert_valid_ids,
    fake_client,
    load_fixture,
)


def _diseases() -> tuple[Node, ...]:
    return tuple(
        n for n in monarch.normalize(load_fixture("monarch")).nodes if n.type.value == "disease"
    )


def _result() -> clinicaltrials.IngestResult:
    aliases = curated.condition_aliases(curated.load_all())
    return clinicaltrials.normalize(load_fixture("clinicaltrials"), _diseases(), aliases)


def test_normalize_name_handles_punctuation_possessive_and_roman_numerals() -> None:
    assert clinicaltrials.normalize_name("Gaucher's Disease Type III") == "gaucher disease type 3"
    assert clinicaltrials.normalize_name("Gaucher Disease, Type 3") == "gaucher disease type 3"
    assert clinicaltrials.normalize_name("Parkinson's Disease") == "parkinson disease"


def test_normalize_builds_study_nodes_and_condition_edges() -> None:
    result = _result()
    assert_valid_ids(result.nodes)
    assert_provenance(result.edges, "ingest:clinicaltrials")
    assert_sorted_unique(result.nodes, result.edges)
    nodes = {node.id: node for node in result.nodes}
    aspro = nodes["clinicaltrials:NCT05778617"]
    assert aspro.type is NodeType.STUDY
    assert aspro.attributes["phase"] == "3"
    assert aspro.attributes["status"] == "RECRUITING"
    assert "ASPro-PD" in aspro.synonyms
    assert all(e.relation is Relation.STUDIES_CONDITION for e in result.edges)
    assert all(e.evidence_type.value == "observed" for e in result.edges)


def test_registry_conditions_map_by_synonym_and_alias() -> None:
    edges = {(e.source_id, e.target_id): e for e in _result().edges}
    pd = edges[("clinicaltrials:NCT05778617", "MONDO:0008199")]
    assert pd.qualifiers["condition_match"] == "alias"
    assert pd.confidence == clinicaltrials.CONFIDENCE_ALIAS
    gd2 = edges[("clinicaltrials:NCT04411654", "MONDO:0009266")]
    assert gd2.qualifiers["condition_match"] in {"label", "synonym"}
    assert gd2.confidence == clinicaltrials.CONFIDENCE_RECORD
    assert str(gd2.provenance.url) == "https://clinicaltrials.gov/study/NCT04411654"


def test_unmapped_conditions_are_reported_not_guessed() -> None:
    result = _result()
    assert "NCT00029965" in result.notes["dropped_studies_without_slice_condition"]
    assert result.notes["unmapped_conditions"]["Myoclonus"] == 1
    assert "clinicaltrials:NCT00029965" not in {n.id for n in result.nodes}


def test_seed_trials_are_kept_even_without_mapped_condition() -> None:
    payload = load_fixture("clinicaltrials")
    study = dict(payload["studies"]["NCT05222906"])
    study["conditions"] = ["Something unmapped"]
    payload["studies"] = {"NCT05222906": study}
    result = clinicaltrials.normalize(payload, _diseases(), [])
    assert [n.id for n in result.nodes] == ["clinicaltrials:NCT05222906"]
    assert result.edges == ()


def test_ambiguous_synonyms_are_dropped() -> None:
    a = Node(id="MONDO:0009266", type=NodeType.DISEASE, label="A", synonyms=("shared",))
    b = Node(id="MONDO:0009267", type=NodeType.DISEASE, label="B", synonyms=("shared",))
    index = clinicaltrials.build_condition_index([a, b], [])
    assert "shared" not in index
    assert index["a"] == ("MONDO:0009266", "label")


def test_fetch_runs_bounded_queries_and_seed_lookups() -> None:
    fixture = load_fixture("clinicaltrials")
    raw: dict[str, Any] = {
        "protocolSection": {
            "identificationModule": {"nctId": "NCT05778617", "briefTitle": "Ambroxol"},
            "statusModule": {"overallStatus": "RECRUITING"},
            "designModule": {"phases": ["PHASE3"], "enrollmentInfo": {"count": 330}},
            "conditionsModule": {"conditions": ["Parkinson Disease"]},
            "armsInterventionsModule": {"interventions": [{"type": "DRUG", "name": "Ambroxol"}]},
        },
        "hasResults": False,
    }
    pages = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/version"):
            return httpx.Response(200, json={"dataTimestamp": "2026-10-02T09:00:04"})
        if path.endswith("/studies"):
            pages["n"] += 1
            if request.url.params.get("query.intr") == "ambroxol" and "pageToken" not in str(
                request.url
            ):
                return httpx.Response(200, json={"studies": [raw], "nextPageToken": "t2"})
            return httpx.Response(200, json={"studies": []})
        nct = path.rsplit("/", 1)[1]
        study = {**raw, "protocolSection": {"identificationModule": {"nctId": nct}}}
        return httpx.Response(200, json=study)

    with fake_client(handler) as client:
        payload = clinicaltrials.fetch(client)
    assert payload["meta"]["source_version"] == "ctgov data 2026-10-02T09:00:04"
    assert set(clinicaltrials.SEED_TRIALS) <= set(payload["studies"])
    aspro = payload["studies"]["NCT05778617"]
    assert aspro["matched_queries"] == ["ambroxol", "seed"]
    assert aspro["phases"] == ["PHASE3"]
    assert payload["query_counts"]["ambroxol"] == 1
    assert fixture["studies"]  # fixture shape matches the trimmed payload
    assert set(aspro) >= set(fixture["studies"]["NCT05778617"]) - {"brief_summary"}
