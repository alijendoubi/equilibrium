"""Validation and immutability of the evidence model.

Fixtures use the demo cluster: Gaucher disease (MONDO:0018150) is caused by GBA1 (HGNC:4177),
and GBA1 is a risk factor for Parkinson disease (MONDO:0005180). IDs verified against HGNC and
MONDO (OLS) on 2026-10-03. Record ids below are illustrative, not cited evidence.
"""

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from atlas.models import (
    Edge,
    EvidenceType,
    FrozenStrMap,
    Node,
    NodeType,
    Provenance,
    Relation,
    compute_edge_id,
)

RETRIEVED_AT = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
GBA1 = "HGNC:4177"
GAUCHER = "MONDO:0018150"
PARKINSON = "MONDO:0005180"
SUPPORT_A = "E:0123456789abcdef"
SUPPORT_B = "E:fedcba9876543210"


def make_provenance(**overrides: Any) -> Provenance:
    data: dict[str, Any] = {
        "source": "omim",
        "source_record_id": "230800",
        "url": "https://omim.org/entry/230800",
        "retrieved_at": RETRIEVED_AT,
    }
    return Provenance.model_validate({**data, **overrides})


def make_edge(**overrides: Any) -> Edge:
    data: dict[str, Any] = {
        "source_id": GAUCHER,
        "target_id": GBA1,
        "relation": "caused_by",
        "provenance": make_provenance(),
        "confidence": 0.9,
        "evidence_type": "curated",
    }
    return Edge.model_validate({**data, **overrides})


def make_inferred_edge(**provenance_overrides: Any) -> Edge:
    provenance = make_provenance(
        source="analytics",
        source_record_id="mechanism-similarity:r1",
        url=None,
        **provenance_overrides,
    )
    return make_edge(
        source_id=GAUCHER,
        target_id=PARKINSON,
        relation="shares_mechanism_with",
        provenance=provenance,
        confidence=0.4,
        evidence_type="inferred",
    )


# --- vocabularies -------------------------------------------------------------------------


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


def test_relation_vocabulary_includes_required_relations() -> None:
    required = {
        "caused_by",
        "risk_factor_for",
        "has_phenotype",
        "participates_in",
        "studies_condition",
        "represents",
        "investigates",
        "funds",
        "similar_phenotype_to",
        "shares_mechanism_with",
        "contradicts",
    }
    assert required <= {r.value for r in Relation}


@pytest.mark.parametrize("relation", ["gene_associated_with_disease", "", "CAUSED_BY", "causes"])
def test_edge_rejects_unknown_relation(relation: str) -> None:
    with pytest.raises(ValidationError):
        make_edge(relation=relation)


def test_edge_accepts_relation_enum_and_string() -> None:
    assert make_edge(relation=Relation.RISK_FACTOR_FOR).relation is Relation.RISK_FACTOR_FOR
    assert make_edge(relation="has_phenotype").relation is Relation.HAS_PHENOTYPE


# --- nodes --------------------------------------------------------------------------------


def test_valid_node_with_xrefs_and_attributes() -> None:
    node = Node(
        id=GBA1,
        type=NodeType.GENE,
        label="GBA1",
        synonyms=("GBA", "glucosylceramidase beta 1"),
        xrefs=("NCBIGene:2629", "OMIM:606463"),
        attributes=FrozenStrMap({"locus": "1q22"}),
    )

    assert node.type is NodeType.GENE
    assert node.xrefs == ("NCBIGene:2629", "OMIM:606463")
    assert node.attributes["locus"] == "1q22"


def test_node_defaults_to_empty_collections() -> None:
    node = Node(id="HP:0001744", type=NodeType.PHENOTYPE, label="Splenomegaly")

    assert node.synonyms == ()
    assert node.xrefs == ()
    assert dict(node.attributes) == {}


@pytest.mark.parametrize("bad_id", ["", "MONDO", "MONDO 0018150", ":123", "MONDO:"])
def test_node_rejects_non_curie_ids(bad_id: str) -> None:
    with pytest.raises(ValidationError):
        Node(id=bad_id, type=NodeType.DISEASE, label="x")


@pytest.mark.parametrize("bad_xref", ["2629", "OMIM 606463", " "])
def test_node_rejects_non_curie_xrefs(bad_xref: str) -> None:
    with pytest.raises(ValidationError):
        Node.model_validate({"id": GBA1, "type": "gene", "label": "GBA1", "xrefs": [bad_xref]})


def test_node_rejects_unknown_type_and_blank_label() -> None:
    with pytest.raises(ValidationError):
        Node.model_validate({"id": "X:1", "type": "planet", "label": "x"})
    with pytest.raises(ValidationError):
        Node(id="X:1", type=NodeType.GENE, label="   ")


def test_node_attributes_reject_blank_keys_and_non_string_values() -> None:
    with pytest.raises(ValidationError):
        Node.model_validate({"id": GBA1, "type": "gene", "label": "x", "attributes": {" ": "v"}})
    with pytest.raises(ValidationError):
        Node.model_validate({"id": GBA1, "type": "gene", "label": "x", "attributes": {"k": 1}})


# --- immutability -------------------------------------------------------------------------


def test_models_are_frozen() -> None:
    node = Node(id=GBA1, type=NodeType.GENE, label="GBA1")
    edge = make_edge()

    with pytest.raises(ValidationError):
        node.label = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        edge.confidence = 0.1  # type: ignore[misc]


def test_qualifiers_and_attributes_are_immutable() -> None:
    source = {"zygosity": "heterozygous"}
    edge = make_edge(
        source_id=GBA1,
        target_id=PARKINSON,
        relation="risk_factor_for",
        qualifiers=source,
    )
    node = Node.model_validate(
        {"id": GBA1, "type": "gene", "label": "GBA1", "attributes": {"locus": "1q22"}}
    )

    source["zygosity"] = "homozygous"
    assert edge.qualifiers["zygosity"] == "heterozygous"
    with pytest.raises(TypeError):
        edge.qualifiers["zygosity"] = "homozygous"  # type: ignore[index]
    with pytest.raises(TypeError):
        node.attributes["locus"] = "x"  # type: ignore[index]
    assert not hasattr(edge.qualifiers, "update")


def test_frozen_models_with_mappings_are_hashable_and_comparable() -> None:
    first = make_edge(qualifiers={"zygosity": "biallelic", "inheritance": "AR"})
    second = make_edge(qualifiers={"inheritance": "AR", "zygosity": "biallelic"})

    assert first == second
    assert hash(first) == hash(second)
    assert len({first, second}) == 1
    assert len(first.qualifiers) == 2
    assert repr(first.qualifiers).startswith("FrozenStrMap(")


def test_extra_fields_are_forbidden() -> None:
    with pytest.raises(ValidationError):
        Node.model_validate({"id": "X:1", "type": "gene", "label": "x", "extra": 1})
    with pytest.raises(ValidationError):
        make_provenance(model="gpt")


# --- edge id ------------------------------------------------------------------------------


def test_edge_id_is_deterministic() -> None:
    first = make_edge()
    second = make_edge(confidence=0.5, confidence_reasons=("curated KB 0.90",))

    assert first.id == second.id
    assert first.id.startswith("E:")
    assert len(first.id) == len("E:") + 16
    assert first.id == compute_edge_id(GAUCHER, "caused_by", GBA1, "omim", "230800")


@pytest.mark.parametrize(
    "overrides",
    [
        {"source_id": "MONDO:0009265"},
        {"target_id": "HGNC:0000001"},
        {"relation": "has_phenotype", "target_id": "HP:0001744"},
        {"provenance": make_provenance(source="orphanet")},
        {"provenance": make_provenance(source_record_id="230900")},
    ],
)
def test_edge_id_changes_with_identity_fields(overrides: dict[str, Any]) -> None:
    assert make_edge(**overrides).id != make_edge().id


def test_edge_id_is_unambiguous_across_field_boundaries() -> None:
    assert compute_edge_id("A:1", "caused_by", "B:2", "x|y", "z") != compute_edge_id(
        "A:1", "caused_by", "B:2", "x", "y|z"
    )


def test_edge_id_round_trips_through_serialization() -> None:
    edge = make_edge(qualifiers={"zygosity": "biallelic"})
    dumped = edge.model_dump(mode="json")

    assert dumped["id"] == edge.id
    assert dumped["qualifiers"] == {"zygosity": "biallelic"}
    assert Edge.model_validate(dumped) == edge
    assert Edge.model_validate_json(edge.model_dump_json()) == edge


def test_edge_rejects_tampered_id() -> None:
    dumped = make_edge().model_dump(mode="json")
    dumped["id"] = "E:0000000000000000"

    with pytest.raises(ValidationError, match="does not match"):
        Edge.model_validate(dumped)


# --- provenance and the URL rule ----------------------------------------------------------


def test_valid_edge_with_v2_fields() -> None:
    edge = make_edge(
        source_id=GBA1,
        target_id=PARKINSON,
        relation="risk_factor_for",
        provenance=make_provenance(
            source="pubmed",
            source_record_id="PMID:00000000",
            url="https://pubmed.ncbi.nlm.nih.gov/00000000/",
            source_version="2026-10",
            evidence_quote="heterozygous GBA1 variants increase Parkinson disease risk",
            extractor="openai:gpt-6.1-sol",
        ),
        confidence=0.5,
        evidence_type="inferred",
        qualifiers={"zygosity": "heterozygous"},
        confidence_reasons=("LLM claim with verbatim quote 0.50",),
        contradicted_by=("PMID:123",),
    )

    assert edge.evidence_type is EvidenceType.INFERRED
    assert edge.provenance.extractor == "openai:gpt-6.1-sol"
    assert edge.provenance.source_version == "2026-10"
    assert edge.contradicted_by == ("PMID:123",)
    assert edge.confidence_reasons == ("LLM claim with verbatim quote 0.50",)


@pytest.mark.parametrize("evidence_type", ["observed", "curated"])
def test_observed_and_curated_edges_require_url(evidence_type: str) -> None:
    with pytest.raises(ValidationError, match=r"provenance\.url"):
        make_edge(provenance=make_provenance(url=None), evidence_type=evidence_type)


def test_observed_and_curated_edges_need_url_even_with_supporting_edges() -> None:
    provenance = make_provenance(url=None, supporting_edge_ids=(SUPPORT_A,))

    with pytest.raises(ValidationError, match=r"provenance\.url"):
        make_edge(provenance=provenance, evidence_type="curated")


def test_inferred_edge_without_url_requires_supporting_edges() -> None:
    with pytest.raises(ValidationError, match="supporting_edge_ids"):
        make_inferred_edge()


def test_inferred_edge_without_url_but_with_support_is_valid() -> None:
    edge = make_inferred_edge(supporting_edge_ids=(SUPPORT_A, SUPPORT_B))

    assert edge.provenance.url is None
    assert edge.provenance.supporting_edge_ids == (SUPPORT_A, SUPPORT_B)


def test_inferred_edge_with_url_needs_no_support() -> None:
    assert make_edge(evidence_type="inferred").provenance.supporting_edge_ids == ()


def test_edge_cannot_support_itself() -> None:
    own_id = make_inferred_edge(supporting_edge_ids=(SUPPORT_A,)).id

    with pytest.raises(ValidationError, match="itself"):
        make_inferred_edge(supporting_edge_ids=(own_id,))


@pytest.mark.parametrize("bad_id", ["PMID:123", "E:XYZ", "E:0123", "e_0123456789ab"])
def test_supporting_edge_ids_must_be_edge_ids(bad_id: str) -> None:
    with pytest.raises(ValidationError):
        make_provenance(supporting_edge_ids=(bad_id,))


@pytest.mark.parametrize("evidence_type", ["observed", "curated"])
def test_llm_extracted_edges_must_be_inferred(evidence_type: str) -> None:
    provenance = make_provenance(extractor="openai:gpt-6.1-sol")

    with pytest.raises(ValidationError, match="inferred"):
        make_edge(provenance=provenance, evidence_type=evidence_type)


def test_curated_extractor_may_be_curated() -> None:
    edge = make_edge(provenance=make_provenance(extractor="curated:team"))

    assert edge.provenance.extractor == "curated:team"


@pytest.mark.parametrize("extractor", ["gpt-6.1-sol", "OpenAI:gpt", "openai:", " "])
def test_extractor_format_is_validated(extractor: str) -> None:
    with pytest.raises(ValidationError):
        make_provenance(extractor=extractor)


def test_provenance_optional_text_fields_reject_blank() -> None:
    with pytest.raises(ValidationError):
        make_provenance(evidence_quote="  ")
    with pytest.raises(ValidationError):
        make_provenance(source_version="")


def test_provenance_url_is_optional_but_validated() -> None:
    assert make_provenance(url=None).url is None
    with pytest.raises(ValidationError):
        make_provenance(url="not a url")
    with pytest.raises(ValidationError):
        make_provenance(source="")


# --- edge field validation ----------------------------------------------------------------


@pytest.mark.parametrize("confidence", [0.0, 1.0, 0.5])
def test_edge_accepts_confidence_bounds(confidence: float) -> None:
    assert make_edge(confidence=confidence).confidence == confidence


@pytest.mark.parametrize("confidence", [-0.01, 1.01, 2, float("nan"), float("inf")])
def test_edge_rejects_confidence_out_of_range(confidence: float) -> None:
    with pytest.raises(ValidationError):
        make_edge(confidence=confidence)


def test_edge_rejects_blank_contradiction_reason_and_bad_evidence_type() -> None:
    with pytest.raises(ValidationError):
        make_edge(contradicted_by=("PMID:1", " "))
    with pytest.raises(ValidationError):
        make_edge(confidence_reasons=("curated KB 0.90", "  "))
    with pytest.raises(ValidationError):
        make_edge(evidence_type="rumoured")


def test_edge_rejects_bad_qualifiers() -> None:
    with pytest.raises(ValidationError):
        make_edge(qualifiers={"": "x"})
    with pytest.raises(ValidationError):
        make_edge(qualifiers={"frequency": 0.5})
    with pytest.raises(ValidationError):
        make_edge(qualifiers=["zygosity", "heterozygous"])


def test_edge_requires_provenance() -> None:
    with pytest.raises(ValidationError):
        Edge.model_validate(
            {
                "source_id": GAUCHER,
                "target_id": GBA1,
                "relation": "caused_by",
                "confidence": 0.5,
                "evidence_type": "observed",
            }
        )
