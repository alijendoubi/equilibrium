"""Hand-curated organizations, assets and mechanisms from ``data/curated/*.yaml``.

Node ids:

* organizations -> ``org:<slug>`` (``patient_group``; ``funder`` for funder programmes and
  research charities)
* assets whose ``source_record_id`` is an NCT id -> ``clinicaltrials:<NCT>`` (``study``), so the
  curated record and the ClinicalTrials.gov record merge into one node
* ``publication_*`` assets whose ``source_record_id`` is ``PMID:<n>`` -> ``PMID:<n>``
  (``publication``)
* any other asset -> ``asset:<slug>`` (``asset``)

Edges (all ``evidence_type: curated``, ``provenance.url`` = the entry's url):

* org ``represents`` disease (per ``disease_ids``)
* org ``funds`` / ``operates`` asset (optional ``funds`` / ``operates`` slug lists on an org)
* study/asset ``studies_condition`` disease; publication ``mentions`` disease

``no_dedicated_org_found`` entries are returned as coverage data in the notes, never as edges.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import HttpUrl

from atlas.ingest.common import (
    CURATED_DIR,
    IngestResult,
    JsonDict,
    clean_text,
    dedupe_edges,
    merge_nodes,
)
from atlas.models.evidence import (
    Edge,
    EvidenceType,
    FrozenStrMap,
    Node,
    NodeType,
    Provenance,
    Relation,
)

SOURCE = "curated"
EXTRACTOR = "ingest:curated"
ORG_PREFIX = "org:"
ASSET_PREFIX = "asset:"
STUDY_PREFIX = "clinicaltrials:"
CONFIDENCE_CURATED = 0.8
CONFIDENCE_ORG_READ = 0.6
CONFIDENCE_ORG_RESOLVES = 0.5
FUNDER_TYPES = frozenset({"research_funder_program", "research_charity"})
FILES = ("organizations", "assets", "mechanisms", "condition_aliases", "contradictions")

_NCT = re.compile(r"^NCT\d{8}$")
_PMID = re.compile(r"^PMID:\d+$")
_PAGE_READ = re.compile(r"\b(?:page|homepage) read\b")
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_MONDO = re.compile(r"^MONDO:\d{7}$")

_ENTRY_FIELDS = (
    "id",
    "name",
    "type",
    "url",
    "disease_ids",
    "retrieved",
    "curator",
    "notes",
)


class CuratedDataError(ValueError):
    """A curated entry breaks the rules in data/curated/README.md."""


def load_yaml(name: str, curated_dir: Path | None = None) -> JsonDict:
    path = (curated_dir or CURATED_DIR) / f"{name}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise CuratedDataError(f"{path} must contain a mapping at the top level")
    return data


def load_all(curated_dir: Path | None = None) -> JsonDict:
    """All curated files as one payload (what the pipeline passes to ``normalize``)."""
    return {name: load_yaml(name, curated_dir) for name in FILES}


def _require(
    entry: Mapping[str, Any],
    kind: str,
    fields: Sequence[str] = _ENTRY_FIELDS,
    *,
    slug_id: bool = True,
) -> None:
    missing = [key for key in fields if key != "disease_ids" and not entry.get(key)]
    if missing:
        raise CuratedDataError(f"{kind} entry {entry.get('id')!r} is missing {missing}")
    if not str(entry["url"]).startswith(("https://", "http://")):
        raise CuratedDataError(f"{kind} entry {entry['id']!r} url must be http(s)")
    if slug_id and "id" in fields and not _SLUG.fullmatch(str(entry["id"])):
        raise CuratedDataError(f"{kind} entry {entry['id']!r} id must be a kebab-case slug")
    if "disease_ids" in fields:
        disease_ids = entry.get("disease_ids")
        if not isinstance(disease_ids, Sequence) or isinstance(disease_ids, str) or not disease_ids:
            raise CuratedDataError(f"{kind} entry {entry['id']!r} needs non-empty disease_ids")
        invalid = [
            disease_id for disease_id in disease_ids if not _MONDO.fullmatch(str(disease_id))
        ]
        if invalid:
            raise CuratedDataError(
                f"{kind} entry {entry['id']!r} has invalid MONDO disease_ids {invalid}"
            )
    try:
        _retrieved(entry)
    except (TypeError, ValueError) as exc:
        raise CuratedDataError(
            f"{kind} entry {entry.get('id')!r} retrieved must be an ISO date"
        ) from exc


def _retrieved(entry: Mapping[str, Any]) -> datetime:
    value = entry["retrieved"]
    day = value if isinstance(value, date) else date.fromisoformat(str(value))
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


def _provenance(entry: Mapping[str, Any], record_id: str) -> Provenance:
    return Provenance(
        source=SOURCE,
        source_record_id=record_id,
        url=HttpUrl(str(entry["url"])),
        retrieved_at=_retrieved(entry),
        extractor=EXTRACTOR,
    )


def _base_attributes(entry: Mapping[str, Any]) -> dict[str, str]:
    attrs = {
        "url": str(entry["url"]),
        "curated_retrieved": str(entry["retrieved"]),
        "curator": clean_text(entry.get("curator")),
        "curated_notes": clean_text(entry.get("notes")),
    }
    return {key: value for key, value in attrs.items() if value}


def asset_node_id(entry: Mapping[str, Any]) -> tuple[str, NodeType]:
    record = str(entry.get("source_record_id") or "")
    if _NCT.match(record):
        return f"{STUDY_PREFIX}{record}", NodeType.STUDY
    if _PMID.match(record) and str(entry.get("type") or "").startswith("publication"):
        return record, NodeType.PUBLICATION
    return f"{ASSET_PREFIX}{entry['id']}", NodeType.ASSET


def _asset(entry: Mapping[str, Any]) -> tuple[Node, list[Edge]]:
    _require(entry, "asset", (*_ENTRY_FIELDS, "source_record_id"))
    node_id, node_type = asset_node_id(entry)
    attributes = _base_attributes(entry)
    attributes["asset_slug"] = str(entry["id"])
    attributes["asset_type"] = str(entry.get("type") or "unknown")
    for key, value in sorted((entry.get("attributes") or {}).items()):
        attributes[f"curated_{key}"] = str(value)
    node = Node(
        id=node_id,
        type=node_type,
        label=clean_text(entry["name"]),
        attributes=FrozenStrMap(attributes),
    )
    relation = (
        Relation.MENTIONS if node_type is NodeType.PUBLICATION else Relation.STUDIES_CONDITION
    )
    record_id = str(entry.get("source_record_id") or entry["id"])
    edges = [
        Edge(
            source_id=node_id,
            target_id=str(disease_id),
            relation=relation,
            provenance=_provenance(entry, record_id),
            confidence=CONFIDENCE_CURATED,
            evidence_type=EvidenceType.CURATED,
            qualifiers=FrozenStrMap({"asset_type": attributes["asset_type"]}),
            confidence_reasons=("team-curated with cited source 0.80 (needs human check)",),
        )
        for disease_id in entry.get("disease_ids") or []
    ]
    return node, edges


def _organization(
    entry: Mapping[str, Any], asset_ids: Mapping[str, str]
) -> tuple[Node, list[Edge]]:
    _require(entry, "organization", (*_ENTRY_FIELDS, "verified"))
    org_id = f"{ORG_PREFIX}{entry['id']}"
    org_type = str(entry.get("type") or "unknown")
    attributes = _base_attributes(entry)
    attributes["org_type"] = org_type
    if entry.get("verified"):
        attributes["verified"] = clean_text(entry["verified"])
    node = Node(
        id=org_id,
        type=NodeType.FUNDER if org_type in FUNDER_TYPES else NodeType.PATIENT_GROUP,
        label=clean_text(entry["name"]),
        attributes=FrozenStrMap(attributes),
    )
    page_read = bool(_PAGE_READ.search(str(entry.get("verified") or "")))
    confidence = CONFIDENCE_ORG_READ if page_read else CONFIDENCE_ORG_RESOLVES
    reason = (
        "org verified on its own site 0.60"
        if page_read
        else "org url resolves, scope page not read 0.50"
    )
    edges = [
        Edge(
            source_id=org_id,
            target_id=str(disease_id),
            relation=Relation.REPRESENTS,
            provenance=_provenance(entry, str(entry["id"])),
            confidence=confidence,
            evidence_type=EvidenceType.CURATED,
            qualifiers=FrozenStrMap(
                {"org_type": org_type, "verification": "page_read" if page_read else "url_resolves"}
            ),
            confidence_reasons=(reason,),
        )
        for disease_id in entry.get("disease_ids") or []
    ]
    for field_name, relation in (("funds", Relation.FUNDS), ("operates", Relation.OPERATES)):
        for slug in entry.get(field_name) or []:
            if slug not in asset_ids:
                raise CuratedDataError(
                    f"organization {entry['id']!r} {field_name} unknown {slug!r}"
                )
            edges.append(
                Edge(
                    source_id=org_id,
                    target_id=asset_ids[slug],
                    relation=relation,
                    provenance=_provenance(entry, f"{entry['id']}|{field_name}|{slug}"),
                    confidence=CONFIDENCE_CURATED,
                    evidence_type=EvidenceType.CURATED,
                    qualifiers=FrozenStrMap({"asset_slug": str(slug)}),
                    confidence_reasons=("team-curated with cited source 0.80 (needs human check)",),
                )
            )
    return node, edges


def _mechanism_check(mechanisms: Sequence[Mapping[str, Any]]) -> None:
    for item in mechanisms:
        _require(
            item,
            "mechanism",
            ("id", "name", "url", "retrieved", "curator", "notes"),
            slug_id=False,
        )
        if not re.match(r"^GO:\d{7}$", str(item["id"])):
            raise CuratedDataError(f"mechanism {item['id']!r} is not a GO id")


def mechanisms(payload: Mapping[str, Any]) -> list[JsonDict]:
    items = list((payload.get("mechanisms") or {}).get("mechanisms") or [])
    _mechanism_check(items)
    return items


def condition_aliases(payload: Mapping[str, Any]) -> list[JsonDict]:
    items = list((payload.get("condition_aliases") or {}).get("aliases") or [])
    for item in items:
        fields = ("name", "disease_id", "url", "retrieved", "curator", "notes")
        missing = [field for field in fields if not item.get(field)]
        if missing:
            raise CuratedDataError(f"condition alias {item!r} is missing {missing}")
        if not str(item["url"]).startswith(("https://", "http://")):
            raise CuratedDataError(f"condition alias {item['name']!r} url must be http(s)")
        if not _MONDO.fullmatch(str(item["disease_id"])):
            raise CuratedDataError(
                f"condition alias {item['name']!r} disease_id must be a MONDO id"
            )
        try:
            _retrieved(item)
        except (TypeError, ValueError) as exc:
            raise CuratedDataError(
                f"condition alias {item['name']!r} retrieved must be an ISO date"
            ) from exc
    return items


def _coverage_gaps(items: Sequence[Mapping[str, Any]]) -> list[JsonDict]:
    gaps: list[JsonDict] = []
    for item in items:
        missing = [field for field in ("disease_id", "name", "retrieved") if not item.get(field)]
        if missing:
            raise CuratedDataError(f"coverage gap {item.get('disease_id')!r} is missing {missing}")
        if not _MONDO.fullmatch(str(item["disease_id"])):
            raise CuratedDataError(f"coverage gap {item['disease_id']!r} must use a MONDO id")
        searched = item.get("searched")
        if not isinstance(searched, Sequence) or isinstance(searched, str) or not searched:
            raise CuratedDataError(f"coverage gap {item['disease_id']!r} needs non-empty searched")
        try:
            _retrieved(item)
        except (TypeError, ValueError) as exc:
            raise CuratedDataError(
                f"coverage gap {item['disease_id']!r} retrieved must be an ISO date"
            ) from exc
        gaps.append(
            {key: (str(value) if isinstance(value, date) else value) for key, value in item.items()}
        )
    return gaps


def _unique_ids(entries: Sequence[Mapping[str, Any]], kind: str) -> None:
    ids = [str(entry.get("id") or "") for entry in entries]
    duplicates = sorted({entry_id for entry_id in ids if entry_id and ids.count(entry_id) > 1})
    if duplicates:
        raise CuratedDataError(f"duplicate {kind} ids: {duplicates}")


def normalize(payload: Mapping[str, Any]) -> IngestResult:
    """Org/asset nodes and their edges; coverage seeds go to ``notes``."""
    orgs_doc = payload.get("organizations") or {}
    assets = list((payload.get("assets") or {}).get("assets") or [])
    organizations = list(orgs_doc.get("organizations") or [])
    _unique_ids(assets, "asset")
    _unique_ids(organizations, "organization")
    asset_ids = {str(entry["id"]): asset_node_id(entry)[0] for entry in assets}
    nodes: list[Node] = []
    edges: list[Edge] = []
    for entry in assets:
        node, asset_edges = _asset(entry)
        nodes.append(node)
        edges.extend(asset_edges)
    for entry in organizations:
        node, org_edges = _organization(entry, asset_ids)
        nodes.append(node)
        edges.extend(org_edges)
    _mechanism_check(mechanisms(payload))
    condition_aliases(payload)
    gaps = _coverage_gaps(list(orgs_doc.get("no_dedicated_org_found") or []))
    dates = sorted(str(entry["retrieved"]) for entry in [*assets, *organizations])
    return IngestResult(
        source=SOURCE,
        source_version=None,
        retrieved_at=f"{dates[-1]}T00:00:00Z" if dates else "1970-01-01T00:00:00Z",
        nodes=merge_nodes(nodes),
        edges=dedupe_edges(edges),
        notes={
            "records": len(assets) + len(organizations),
            "no_dedicated_org_found": gaps,
        },
    )
