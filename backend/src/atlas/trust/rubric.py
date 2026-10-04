"""Confidence rubric ``trust-v1``: deterministic, explainable edge confidence.

``score(edge, corroboration)`` is a pure function. It picks a base value from the edge's
evidence type and source (table below, also in docs/EVIDENCE_MODEL.md), adds a bonus when the
same ``(source_id, relation, target_id)`` is asserted by two or more independent sources,
subtracts a penalty per contradicting record, and clamps the result.

| Rule id                | Base | When                                                         |
|------------------------|------|--------------------------------------------------------------|
| kb_gene_disease        | 0.90 | OMIM / Orphanet gene-disease edge (via Monarch)              |
| kb_phenotype           | 0.90 | HPO disease-phenotype annotation (via Monarch)               |
| go_experimental        | 0.85 | GO annotation with at least one non-IEA evidence code        |
| go_iea                 | 0.80 | GO annotations inferred electronically only (IEA)            |
| team_curated           | 0.80 | Team curation with a cited url (assets, funds, verified      |
|                        |      | contradictions)                                              |
| ctgov_record           | 0.75 | ClinicalTrials.gov condition matched a MONDO label/synonym   |
| reporter_record        | 0.75 | NIH RePORTER project record                                  |
| ctgov_alias            | 0.65 | ClinicalTrials.gov condition matched a curated alias         |
| org_page_read          | 0.60 | Patient org whose scope page was read                        |
| org_url_resolves       | 0.50 | Patient org whose url resolves, scope page not read          |
| curated_unverified     | 0.50 | Team curation whose key claim is marked [U]                  |
| inferred_high          | 0.45 | OpenAI Extract claim, stated certainty high                  |
| inferred_medium        | 0.35 | OpenAI Extract claim, stated certainty medium                |
| inferred_low           | 0.25 | OpenAI Extract claim (certainty low) or a mention            |
| inferred_computed      | edge | Analytics edge: keeps its computed value                     |

Adjustments: +0.05 per extra independent source (max +0.15); -0.15 per contradicting record.
The result is clamped to [0.05, 0.99]; inferred edges are additionally capped at 0.49, below
every curated base, so a hypothesis never outranks curated evidence.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from atlas.models.evidence import Edge, EvidenceType, Relation

RUBRIC_VERSION = "trust-v1"
CORROBORATION_STEP = 0.05
CORROBORATION_MAX = 0.15
CONTRADICTION_PENALTY = 0.15
FLOOR = 0.05
CEILING = 0.99
INFERRED_CEILING = 0.49
IEA_CODE = "ECO:0000501"
LLM_PREFIX = "openai:"
KNOWLEDGE_SOURCE_LABELS: Mapping[str, str] = {
    "infores:omim": "OMIM",
    "infores:orphanet": "Orphanet",
}


@dataclass(frozen=True)
class Rule:
    rule_id: str
    base: float
    label: str


RULES: Mapping[str, Rule] = {
    rule.rule_id: rule
    for rule in (
        Rule("kb_gene_disease", 0.90, "curated KB gene-disease"),
        Rule("kb_phenotype", 0.90, "curated KB phenotype annotation (HPO)"),
        Rule("go_experimental", 0.85, "curated GO annotation, non-IEA evidence"),
        Rule("go_iea", 0.80, "curated GO annotation, electronic (IEA) only"),
        Rule("team_curated", 0.80, "team-curated with cited source (needs human check)"),
        Rule("ctgov_record", 0.75, "ClinicalTrials.gov record, condition matched"),
        Rule("reporter_record", 0.75, "NIH RePORTER project record"),
        Rule("ctgov_alias", 0.65, "ClinicalTrials.gov record, condition matched by alias"),
        Rule("org_page_read", 0.60, "org verified on its own site"),
        Rule("org_url_resolves", 0.50, "org url resolves, scope page not read"),
        Rule("curated_unverified", 0.50, "team-curated, key claim unverified [U]"),
        Rule("inferred_high", 0.45, "OpenAI Extract claim, certainty high (hypothesis)"),
        Rule("inferred_medium", 0.35, "OpenAI Extract claim, certainty medium (hypothesis)"),
        Rule("inferred_low", 0.25, "OpenAI Extract claim or mention, low (hypothesis)"),
    )
}
COMPUTED_RULE = "inferred_computed"


@dataclass(frozen=True)
class Corroboration:
    """Independent sources asserting the same ``(source_id, relation, target_id)``."""

    sources: frozenset[str] = frozenset()

    @property
    def count(self) -> int:
        return len(self.sources)


def independent_source(edge: Edge) -> str:
    """Key that tells two assertions apart as independent evidence.

    Monarch edges count by their primary knowledge source (OMIM vs Orphanet). Extract edges
    count per publication. A curated record copied from a registry (NCT) counts as that
    registry, so it does not double-count the ClinicalTrials.gov record.
    """
    prov = edge.provenance
    if prov.source == "monarch":
        return edge.qualifiers.get("primary_knowledge_source", "monarch")
    if (prov.extractor or "").startswith(LLM_PREFIX):
        return prov.source_record_id
    if prov.source == "curated" and prov.source_record_id.startswith("NCT"):
        return "clinicaltrials"
    if prov.source == "curated" and prov.source_record_id.startswith("PMID:"):
        return prov.source_record_id
    return prov.source


def triple(edge: Edge) -> tuple[str, str, str]:
    return (edge.source_id, edge.relation.value, edge.target_id)


def corroboration_index(edges: Iterable[Edge]) -> dict[tuple[str, str, str], Corroboration]:
    """Independent sources per triple, over the whole merged graph."""
    found: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for edge in edges:
        found[triple(edge)].add(independent_source(edge))
    return {key: Corroboration(frozenset(value)) for key, value in found.items()}


def _rule_for(edge: Edge) -> str | None:
    prov = edge.provenance
    qualifiers = edge.qualifiers
    if edge.evidence_type is EvidenceType.INFERRED:
        if not (prov.extractor or "").startswith(LLM_PREFIX):
            return COMPUTED_RULE
        if edge.relation is Relation.MENTIONS:
            return "inferred_low"
        return f"inferred_{qualifiers.get('certainty', 'low')}"
    if prov.source == "monarch":
        return "kb_phenotype" if edge.relation is Relation.HAS_PHENOTYPE else "kb_gene_disease"
    if prov.source == "go":
        codes = [c for c in qualifiers.get("evidence_codes", "").split(",") if c]
        return "go_experimental" if any(c != IEA_CODE for c in codes) else "go_iea"
    if prov.source == "clinicaltrials":
        return "ctgov_alias" if qualifiers.get("condition_match") == "alias" else "ctgov_record"
    if prov.source == "reporter":
        return "reporter_record"
    if prov.source == "curated":
        verification = qualifiers.get("verification")
        if verification == "page_read":
            return "org_page_read"
        if verification == "url_resolves":
            return "org_url_resolves"
        if verification == "unverified":
            return "curated_unverified"
        return "team_curated"
    return None


def _base(edge: Edge) -> tuple[float, str]:
    rule_id = _rule_for(edge)
    if rule_id == COMPUTED_RULE:
        return edge.confidence, f"computed analytics value {edge.confidence:.2f}"
    rule = RULES.get(rule_id or "")
    if rule is None:
        return edge.confidence, f"no rubric row for {edge.provenance.source}; ingest value"
    source = edge.qualifiers.get("primary_knowledge_source", "")
    name = KNOWLEDGE_SOURCE_LABELS.get(source, source.removeprefix("infores:"))
    via = f" ({name} via Monarch)" if source else ""
    return rule.base, f"{rule.label}{via} {rule.base:.2f}"


def _clamp(value: float, evidence_type: EvidenceType) -> float:
    ceiling = INFERRED_CEILING if evidence_type is EvidenceType.INFERRED else CEILING
    return round(min(max(value, FLOOR), ceiling), 4)


def score(edge: Edge, corroboration: Corroboration | None = None) -> tuple[float, tuple[str, ...]]:
    """Confidence in [0.05, 0.99] and the rubric steps that produced it."""
    value, first = _base(edge)
    reasons = [first]
    names = sorted(s.removeprefix("infores:") for s in (corroboration or Corroboration()).sources)
    sources = len(names)
    if sources >= 2:
        bonus = min(CORROBORATION_STEP * (sources - 1), CORROBORATION_MAX)
        value += bonus
        reasons.append(f"+{bonus:.2f} corroborated by {sources} sources ({', '.join(names)})")
    contradictions = 0 if edge.relation is Relation.CONTRADICTS else len(edge.contradicted_by)
    if contradictions:
        penalty = CONTRADICTION_PENALTY * contradictions
        value -= penalty
        noun = "record" if contradictions == 1 else "records"
        reasons.append(f"-{penalty:.2f} contradicted by {contradictions} {noun}")
    final = _clamp(value, edge.evidence_type)
    if edge.evidence_type is EvidenceType.INFERRED and value > INFERRED_CEILING:
        reasons.append(f"capped at {INFERRED_CEILING:.2f}: inferred stays below curated")
    return final, tuple(reasons)


def apply(edges: Iterable[Edge]) -> tuple[Edge, ...]:
    """Rescore every edge with the rubric, using corroboration across the whole set."""
    edge_list = tuple(edges)
    index = corroboration_index(edge_list)
    rescored = []
    for edge in edge_list:
        confidence, reasons = score(edge, index.get(triple(edge)))
        rescored.append(
            edge.model_copy(update={"confidence": confidence, "confidence_reasons": reasons})
        )
    return tuple(rescored)
