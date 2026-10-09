"""Curated YAML connector: org/asset ids, edges, validation and coverage seeds."""

from pathlib import Path
from typing import Any

import pytest

from atlas.ingest import curated
from atlas.models.evidence import NodeType, Relation
from tests._ingest_helpers import assert_provenance, assert_sorted_unique, assert_valid_ids


def _payload() -> dict[str, Any]:
    return curated.load_all()


def test_normalize_real_curated_files() -> None:
    result = curated.normalize(_payload())
    assert_valid_ids(result.nodes)
    assert_provenance(result.edges, "ingest:curated")
    assert_sorted_unique(result.nodes, result.edges)
    assert all(e.evidence_type.value == "curated" for e in result.edges)
    nodes = {node.id: node for node in result.nodes}
    assert nodes["org:international-gaucher-alliance"].type is NodeType.PATIENT_GROUP
    assert nodes["org:cure-parkinsons"].type is NodeType.FUNDER
    assert nodes["clinicaltrials:NCT05778617"].type is NodeType.STUDY
    assert nodes["clinicaltrials:NCT05778617"].attributes["asset_slug"] == "aspro-pd"
    assert nodes["PMID:27042680"].type is NodeType.PUBLICATION
    assert nodes["asset:biomarker-lyso-gb1"].type is NodeType.ASSET


def test_edges_connect_orgs_assets_and_diseases() -> None:
    edges = curated.normalize(_payload()).edges
    triples = {(e.source_id, e.relation, e.target_id) for e in edges}
    assert ("org:cure-parkinsons", Relation.FUNDS, "clinicaltrials:NCT05778617") in triples
    assert ("org:cure-parkinsons", Relation.REPRESENTS, "MONDO:0008199") in triples
    assert ("clinicaltrials:NCT05778617", Relation.STUDIES_CONDITION, "MONDO:0008199") in triples
    assert ("PMID:27042680", Relation.MENTIONS, "MONDO:0009266") in triples


def test_no_dedicated_org_entries_are_coverage_data_not_edges() -> None:
    result = curated.normalize(_payload())
    gaps = result.notes["no_dedicated_org_found"]
    assert {g["disease_id"] for g in gaps} >= {"MONDO:0012517"}
    assert not any(
        e.relation is Relation.REPRESENTS and e.target_id == "MONDO:0012517" for e in result.edges
    )


def test_org_confidence_depends_on_verification() -> None:
    edges = curated.normalize(_payload()).edges
    by_org = {e.source_id: e.confidence for e in edges if e.relation is Relation.REPRESENTS}
    assert by_org["org:international-gaucher-alliance"] == curated.CONFIDENCE_ORG_READ
    assert by_org["org:national-gaucher-foundation"] == curated.CONFIDENCE_ORG_RESOLVES


def test_entry_without_url_is_rejected() -> None:
    payload = _payload()
    bad = {**payload["assets"]["assets"][0]}
    bad.pop("url")
    payload["assets"] = {"assets": [bad]}
    with pytest.raises(curated.CuratedDataError, match="missing"):
        curated.normalize(payload)


def test_non_http_url_is_rejected() -> None:
    payload = _payload()
    payload["assets"] = {"assets": [{**payload["assets"]["assets"][0], "url": "ftp://x"}]}
    with pytest.raises(curated.CuratedDataError, match="http"):
        curated.normalize(payload)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("disease_ids", [], "non-empty disease_ids"),
        ("retrieved", "not-a-date", "ISO date"),
        ("id", "Not a slug", "kebab-case slug"),
        ("source_record_id", None, "source_record_id"),
    ],
)
def test_asset_schema_fields_are_required_and_valid(
    field: str, value: object, match: str
) -> None:
    payload = _payload()
    asset = {**payload["assets"]["assets"][0], field: value}
    payload["assets"] = {"assets": [asset]}
    with pytest.raises(curated.CuratedDataError, match=match):
        curated.normalize(payload)


def test_duplicate_asset_ids_are_rejected() -> None:
    payload = _payload()
    first = payload["assets"]["assets"][0]
    payload["assets"] = {"assets": [first, {**first, "name": "Duplicate"}]}
    with pytest.raises(curated.CuratedDataError, match="duplicate asset ids"):
        curated.normalize(payload)


def test_unknown_funded_asset_is_rejected() -> None:
    payload = _payload()
    org = {**payload["organizations"]["organizations"][0], "funds": ["nope"]}
    payload["organizations"] = {"organizations": [org]}
    with pytest.raises(curated.CuratedDataError, match="unknown"):
        curated.normalize(payload)


def test_bad_mechanism_and_alias_are_rejected() -> None:
    payload = _payload()
    mech = {**payload["mechanisms"]["mechanisms"][0], "id": "MONDO:0000001"}
    with pytest.raises(curated.CuratedDataError, match="GO id"):
        curated.mechanisms({"mechanisms": {"mechanisms": [mech]}})
    with pytest.raises(curated.CuratedDataError, match="alias"):
        curated.condition_aliases({"condition_aliases": {"aliases": [{"name": "x"}]}})


def test_invalid_coverage_gap_is_rejected() -> None:
    payload = _payload()
    gap = {**payload["organizations"]["no_dedicated_org_found"][0], "searched": []}
    payload["organizations"] = {
        **payload["organizations"],
        "no_dedicated_org_found": [gap],
    }
    with pytest.raises(curated.CuratedDataError, match="non-empty searched"):
        curated.normalize(payload)


def test_load_yaml_rejects_non_mapping(tmp_path: Path) -> None:
    (tmp_path / "organizations.yaml").write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(curated.CuratedDataError, match="mapping"):
        curated.load_yaml("organizations", tmp_path)


def test_mechanism_whitelist_ids_are_go_terms() -> None:
    items = curated.mechanisms(_payload())
    assert {"GO:0006680", "GO:0007040"} <= {str(m["id"]) for m in items}
