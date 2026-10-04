"""Deterministic template explanation: one sentence per edge, no model involved.

Direction convention (docs/EVIDENCE_MODEL.md): every relation reads source_id -> target_id,
e.g. ``Gaucher disease type III caused_by GBA1`` (source = disease, target = gene),
``GBA1 risk_factor_for Parkinson disease``, ``trial studies_condition disease``,
``funder funds trial``, ``organization represents disease``.
"""

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from atlas.explain.models import Audience, ExplainResponse, ExplainStep
from atlas.explain.prompt import PROMPT_VERSION
from atlas.models.evidence import Edge, EvidenceType, Node, Relation

LOW_CONFIDENCE = 0.7

RELATION_PHRASES: Mapping[Relation, str] = MappingProxyType(
    {
        Relation.CAUSED_BY: "{source} is caused by changes in {target}.",
        Relation.RISK_FACTOR_FOR: "Changes in {source} are a risk factor for {target}.",
        Relation.HAS_VARIANT: "{source} has the variant {target}.",
        Relation.VARIANT_ASSOCIATED_WITH: "The variant {source} is associated with {target}.",
        Relation.HAS_MECHANISM: "{source} involves the biological mechanism {target}.",
        Relation.PARTICIPATES_IN: "{source} takes part in {target}.",
        Relation.HAS_PHENOTYPE: "{source} can show the feature {target}.",
        Relation.SHARES_MECHANISM_WITH: "{source} shares a biological mechanism with {target}.",
        Relation.SIMILAR_PHENOTYPE_TO: "{source} has features similar to {target}.",
        Relation.MENTIONS: "{source} mentions {target}.",
        Relation.CLAIMS: "{source} reports the finding {target}.",
        Relation.AUTHORED_BY: "{source} was written by {target}.",
        Relation.STUDIES_CONDITION: "The study {source} focuses on {target}.",
        Relation.TESTS_INTERVENTION: "The study {source} tests {target}.",
        Relation.INVESTIGATES: "{source} investigates {target}.",
        Relation.FUNDS: "{source} funds {target}.",
        Relation.WORKS_ON: "{source} works on {target}.",
        Relation.REPRESENTS: "{source} represents people affected by {target}.",
        Relation.OPERATES: "{source} runs {target}.",
        Relation.CONTRADICTS: "{source} contradicts {target}.",
    }
)

HYPOTHESIS_PREFIX = "Hypothesis (inferred, not directly observed): "
ADVICE_CAVEAT = (
    "Research context only, not medical advice: a clinician or researcher must verify each "
    "link before acting on it."
)
TEMPLATE_CAVEAT = "Written from a fixed template because the AI explanation is unavailable."


def _label(node_id: str, nodes: Mapping[str, Node]) -> str:
    node = nodes.get(node_id)
    return node.label if node is not None else node_id


def edge_sentence(edge: Edge, nodes: Mapping[str, Node], audience: Audience = "family") -> str:
    """One sentence for one edge, using the relation's direction-aware phrase."""
    sentence = RELATION_PHRASES[edge.relation].format(
        source=_label(edge.source_id, nodes), target=_label(edge.target_id, nodes)
    )
    sentence = sentence[0].upper() + sentence[1:]
    if audience == "researcher":
        prov = edge.provenance
        sentence = (
            f"{sentence} (source: {prov.source} {prov.source_record_id}; "
            f"{edge.evidence_type.value}, confidence {edge.confidence:.2f})"
        )
    if edge.evidence_type is EvidenceType.INFERRED:
        sentence = HYPOTHESIS_PREFIX + sentence
    return sentence


def _caveats(edges: Sequence[Edge]) -> list[str]:
    caveats = [ADVICE_CAVEAT]
    if any(e.evidence_type is EvidenceType.INFERRED for e in edges):
        caveats.append("Some links are inferred (for example extracted from text), not curated.")
    low = [e.id for e in edges if e.confidence < LOW_CONFIDENCE]
    if low:
        caveats.append(f"Lower-confidence links (below {LOW_CONFIDENCE:.1f}): {', '.join(low)}.")
    contradicted = [e.id for e in edges if e.contradicted_by]
    if contradicted:
        caveats.append(f"Other evidence contradicts: {', '.join(contradicted)}.")
    caveats.append(TEMPLATE_CAVEAT)
    return caveats


def path_ends(edges: Sequence[Edge]) -> tuple[str, str] | None:
    """Start and end node ids of a chained path, independent of each edge's direction."""
    if not edges:
        return None
    if len(edges) == 1:
        return edges[0].source_id, edges[0].target_id
    first, second, prev, last = edges[0], edges[1], edges[-2], edges[-1]
    start = (
        first.source_id
        if first.target_id in {second.source_id, second.target_id}
        else (first.target_id)
    )
    end = last.target_id if last.source_id in {prev.source_id, prev.target_id} else last.source_id
    return start, end


def template_explanation(
    edges: Sequence[Edge], nodes: Mapping[str, Node], audience: Audience = "family"
) -> ExplainResponse:
    """Deterministic, always-available explanation (source="template", ai_generated=False)."""
    steps = [
        ExplainStep(
            text=edge_sentence(edge, nodes, audience),
            edge_ids=[edge.id],
            is_hypothesis=edge.evidence_type is EvidenceType.INFERRED,
        )
        for edge in edges
    ]
    ends = path_ends(edges)
    start = _label(ends[0], nodes) if ends else "this entity"
    end = _label(ends[1], nodes) if ends else "the next one"
    summary = f"This path links {start} to {end} through {len(edges)} recorded fact(s)."
    return ExplainResponse(
        steps=steps,
        summary=summary,
        caveats=_caveats(edges),
        source="template",
        model=None,
        prompt_version=PROMPT_VERSION,
        ai_generated=False,
    )
