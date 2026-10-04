"""Monarch API v3: seed disease/gene entities, gene-disease links and disease phenotypes.

Gene-disease associations in Monarch carry ``primary_knowledge_source`` (``infores:omim``,
``infores:orphanet``); we keep it in the edge qualifiers so OMIM-sourced links are attributed
to OMIM without ingesting OMIM itself (its licence restricts redistribution).

Predicate mapping (direction follows docs/EVIDENCE_MODEL.md):

* ``biolink:causes`` (gene -> disease)            -> disease ``caused_by`` gene
* ``biolink:contributes_to`` (gene -> disease)    -> gene ``risk_factor_for`` disease
* ``biolink:gene_associated_with_condition``       -> ``caused_by`` when OMIM also says
  ``causes`` for the same pair (independent Orphanet support), otherwise ``risk_factor_for``
  with ``association_role=unspecified`` so the UI never upgrades it to a cause.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import HttpUrl

from atlas.ingest.common import (
    IngestResult,
    JsonDict,
    PoliteClient,
    clean_text,
    dedupe_edges,
    make_meta,
    merge_nodes,
    parse_time,
)
from atlas.ingest.seeds import SEED_DISEASES, SEED_GENES
from atlas.models.evidence import (
    CURIE_PATTERN,
    Edge,
    EvidenceType,
    FrozenStrMap,
    Node,
    NodeType,
    Provenance,
    Relation,
)

logger = logging.getLogger(__name__)

SOURCE = "monarch"
EXTRACTOR = "ingest:monarch"
API = "https://api-v3.monarchinitiative.org/v3/api"
WEB = "https://monarchinitiative.org"
PAGE_SIZE = 500
CURATED_CONFIDENCE = 0.9
DESCRIPTION_MAX = 600

GENE_DISEASE_CATEGORIES = (
    "biolink:CausalGeneToDiseaseAssociation",
    "biolink:CorrelatedGeneToDiseaseAssociation",
)
PHENOTYPE_CATEGORY = "biolink:DiseaseToPhenotypicFeatureAssociation"

CAUSES = "biolink:causes"
CONTRIBUTES_TO = "biolink:contributes_to"
ASSOCIATED = "biolink:gene_associated_with_condition"

KNOWLEDGE_SOURCE_LABELS = {
    "infores:omim": "OMIM",
    "infores:orphanet": "Orphanet",
    "infores:hpo-annotations": "HPO annotations",
}

# HPO frequency terms (HP:0040279 subtree) -> human-readable label.
FREQUENCY_LABELS = {
    "HP:0040280": "Obligate (100%)",
    "HP:0040281": "Very frequent (99-80%)",
    "HP:0040282": "Frequent (79-30%)",
    "HP:0040283": "Occasional (29-5%)",
    "HP:0040284": "Very rare (<4-1%)",
    "HP:0040285": "Excluded (0%)",
}

ENTITY_FIELDS = ("id", "name", "category", "description", "synonym", "xref", "symbol", "full_name")
ASSOCIATION_FIELDS = (
    "id",
    "category",
    "subject",
    "subject_label",
    "predicate",
    "object",
    "object_label",
    "primary_knowledge_source",
    "original_subject",
    "negated",
    "publications",
    "frequency_qualifier",
    "has_percentage",
    "onset_qualifier",
    "onset_qualifier_label",
)

XREF_PREFIX_MAP = {"Orphanet": "ORPHA"}


# --------------------------------------------------------------------------------------------
# fetch
# --------------------------------------------------------------------------------------------


def _pick(record: Mapping[str, Any], fields: Iterable[str]) -> JsonDict:
    return {key: record.get(key) for key in fields if record.get(key) not in (None, [], "")}


def fetch_associations(client: PoliteClient, params: Mapping[str, Any]) -> list[JsonDict]:
    """Page through /association with the given filters and return trimmed records."""
    items: list[JsonDict] = []
    offset = 0
    while True:
        page = client.get_json(
            f"{API}/association", params={**params, "limit": PAGE_SIZE, "offset": offset}
        )
        batch = page.get("items") or []
        # Monarch matches the subject *closure*: a grouping disease also returns its subtypes'
        # associations. Keep direct assertions only.
        items.extend(
            _pick(item, ASSOCIATION_FIELDS)
            for item in batch
            if "subject" not in params or item.get("subject") == params["subject"]
        )
        offset += len(batch)
        if not batch or offset >= int(page.get("total") or 0):
            return items


def fetch_version(client: PoliteClient) -> str | None:
    data = client.get_json(f"{API}/version")
    version = data.get("monarch_kg_version")
    return str(version) if version else None


def fetch(client: PoliteClient) -> JsonDict:
    """Fetch seed entities, gene-disease and disease-phenotype associations (compact)."""
    version = fetch_version(client)
    entities: dict[str, JsonDict] = {}
    for entity_id in (*SEED_DISEASES, *SEED_GENES):
        entities[entity_id] = _pick(client.get_json(f"{API}/entity/{entity_id}"), ENTITY_FIELDS)

    gene_disease: list[JsonDict] = []
    for gene_id in SEED_GENES:
        gene_disease.extend(
            fetch_associations(client, {"subject": gene_id, "category": GENE_DISEASE_CATEGORIES})
        )
    phenotypes: list[JsonDict] = []
    for disease_id in SEED_DISEASES:
        phenotypes.extend(
            fetch_associations(client, {"subject": disease_id, "category": PHENOTYPE_CATEGORY})
        )
    return {
        "meta": make_meta(f"{API}/association", f"monarch-kg {version}" if version else None),
        "entities": dict(sorted(entities.items())),
        "gene_disease": sorted(gene_disease, key=_association_key),
        "disease_phenotype": sorted(phenotypes, key=_association_key),
    }


def _association_key(item: Mapping[str, Any]) -> tuple[str, ...]:
    return (
        str(item.get("subject")),
        str(item.get("predicate")),
        str(item.get("object")),
        str(item.get("primary_knowledge_source")),
        str(item.get("id")),
    )


# --------------------------------------------------------------------------------------------
# normalize
# --------------------------------------------------------------------------------------------


def normalize_xref(xref: str) -> str | None:
    """Map Monarch xref prefixes to ours (Orphanet: -> ORPHA:) and drop malformed values."""
    prefix, _, local = xref.partition(":")
    if not local:
        return None
    curie = f"{XREF_PREFIX_MAP.get(prefix, prefix)}:{local}"
    return curie if re.match(CURIE_PATTERN, curie) else None


def _synonyms(label: str, values: Iterable[str | None]) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for value in values:
        text = clean_text(value)
        if text and text.casefold() != label.casefold():
            seen.setdefault(text, None)
    return tuple(seen)


def entity_node(entity: Mapping[str, Any]) -> Node:
    """Build a disease or gene node from a trimmed Monarch entity record."""
    entity_id = str(entity["id"])
    is_gene = entity_id in SEED_GENES or entity.get("category") == "biolink:Gene"
    label = clean_text(entity.get("symbol") if is_gene else entity.get("name")) or entity_id
    synonyms = _synonyms(label, [entity.get("full_name"), *(entity.get("synonym") or [])])
    xrefs = tuple(
        dict.fromkeys(x for x in map(normalize_xref, entity.get("xref") or []) if x is not None)
    )
    attributes: dict[str, str] = {"monarch_url": f"{WEB}/{entity_id}"}
    description = clean_text(entity.get("description"), DESCRIPTION_MAX)
    if is_gene:
        full_name = clean_text(entity.get("full_name"))
        if full_name:
            attributes["full_name"] = full_name
        description = description or full_name
    else:
        role = SEED_DISEASES.get(entity_id)
        if role:
            attributes["slice_role"] = role
    if description:
        attributes["description"] = description
    return Node(
        id=entity_id,
        type=NodeType.GENE if is_gene else NodeType.DISEASE,
        label=label,
        synonyms=synonyms,
        xrefs=xrefs,
        attributes=FrozenStrMap(attributes),
    )


def _provenance(record_id: str, page_id: str, retrieved_at: str, version: str | None) -> Provenance:
    return Provenance(
        source=SOURCE,
        source_record_id=record_id,
        url=HttpUrl(f"{WEB}/{page_id}"),
        retrieved_at=parse_time(retrieved_at),
        source_version=version,
        extractor=EXTRACTOR,
    )


def _record_id(item: Mapping[str, Any]) -> str:
    """Stable per-assertion record id (Monarch association uuids change between KG releases)."""
    return "|".join(
        (
            str(item.get("primary_knowledge_source") or "unknown"),
            str(item["subject"]),
            str(item["predicate"]),
            str(item["object"]),
        )
    )


def _ks_label(item: Mapping[str, Any]) -> str:
    source = str(item.get("primary_knowledge_source") or "unknown")
    return KNOWLEDGE_SOURCE_LABELS.get(source, source)


def gene_disease_edges(items: list[JsonDict], retrieved_at: str, version: str | None) -> list[Edge]:
    omim_causal = {
        (item["subject"], item["object"])
        for item in items
        if item.get("predicate") == CAUSES and not item.get("negated")
    }
    edges: list[Edge] = []
    for item in items:
        if item.get("negated"):
            continue
        gene, disease, predicate = str(item["subject"]), str(item["object"]), item["predicate"]
        qualifiers = {
            "monarch_predicate": str(predicate),
            "primary_knowledge_source": str(item.get("primary_knowledge_source") or "unknown"),
        }
        if item.get("original_subject"):
            qualifiers["original_subject"] = str(item["original_subject"])
        if predicate == CAUSES or (predicate == ASSOCIATED and (gene, disease) in omim_causal):
            source_id, relation, target_id = disease, Relation.CAUSED_BY, gene
        elif predicate in (CONTRIBUTES_TO, ASSOCIATED):
            source_id, relation, target_id = gene, Relation.RISK_FACTOR_FOR, disease
            if predicate == ASSOCIATED:
                qualifiers["association_role"] = "unspecified"
        else:
            logger.info("skipping unmapped Monarch predicate %s", predicate)
            continue
        edges.append(
            Edge(
                source_id=source_id,
                target_id=target_id,
                relation=relation,
                provenance=_provenance(_record_id(item), disease, retrieved_at, version),
                confidence=CURATED_CONFIDENCE,
                evidence_type=EvidenceType.CURATED,
                qualifiers=FrozenStrMap(qualifiers),
                confidence_reasons=(f"curated KB 0.90 ({_ks_label(item)} via Monarch)",),
            )
        )
    return edges


def phenotype_edges(items: list[JsonDict], retrieved_at: str, version: str | None) -> list[Edge]:
    edges: list[Edge] = []
    for item in items:
        if item.get("negated"):
            continue
        qualifiers = {
            "primary_knowledge_source": str(item.get("primary_knowledge_source") or "unknown"),
        }
        frequency = item.get("frequency_qualifier")
        if frequency:
            qualifiers["frequency"] = FREQUENCY_LABELS.get(str(frequency), str(frequency))
            qualifiers["frequency_term"] = str(frequency)
        if item.get("has_percentage") is not None:
            qualifiers["frequency_percent"] = str(item["has_percentage"])
        if item.get("onset_qualifier"):
            qualifiers["onset"] = str(item.get("onset_qualifier_label") or item["onset_qualifier"])
        edges.append(
            Edge(
                source_id=str(item["subject"]),
                target_id=str(item["object"]),
                relation=Relation.HAS_PHENOTYPE,
                provenance=_provenance(
                    _record_id(item), str(item["subject"]), retrieved_at, version
                ),
                confidence=CURATED_CONFIDENCE,
                evidence_type=EvidenceType.CURATED,
                qualifiers=FrozenStrMap(qualifiers),
                confidence_reasons=(f"curated KB 0.90 (HPO annotation, {_ks_label(item)})",),
            )
        )
    return edges


def _stub_node(node_id: str, label: str | None, node_type: NodeType) -> Node:
    return Node(
        id=node_id,
        type=node_type,
        label=clean_text(label) or node_id,
        attributes=FrozenStrMap({"monarch_url": f"{WEB}/{node_id}"}),
    )


def normalize(payload: Mapping[str, Any]) -> IngestResult:
    """Turn the cached Monarch payload into nodes and edges (pure, deterministic)."""
    meta = payload["meta"]
    retrieved_at, version = str(meta["retrieved_at"]), meta.get("source_version")
    entities: Mapping[str, JsonDict] = payload.get("entities") or {}
    gene_disease: list[JsonDict] = list(payload.get("gene_disease") or [])
    disease_phenotype: list[JsonDict] = [
        item for item in payload.get("disease_phenotype") or [] if item.get("subject") in entities
    ]

    nodes = [entity_node(entity) for entity in entities.values()]
    for item in gene_disease:
        nodes.append(_stub_node(str(item["object"]), item.get("object_label"), NodeType.DISEASE))
    for item in disease_phenotype:
        nodes.append(_stub_node(str(item["object"]), item.get("object_label"), NodeType.PHENOTYPE))

    edges = gene_disease_edges(gene_disease, retrieved_at, version)
    edges += phenotype_edges(disease_phenotype, retrieved_at, version)
    missing_entities = sorted((set(SEED_DISEASES) | set(SEED_GENES)) - set(entities))
    return IngestResult(
        source=SOURCE,
        source_version=version,
        retrieved_at=retrieved_at,
        nodes=merge_nodes(nodes),
        edges=dedupe_edges(edges),
        notes={
            "records": len(gene_disease) + len(disease_phenotype),
            "missing_seed_entities": missing_entities,
        },
    )


def phenotype_ids(payload: Mapping[str, Any]) -> tuple[str, ...]:
    """HPO ids used by the slice (input for the HPO information-content step)."""
    return tuple(sorted({str(item["object"]) for item in payload.get("disease_phenotype") or []}))
