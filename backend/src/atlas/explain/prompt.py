"""Prompt and JSON schema for Explain. The context holds ONLY facts taken from the edges."""

from collections.abc import Mapping, Sequence
from typing import Any

from atlas.explain.models import Audience
from atlas.models.evidence import Edge, Node

PROMPT_VERSION = "explain-v1"

_AUDIENCE_STYLE: Mapping[str, str] = {
    "family": (
        "Write for a patient family with no science background: short sentences, everyday "
        "words (about a grade-8 reading level), and explain any technical term in a few words."
    ),
    "researcher": (
        "Write for a biomedical researcher: precise terms, name the source database and "
        "record for each claim, and note the evidence type and confidence."
    ),
}

INSTRUCTIONS = (
    "You explain a path through a rare-disease evidence graph. You are given a numbered list "
    "of edges; each edge has an id like E:0123456789abcdef and the facts recorded for it. "
    "Rules: (1) Use ONLY the facts in the edges. Never add diseases, genes, drugs, numbers, "
    "doses, outcomes or claims that are not in the edges. (2) Every step must cite at least "
    "one edge id from the list in edge_ids, and only ids from the list. (3) If an edge's "
    "evidence type is 'inferred', or a step joins facts in a way the edges do not state "
    "directly, set is_hypothesis to true and say plainly that it is a hypothesis. (4) This is "
    "research context only: give no treatment, dosing or medical advice; say what experts "
    "must verify. (5) In caveats, list what is uncertain or missing (low confidence, inferred "
    "links, contradictions, facts the edges do not cover). Mention every contradicted edge. "
    "Keep steps in path order."
)


def instructions_for(audience: Audience) -> str:
    """System instructions plus the audience style line."""
    return f"{INSTRUCTIONS} {_AUDIENCE_STYLE[audience]}"


def _node_text(node_id: str, nodes: Mapping[str, Node]) -> str:
    node = nodes.get(node_id)
    if node is None:
        return node_id
    return f"{node.label} ({node.type.value}, {node.id})"


def edge_context(edge: Edge, nodes: Mapping[str, Node]) -> str:
    """Facts for one edge, one per line. Nothing outside the edge and its endpoint labels."""
    prov = edge.provenance
    url = f"; url: {prov.url}" if prov.url else ""
    lines = [
        f"[{edge.id}] {_node_text(edge.source_id, nodes)} --{edge.relation.value}--> "
        f"{_node_text(edge.target_id, nodes)}",
        f"  evidence_type: {edge.evidence_type.value}; confidence: {edge.confidence:.2f}",
        f"  source: {prov.source}; record: {prov.source_record_id}{url}",
    ]
    if prov.evidence_quote:
        lines.append(f"  quote: {prov.evidence_quote}")
    if edge.qualifiers:
        pairs = "; ".join(f"{key}={value}" for key, value in sorted(edge.qualifiers.items()))
        lines.append(f"  qualifiers: {pairs}")
    if edge.contradicted_by:
        lines.append(f"  contradicted_by: {', '.join(edge.contradicted_by)}")
    return "\n".join(lines)


def build_context(edges: Sequence[Edge], nodes: Mapping[str, Node]) -> str:
    """The model input: every edge's facts, in path order."""
    body = "\n".join(f"{i}. {edge_context(edge, nodes)}" for i, edge in enumerate(edges, 1))
    return f"Edges (path order):\n{body}"


def response_schema(edge_ids: Sequence[str]) -> dict[str, Any]:
    """Strict JSON schema; each cited id must be one of exactly the provided edge ids."""
    step = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "edge_ids": {"type": "array", "items": {"type": "string", "enum": list(edge_ids)}},
            "is_hypothesis": {"type": "boolean"},
        },
        "required": ["text", "edge_ids", "is_hypothesis"],
        "additionalProperties": False,
    }
    return {
        "format": {
            "type": "json_schema",
            "name": "atlas_explanation",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "steps": {"type": "array", "items": step},
                    "summary": {"type": "string"},
                    "caveats": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["steps", "summary", "caveats"],
                "additionalProperties": False,
            },
        }
    }
