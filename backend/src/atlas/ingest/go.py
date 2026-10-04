"""GO biological-process annotations for the seed genes (via Monarch) -> mechanism edges.

Only terms on the curated whitelist (``data/curated/mechanisms.yaml``) become mechanism nodes.
A gene annotated to a whitelisted term, or to any descendant of it (Monarch returns the
ancestor closure of every annotated term), gets one ``participates_in`` edge to that term.
All GO annotations for that gene-term pair are summarized in the edge qualifiers.

Confidence: 0.90 when at least one supporting annotation is not inferred electronically
(evidence code other than IEA, ECO:0000501); 0.70 when all of them are IEA.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import HttpUrl

from atlas.ingest.common import (
    IngestResult,
    JsonDict,
    PoliteClient,
    dedupe_edges,
    make_meta,
    merge_nodes,
    parse_time,
    unique_sorted,
)
from atlas.ingest.monarch import API, WEB, fetch_version
from atlas.ingest.seeds import SEED_GENES
from atlas.models.evidence import (
    Edge,
    EvidenceType,
    FrozenStrMap,
    Node,
    NodeType,
    Provenance,
    Relation,
)

SOURCE = "go"
EXTRACTOR = "ingest:go"
CATEGORY = "biolink:MacromolecularMachineToBiologicalProcessAssociation"
IEA = "ECO:0000501"
CONFIDENCE_EXPERIMENTAL = 0.9
CONFIDENCE_IEA_ONLY = 0.7
PAGE_SIZE = 500
MAX_LISTED = 8


def fetch(client: PoliteClient, whitelist: Sequence[str]) -> JsonDict:
    """Fetch GO BP annotations for seed genes; keep only those under a whitelisted term."""
    wanted = set(whitelist)
    version = fetch_version(client)
    annotations: list[JsonDict] = []
    for gene_id in SEED_GENES:
        offset = 0
        while True:
            page = client.get_json(
                f"{API}/association",
                params={
                    "subject": gene_id,
                    "category": CATEGORY,
                    "limit": PAGE_SIZE,
                    "offset": offset,
                },
            )
            batch = page.get("items") or []
            for item in batch:
                closure = set(item.get("object_closure") or []) | {item.get("object")}
                matched = sorted(wanted & closure)
                if not matched or item.get("negated"):
                    continue
                annotations.append(
                    {
                        "gene": gene_id,
                        "term": item.get("object"),
                        "term_label": item.get("object_label"),
                        "matched": matched,
                        "evidence": sorted(item.get("has_evidence") or []),
                        "publications": sorted(item.get("publications") or []),
                        "knowledge_source": item.get("primary_knowledge_source"),
                    }
                )
            offset += len(batch)
            if not batch or offset >= int(page.get("total") or 0):
                break
    annotations.sort(
        key=lambda a: (
            a["gene"],
            str(a["term"]),
            str(a["knowledge_source"]),
            ",".join(a["evidence"]),
            ",".join(a["publications"]),
        )
    )
    return {
        "meta": make_meta(f"{API}/association", f"monarch-kg {version}" if version else None),
        "whitelist": sorted(wanted),
        "annotations": annotations,
    }


def mechanism_nodes(mechanisms: Sequence[Mapping[str, Any]]) -> list[Node]:
    return [
        Node(
            id=str(item["id"]),
            type=NodeType.MECHANISM,
            label=str(item["name"]),
            attributes=FrozenStrMap(
                {
                    "go_aspect": "biological_process",
                    "quickgo_url": str(item["url"]),
                    **({"description": str(item["notes"])} if item.get("notes") else {}),
                }
            ),
        )
        for item in mechanisms
    ]


def normalize(payload: Mapping[str, Any], mechanisms: Sequence[Mapping[str, Any]]) -> IngestResult:
    """Build mechanism nodes (whitelist) and gene ``participates_in`` mechanism edges."""
    meta = payload["meta"]
    retrieved_at = parse_time(str(meta["retrieved_at"]))
    version = meta.get("source_version")
    known = {str(item["id"]) for item in mechanisms}
    grouped: dict[tuple[str, str], list[JsonDict]] = defaultdict(list)
    for annotation in payload.get("annotations") or []:
        for term in annotation["matched"]:
            if term in known:
                grouped[(str(annotation["gene"]), term)].append(annotation)

    edges: list[Edge] = []
    for (gene, term), items in sorted(grouped.items()):
        evidence = unique_sorted(code for item in items for code in item["evidence"])
        experimental = any(code != IEA for code in evidence)
        confidence = CONFIDENCE_EXPERIMENTAL if experimental else CONFIDENCE_IEA_ONLY
        reason = (
            "curated KB 0.90 (GO annotation with non-IEA evidence)"
            if experimental
            else "0.70 (GO annotations inferred electronically only, IEA)"
        )
        annotated_terms = unique_sorted(str(item["term"]) for item in items)
        publications = unique_sorted(pub for item in items for pub in item["publications"])
        edges.append(
            Edge(
                source_id=gene,
                target_id=term,
                relation=Relation.PARTICIPATES_IN,
                provenance=Provenance(
                    source=SOURCE,
                    source_record_id=f"{gene}|{term}",
                    url=HttpUrl(f"{WEB}/{gene}"),
                    retrieved_at=retrieved_at,
                    source_version=version,
                    extractor=EXTRACTOR,
                ),
                confidence=confidence,
                evidence_type=EvidenceType.CURATED,
                qualifiers=FrozenStrMap(
                    {
                        "annotated_terms": ",".join(annotated_terms[:MAX_LISTED]),
                        "annotation_count": str(len(items)),
                        "evidence_codes": ",".join(evidence),
                        "publications": ",".join(publications[:MAX_LISTED]),
                        "via": "Monarch GO associations (term or descendant)",
                    }
                ),
                confidence_reasons=(reason,),
            )
        )
    genes_with_edges = {gene for gene, _ in grouped}
    return IngestResult(
        source=SOURCE,
        source_version=version,
        retrieved_at=str(meta["retrieved_at"]),
        nodes=merge_nodes(mechanism_nodes(mechanisms)),
        edges=dedupe_edges(edges),
        notes={
            "records": len(payload.get("annotations") or []),
            "genes_without_whitelisted_terms": sorted(set(SEED_GENES) - genes_with_edges),
        },
    )
