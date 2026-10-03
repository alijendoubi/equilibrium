"""Validation and immutability of the draft evidence model."""

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from atlas.models import Edge, EvidenceType, Node, NodeType, Provenance

RETRIEVED_AT = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


def make_provenance(**overrides: Any) -> Provenance:
    data: dict[str, Any] = {
        "source": "clinvar",
        "source_record_id": "VCV000012345",
        "url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/12345/",
        "retrieved_at": RETRIEVED_AT,
    }
    return Provenance.model_validate({**data, **overrides})


def make_edge(**overrides: Any) -> Edge:
    data: dict[str, Any] = {
        "source_id": "HGNC:1100",
        "target_id": "MONDO:0007739",
        "relation": "gene_associated_with_disease",
        "provenance": make_provenance(),
        "confidence": 0.9,
        "evidence_type": "curated",
    }
    return Edge.model_validate({**data, **overrides})


def test_node_types_cover_planned_entities() -> None:
    assert {t.value for t in NodeType} == {
        "disease",
        "gene",
        "variant",
        "mechanism",
        "phenotype",
        "patient_group",
        "publication",
        "study",
        "asset",
        "investigator",
        "funder",
    }
    assert {t.value for t in EvidenceType} == {"observed", "inferred", "curated"}


def test_valid_node() -> None:
    node = Node(
        id="MONDO:0007739",
        type=NodeType.DISEASE,
        label="Huntington disease",
        synonyms=("HD", "Huntington chorea"),
    )

    assert node.type is NodeType.DISEASE
    assert node.synonyms == ("HD", "Huntington chorea")


def test_node_synonyms_default_to_empty_tuple() -> None:
    assert Node(id="HP:0002072", type=NodeType.PHENOTYPE, label="Chorea").synonyms == ()


@pytest.mark.parametrize("bad_id", ["", "MONDO", "MONDO 0007739", ":123", "MONDO:"])
def test_node_rejects_non_curie_ids(bad_id: str) -> None:
    with pytest.raises(ValidationError):
        Node(id=bad_id, type=NodeType.DISEASE, label="x")


def test_node_rejects_unknown_type_and_blank_label() -> None:
    with pytest.raises(ValidationError):
        Node.model_validate({"id": "X:1", "type": "planet", "label": "x"})
    with pytest.raises(ValidationError):
        Node(id="X:1", type=NodeType.GENE, label="   ")


def test_models_are_frozen() -> None:
    node = Node(id="HGNC:4851", type=NodeType.GENE, label="HTT")
    edge = make_edge()

    with pytest.raises(ValidationError):
        node.label = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        edge.confidence = 0.1  # type: ignore[misc]


def test_extra_fields_are_forbidden() -> None:
    with pytest.raises(ValidationError):
        Node.model_validate({"id": "X:1", "type": "gene", "label": "x", "extra": 1})


def test_valid_edge() -> None:
    edge = make_edge(contradicted_by=("PMID:123",))

    assert edge.evidence_type is EvidenceType.CURATED
    assert edge.provenance.source == "clinvar"
    assert edge.contradicted_by == ("PMID:123",)


@pytest.mark.parametrize("confidence", [0.0, 1.0, 0.5])
def test_edge_accepts_confidence_bounds(confidence: float) -> None:
    assert make_edge(confidence=confidence).confidence == confidence


@pytest.mark.parametrize("confidence", [-0.01, 1.01, 2, float("nan"), float("inf")])
def test_edge_rejects_confidence_out_of_range(confidence: float) -> None:
    with pytest.raises(ValidationError):
        make_edge(confidence=confidence)


def test_edge_rejects_blank_contradiction_and_bad_evidence_type() -> None:
    with pytest.raises(ValidationError):
        make_edge(contradicted_by=("PMID:1", " "))
    with pytest.raises(ValidationError):
        make_edge(evidence_type="rumoured")


def test_edge_requires_provenance() -> None:
    with pytest.raises(ValidationError):
        Edge.model_validate(
            {
                "source_id": "HGNC:1100",
                "target_id": "MONDO:0007739",
                "relation": "r",
                "confidence": 0.5,
                "evidence_type": "observed",
            }
        )


def test_provenance_url_is_optional_but_validated() -> None:
    assert make_provenance(url=None).url is None
    with pytest.raises(ValidationError):
        make_provenance(url="not a url")
    with pytest.raises(ValidationError):
        make_provenance(source="")
