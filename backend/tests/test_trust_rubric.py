"""Trust rubric trust-v1: table cases, corroboration, contradictions, inferred < curated."""

from datetime import UTC, datetime
from itertools import product

import pytest

from atlas.models.evidence import Edge, EvidenceType, Provenance, Relation
from atlas.trust import rubric
from atlas.trust.rubric import Corroboration, corroboration_index, independent_source, score

AT = datetime(2026, 10, 4, tzinfo=UTC)
URL = "https://example.org/record"


def _edge(
    source: str = "monarch",
    relation: Relation = Relation.CAUSED_BY,
    evidence: EvidenceType = EvidenceType.CURATED,
    qualifiers: dict[str, str] | None = None,
    record: str = "r1",
    extractor: str | None = None,
    contradicted_by: tuple[str, ...] = (),
    confidence: float = 0.5,
    url: str | None = URL,
    supporting: tuple[str, ...] = (),
    ends: tuple[str, str] = ("MONDO:0000001", "HGNC:1"),
) -> Edge:
    return Edge(
        source_id=ends[0],
        target_id=ends[1],
        relation=relation,
        provenance=Provenance(
            source=source,
            source_record_id=record,
            url=url,  # type: ignore[arg-type]
            retrieved_at=AT,
            extractor=extractor,
            supporting_edge_ids=supporting,
        ),
        confidence=confidence,
        evidence_type=evidence,
        contradicted_by=contradicted_by,
        qualifiers=qualifiers or {},  # type: ignore[arg-type]
    )


def _llm(
    certainty: str, relation: Relation = Relation.RISK_FACTOR_FOR, pmid: str = "PMID:1"
) -> Edge:
    return _edge(
        source="pubmed",
        relation=relation,
        evidence=EvidenceType.INFERRED,
        qualifiers={"certainty": certainty, "polarity": "supports"},
        record=pmid,
        extractor="openai:gpt-test",
    )


TABLE = [
    (_edge(qualifiers={"primary_knowledge_source": "infores:omim"}), 0.90, "OMIM via Monarch"),
    (
        _edge(relation=Relation.HAS_PHENOTYPE, ends=("MONDO:0000001", "HP:0000001")),
        0.90,
        "HPO",
    ),
    (_edge(source="go", qualifiers={"evidence_codes": "ECO:0000501,ECO:0000314"}), 0.85, "non-IEA"),
    (_edge(source="go", qualifiers={"evidence_codes": "ECO:0000501"}), 0.80, "IEA"),
    (_edge(source="curated", record="aspro"), 0.80, "team-curated"),
    (_edge(source="clinicaltrials", qualifiers={"condition_match": "label"}), 0.75, "condition"),
    (_edge(source="reporter"), 0.75, "RePORTER"),
    (_edge(source="clinicaltrials", qualifiers={"condition_match": "alias"}), 0.65, "alias"),
    (_edge(source="curated", qualifiers={"verification": "page_read"}), 0.60, "own site"),
    (_edge(source="curated", qualifiers={"verification": "url_resolves"}), 0.50, "resolves"),
    (_edge(source="curated", qualifiers={"verification": "unverified"}), 0.50, "[U]"),
    (_llm("high"), 0.45, "certainty high"),
    (_llm("medium"), 0.35, "certainty medium"),
    (_llm("low"), 0.25, "low"),
    (_llm("high", relation=Relation.MENTIONS), 0.25, "mention"),
]


@pytest.mark.parametrize(("edge", "expected", "reason"), TABLE)
def test_rubric_table(edge: Edge, expected: float, reason: str) -> None:
    confidence, reasons = score(edge)
    assert confidence == expected
    assert len(reasons) == 1
    assert reason in reasons[0]
    assert f"{expected:.2f}" in reasons[0]


def test_computed_and_unknown_sources_keep_their_value_within_bounds() -> None:
    computed = _edge(
        source="analytics",
        evidence=EvidenceType.INFERRED,
        url=None,
        supporting=("E:0123456789abcdef",),
        confidence=0.7,
    )
    assert score(computed) == (
        0.49,
        ("computed analytics value 0.70", "capped at 0.49: inferred stays below curated"),
    )
    unknown_conf, unknown_reasons = score(_edge(source="clinvar", confidence=0.6))
    assert unknown_conf == 0.6
    assert "no rubric row for clinvar" in unknown_reasons[0]


@pytest.mark.parametrize(
    ("sources", "bonus"), [(1, 0.0), (2, 0.05), (3, 0.10), (4, 0.15), (6, 0.15)]
)
def test_corroboration_bonus(sources: int, bonus: float) -> None:
    corroboration = Corroboration(frozenset(f"s{i}" for i in range(sources)))
    confidence, reasons = score(_edge(source="clinicaltrials"), corroboration)
    assert confidence == pytest.approx(0.75 + bonus)
    if sources >= 2:
        assert f"corroborated by {sources} sources" in reasons[1]
    else:
        assert len(reasons) == 1


def test_contradiction_penalty_and_floor() -> None:
    one, reasons = score(_edge(contradicted_by=("E:0000000000000001",)))
    assert one == pytest.approx(0.75)
    assert reasons[-1] == "-0.15 contradicted by 1 record"
    many = _edge(
        source="curated",
        qualifiers={"verification": "url_resolves"},
        contradicted_by=tuple(f"E:000000000000000{i}" for i in range(5)),
    )
    floor, many_reasons = score(many)
    assert floor == rubric.FLOOR
    assert "5 records" in many_reasons[-1]


def test_contradicts_edges_are_not_penalised_for_listing_what_they_dispute() -> None:
    edge = _edge(
        source="curated",
        relation=Relation.CONTRADICTS,
        contradicted_by=("E:0000000000000001",),
        ends=("PMID:1", "MONDO:0000001"),
    )
    assert score(edge)[0] == 0.80


def test_inferred_always_below_curated() -> None:
    curated = [e for e, _, _ in TABLE if e.evidence_type is EvidenceType.CURATED]
    inferred = [_llm(c) for c in ("high", "medium", "low")]
    most_sources = Corroboration(frozenset({"a", "b", "c", "d", "e"}))
    lowest_curated = min(score(e)[0] for e in curated)
    for edge, corroboration in product(inferred, (None, most_sources)):
        assert score(edge, corroboration)[0] < lowest_curated
    assert max(rubric.RULES[r].base for r in rubric.RULES if r.startswith("inferred")) < min(
        rule.base for key, rule in rubric.RULES.items() if not key.startswith("inferred")
    )


def test_values_always_in_unit_interval() -> None:
    corroborations = (None, Corroboration(frozenset({"a", "b", "c", "d"})))
    for (edge, _, _), corroboration in product(TABLE, corroborations):
        confidence, _ = score(edge, corroboration)
        assert 0.0 <= confidence <= 1.0


def test_independent_sources() -> None:
    omim = _edge(qualifiers={"primary_knowledge_source": "infores:omim"}, record="a")
    orphanet = _edge(qualifiers={"primary_knowledge_source": "infores:orphanet"}, record="b")
    ctgov = _edge(source="clinicaltrials", record="NCT00000001")
    curated_copy = _edge(source="curated", record="NCT00000001")
    curated_pmid = _edge(source="curated", record="PMID:9")
    assert independent_source(omim) == "infores:omim"
    assert independent_source(_llm("high", pmid="PMID:7")) == "PMID:7"
    assert independent_source(curated_copy) == "clinicaltrials"
    assert independent_source(curated_pmid) == "PMID:9"
    index = corroboration_index([omim, orphanet, ctgov, curated_copy])
    key = rubric.triple(omim)
    assert index[key].count == 3  # omim, orphanet, clinicaltrials (the curated copy is not new)


def test_apply_rescores_with_corroboration_and_keeps_ids() -> None:
    omim = _edge(qualifiers={"primary_knowledge_source": "infores:omim"}, record="a")
    orphanet = _edge(qualifiers={"primary_knowledge_source": "infores:orphanet"}, record="b")
    lone = _edge(record="c", ends=("MONDO:0000002", "HGNC:2"))
    rescored = rubric.apply([omim, orphanet, lone])
    assert [e.id for e in rescored] == [omim.id, orphanet.id, lone.id]
    assert [e.confidence for e in rescored] == [0.95, 0.95, 0.90]
    assert rescored[0].confidence_reasons[1] == "+0.05 corroborated by 2 sources (omim, orphanet)"
