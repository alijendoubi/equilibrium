"""Validated claims -> evidence-model nodes and edges, and the pipeline's extract stage.

Every claim edge is ``inferred`` with extractor ``openai:<model>`` and PubMed provenance
(``PMID:<n>``, the article URL, the verbatim quote). Confidence follows the stated certainty
and always stays below curated evidence. Each PMID with at least one claim also becomes a
publication node with ``mentions`` edges to the entities it was grounded to.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from atlas.extract.claims import (
    DEFAULT_CLAIMS_PATH,
    Claim,
    ClaimsCache,
    Extraction,
    candidate_nodes,
    claims_key,
)
from atlas.extract.pubmed import (
    CACHE_SOURCE,
    DEFAULT_ABSTRACTS_PATH,
    ESEARCH_URL,
    Abstract,
    load_abstracts,
    load_payload,
)
from atlas.ingest.common import IngestResult, parse_time
from atlas.models.evidence import Edge, EvidenceType, Node, NodeType, Provenance, Relation
from atlas.reconcile.usage import UsageRecord

CONFIDENCE_BY_CERTAINTY: Mapping[str, float] = {"high": 0.6, "medium": 0.45, "low": 0.3}
MENTION_CONFIDENCE = 0.3
INFERRED_REASON = "LLM-extracted from a PubMed abstract (inferred, below curated evidence)"


@dataclass(frozen=True)
class ExtractStage:
    """What the pipeline adds: an IngestResult plus the OpenAI usage behind the claims."""

    result: IngestResult
    usage: UsageRecord
    claims: int
    dropped: int


def _provenance(abstract: Abstract, model: str, quote: str, retrieved_at: datetime) -> Provenance:
    return Provenance(
        source=CACHE_SOURCE,
        source_record_id=abstract.node_id,
        url=abstract.url,  # type: ignore[arg-type]
        retrieved_at=retrieved_at,
        evidence_quote=quote,
        extractor=f"openai:{model}",
    )


def publication_node(abstract: Abstract) -> Node:
    attributes = {"title": abstract.title, "year": abstract.year, "journal": abstract.journal}
    if abstract.authors:
        attributes["authors"] = "; ".join(abstract.authors)
    return Node(
        id=abstract.node_id,
        type=NodeType.PUBLICATION,
        label=abstract.title or abstract.node_id,
        xrefs=(abstract.node_id,),
        attributes={k: v for k, v in attributes.items() if v},  # type: ignore[arg-type]
    )


def claim_edge(claim: Claim, abstract: Abstract, model: str, retrieved_at: datetime) -> Edge:
    confidence = CONFIDENCE_BY_CERTAINTY[claim.certainty]
    return Edge(
        source_id=claim.subject_id,
        target_id=claim.object_id,
        relation=Relation(claim.relation),
        provenance=_provenance(abstract, model, claim.quote, retrieved_at),
        confidence=confidence,
        evidence_type=EvidenceType.INFERRED,
        qualifiers={"polarity": claim.polarity, "certainty": claim.certainty},  # type: ignore[arg-type]
        confidence_reasons=(
            INFERRED_REASON,
            f"text certainty '{claim.certainty}' -> {confidence}",
            f"quote verified verbatim in {abstract.node_id}",
        ),
    )


def mention_edge(entity_id: str, quote: str, abstract: Abstract, model: str, at: datetime) -> Edge:
    return Edge(
        source_id=abstract.node_id,
        target_id=entity_id,
        relation=Relation.MENTIONS,
        provenance=_provenance(abstract, model, quote, at),
        confidence=MENTION_CONFIDENCE,
        evidence_type=EvidenceType.INFERRED,
        confidence_reasons=(INFERRED_REASON, "entity grounded to a candidate node id"),
    )


def to_graph(
    extractions: Sequence[Extraction],
    abstracts: Mapping[str, Abstract],
    retrieved_at: datetime,
) -> tuple[tuple[Node, ...], tuple[Edge, ...]]:
    """Publication nodes plus claim and mention edges, in a deterministic order."""
    nodes: dict[str, Node] = {}
    edges: dict[str, Edge] = {}
    for extraction in sorted(extractions, key=lambda e: int(e.pmid)):
        abstract = abstracts.get(extraction.pmid)
        if abstract is None or not extraction.claims:
            continue
        nodes.setdefault(abstract.node_id, publication_node(abstract))
        for claim in extraction.claims:
            built = [claim_edge(claim, abstract, extraction.model, retrieved_at)]
            built += [
                mention_edge(entity, claim.quote, abstract, extraction.model, retrieved_at)
                for entity in (claim.subject_id, claim.object_id)
            ]
            for edge in built:
                edges.setdefault(edge.id, edge)
    return tuple(nodes[k] for k in sorted(nodes)), tuple(edges[k] for k in sorted(edges))


def extract_stage(
    graph_nodes: Sequence[Node],
    model: str,
    claims_path: Path = DEFAULT_CLAIMS_PATH,
    abstracts_path: Path = DEFAULT_ABSTRACTS_PATH,
) -> ExtractStage | None:
    """Cached extractions for the current candidate set, or None when there are none.

    Pure function of the two cache files and the graph: no network, no clock.
    """
    cache = ClaimsCache.load(claims_path)
    if not len(cache):
        return None
    payload = load_payload(abstracts_path)
    abstracts = {a.pmid: a for a in load_abstracts(abstracts_path)}
    candidates = candidate_nodes(graph_nodes)
    found = [cache.get(claims_key(model, pmid, candidates)) for pmid in sorted(abstracts)]
    extractions = [e for e in found if e is not None]
    if not extractions:
        return None
    retrieved_at = str(payload.get("meta", {}).get("retrieved_at", ""))
    nodes, edges = to_graph(extractions, abstracts, parse_time(retrieved_at))
    usage = UsageRecord()
    for extraction in extractions:
        usage = usage.merge(UsageRecord.single(extraction.model, extraction.usage))
    claims = sum(len(e.claims) for e in extractions)
    result = IngestResult(
        source=CACHE_SOURCE,
        source_version=None,
        retrieved_at=retrieved_at,
        nodes=nodes,
        edges=edges,
        notes={
            "records": len(extractions),
            "url": ESEARCH_URL,
            "claims": claims,
            "dropped_claims": sum(e.dropped for e in extractions),
        },
    )
    return ExtractStage(result, usage, claims, sum(e.dropped for e in extractions))
