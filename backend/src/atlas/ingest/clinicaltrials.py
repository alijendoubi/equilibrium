"""ClinicalTrials.gov API v2: studies for the slice's conditions and interventions.

A bounded set of queries (``QUERIES``) plus the verified seed NCT ids. Each study becomes a
``study`` node ``clinicaltrials:NCT...`` with registry fields in ``attributes``. Its
``conditions`` strings are mapped to slice diseases by normalized MONDO label/synonym (from the
Monarch connector) or a curated alias (``data/curated/condition_aliases.yaml``). Unmapped
conditions are reported in the notes, never guessed. Studies with no mapped condition are
dropped and listed in the notes, except the verified seed trials, which are always kept.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
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
from atlas.ingest.seeds import SEED_DISEASES, SEED_TRIALS
from atlas.models.evidence import (
    Edge,
    EvidenceType,
    FrozenStrMap,
    Node,
    NodeType,
    Provenance,
    Relation,
)

SOURCE = "clinicaltrials"
EXTRACTOR = "ingest:clinicaltrials"
API = "https://clinicaltrials.gov/api/v2"
STUDY_URL = "https://clinicaltrials.gov/study/{nct}"
NODE_PREFIX = "clinicaltrials:"
MIN_INTERVAL_S = 1.3  # about 50 requests/minute
PAGE_SIZE = 100
SUMMARY_MAX = 400
CONFIDENCE_RECORD = 0.75
CONFIDENCE_ALIAS = 0.65

# (name, params, max studies). Bounded on purpose: this is a slice, not a mirror.
QUERIES: tuple[tuple[str, dict[str, str], int], ...] = (
    ("gaucher", {"query.cond": "Gaucher Disease"}, 200),
    ("saposin_c", {"query.cond": "saposin C deficiency"}, 20),
    ("prosaposin", {"query.cond": "prosaposin deficiency"}, 20),
    ("pd_gba", {"query.cond": "Parkinson Disease", "query.term": "GBA OR GBA1"}, 100),
    ("lbd_gba", {"query.cond": "Lewy Body Disease", "query.term": "GBA OR GBA1"}, 30),
    ("ambroxol", {"query.intr": "ambroxol"}, 50),
    ("venglustat", {"query.intr": "venglustat"}, 50),
    ("pr001", {"query.intr": "LY3884961 OR PR001"}, 20),
    (
        "niemann_pick_ab",
        {"query.cond": "Niemann-Pick Disease, Type A OR Niemann-Pick Disease, Type B"},
        50,
    ),
    ("amrf", {"query.cond": "action myoclonus renal failure"}, 20),
    ("kufor_rakeb", {"query.cond": "Kufor-Rakeb syndrome"}, 20),
    ("cln10", {"query.cond": "CLN10 OR neuronal ceroid lipofuscinosis 10"}, 20),
    ("spg46", {"query.cond": "spastic paraplegia 46"}, 20),
)

_ROMAN = {"i": "1", "ii": "2", "iii": "3", "iv": "4"}
_TOKEN = re.compile(r"[a-z0-9]+")


def normalize_name(value: str) -> str:
    """Lowercase, drop possessive 's, split on punctuation, Roman type numerals to digits."""
    text = value.casefold().replace("'s", "").replace("’s", "")
    return " ".join(_ROMAN.get(token, token) for token in _TOKEN.findall(text))


# --------------------------------------------------------------------------------------------
# fetch
# --------------------------------------------------------------------------------------------


def _trim(study: Mapping[str, Any]) -> JsonDict:
    """Keep the registry fields we show; everything else stays on clinicaltrials.gov."""
    p = study.get("protocolSection") or {}
    ident = p.get("identificationModule") or {}
    status = p.get("statusModule") or {}
    design = p.get("designModule") or {}
    enrollment = design.get("enrollmentInfo") or {}
    arms = p.get("armsInterventionsModule") or {}
    sponsor = (p.get("sponsorCollaboratorsModule") or {}).get("leadSponsor") or {}
    return {
        "nct_id": ident.get("nctId"),
        "brief_title": ident.get("briefTitle"),
        "acronym": ident.get("acronym"),
        "status": status.get("overallStatus"),
        "why_stopped": status.get("whyStopped"),
        "start_date": (status.get("startDateStruct") or {}).get("date"),
        "primary_completion": (status.get("primaryCompletionDateStruct") or {}).get("date"),
        "phases": design.get("phases") or [],
        "study_type": design.get("studyType"),
        "enrollment": enrollment.get("count"),
        "enrollment_type": enrollment.get("type"),
        "conditions": (p.get("conditionsModule") or {}).get("conditions") or [],
        "interventions": [
            {"type": i.get("type"), "name": i.get("name")} for i in arms.get("interventions") or []
        ],
        "sponsor": sponsor.get("name"),
        "has_results": bool(study.get("hasResults")),
        "brief_summary": clean_text(
            (p.get("descriptionModule") or {}).get("briefSummary"), SUMMARY_MAX
        ),
    }


def search(client: PoliteClient, params: Mapping[str, str], limit: int) -> list[JsonDict]:
    studies: list[JsonDict] = []
    token: str | None = None
    while len(studies) < limit:
        query = {**params, "pageSize": str(min(PAGE_SIZE, limit)), "format": "json"}
        if token:
            query["pageToken"] = token
        page = client.get_json(f"{API}/studies", params=query)
        studies.extend(_trim(s) for s in page.get("studies") or [])
        token = page.get("nextPageToken")
        if not token:
            break
    return studies[:limit]


def fetch(client: PoliteClient) -> JsonDict:
    """Run the bounded queries and the seed-NCT lookups; returns studies keyed by NCT id."""
    version_info = client.get_json(f"{API}/version")
    version = version_info.get("dataTimestamp")
    studies: dict[str, JsonDict] = {}
    matched: dict[str, set[str]] = {}
    query_counts: dict[str, int] = {}
    for name, params, limit in QUERIES:
        found = search(client, params, limit)
        query_counts[name] = len(found)
        for study in found:
            nct = str(study["nct_id"])
            studies.setdefault(nct, study)
            matched.setdefault(nct, set()).add(name)
    for nct in SEED_TRIALS:
        if nct not in studies:
            studies[nct] = _trim(client.get_json(f"{API}/studies/{nct}"))
        matched.setdefault(nct, set()).add("seed")
    for nct, study in studies.items():
        study["matched_queries"] = sorted(matched.get(nct, set()))
    return {
        "meta": make_meta(f"{API}/studies", f"ctgov data {version}" if version else None),
        "queries": [{"name": n, "params": p, "limit": lim} for n, p, lim in QUERIES],
        "query_counts": query_counts,
        "studies": dict(sorted(studies.items())),
    }


# --------------------------------------------------------------------------------------------
# normalize
# --------------------------------------------------------------------------------------------


def build_condition_index(
    disease_nodes: Iterable[Node], aliases: Sequence[Mapping[str, Any]]
) -> dict[str, tuple[str, str]]:
    """normalized name -> (MONDO id, match kind). Labels win; ambiguous synonyms are dropped."""
    seeds = [node for node in disease_nodes if node.id in SEED_DISEASES]
    index: dict[str, tuple[str, str]] = {}
    for node in seeds:
        index.setdefault(normalize_name(node.label), (node.id, "label"))
    synonym_targets: dict[str, set[str]] = {}
    for node in seeds:
        for synonym in node.synonyms:
            synonym_targets.setdefault(normalize_name(synonym), set()).add(node.id)
    for name, targets in synonym_targets.items():
        if name not in index and len(targets) == 1:
            index[name] = (next(iter(targets)), "synonym")
    for alias in aliases:
        index.setdefault(normalize_name(str(alias["name"])), (str(alias["disease_id"]), "alias"))
    return index


def _attributes(study: Mapping[str, Any]) -> dict[str, str]:
    nct = str(study["nct_id"])
    values: dict[str, object] = {
        "nct_id": nct,
        "url": STUDY_URL.format(nct=nct),
        "acronym": study.get("acronym"),
        "status": study.get("status"),
        "why_stopped": study.get("why_stopped"),
        "phase": "/".join(p.replace("PHASE", "") for p in study.get("phases") or []) or None,
        "study_type": study.get("study_type"),
        "enrollment": study.get("enrollment"),
        "enrollment_type": study.get("enrollment_type"),
        "conditions": "; ".join(study.get("conditions") or []),
        "interventions": "; ".join(
            str(i.get("name")) for i in study.get("interventions") or [] if i.get("name")
        ),
        "intervention_types": "; ".join(
            sorted({str(i.get("type")) for i in study.get("interventions") or [] if i.get("type")})
        ),
        "sponsor": study.get("sponsor"),
        "start_date": study.get("start_date"),
        "primary_completion": study.get("primary_completion"),
        "has_results": "true" if study.get("has_results") else "false",
        "matched_queries": ",".join(study.get("matched_queries") or []),
        "description": study.get("brief_summary"),
    }
    return {key: str(value) for key, value in values.items() if value not in (None, "")}


def study_node(study: Mapping[str, Any]) -> Node:
    nct = str(study["nct_id"])
    acronym = clean_text(study.get("acronym"))
    return Node(
        id=f"{NODE_PREFIX}{nct}",
        type=NodeType.STUDY,
        label=clean_text(study.get("brief_title")) or nct,
        synonyms=tuple(s for s in (acronym, nct) if s),
        attributes=FrozenStrMap(_attributes(study)),
    )


def normalize(
    payload: Mapping[str, Any],
    disease_nodes: Iterable[Node],
    aliases: Sequence[Mapping[str, Any]] = (),
) -> IngestResult:
    """Study nodes and ``studies_condition`` edges for conditions that map to slice diseases."""
    meta = payload["meta"]
    retrieved_at = parse_time(str(meta["retrieved_at"]))
    version = meta.get("source_version")
    index = build_condition_index(disease_nodes, aliases)
    nodes: list[Node] = []
    edges: list[Edge] = []
    unmapped: dict[str, int] = {}
    dropped: list[str] = []
    for nct, study in sorted((payload.get("studies") or {}).items()):
        study_edges: list[Edge] = []
        for condition in study.get("conditions") or []:
            hit = index.get(normalize_name(str(condition)))
            if hit is None:
                unmapped[str(condition)] = unmapped.get(str(condition), 0) + 1
                continue
            disease_id, kind = hit
            alias = kind == "alias"
            study_edges.append(
                Edge(
                    source_id=f"{NODE_PREFIX}{nct}",
                    target_id=disease_id,
                    relation=Relation.STUDIES_CONDITION,
                    provenance=Provenance(
                        source=SOURCE,
                        source_record_id=nct,
                        url=HttpUrl(STUDY_URL.format(nct=nct)),
                        retrieved_at=retrieved_at,
                        source_version=version,
                        extractor=EXTRACTOR,
                    ),
                    confidence=CONFIDENCE_ALIAS if alias else CONFIDENCE_RECORD,
                    evidence_type=EvidenceType.OBSERVED,
                    qualifiers=FrozenStrMap(
                        {
                            "registry_condition": clean_text(condition),
                            "condition_match": kind,
                            **({"status": str(study["status"])} if study.get("status") else {}),
                        }
                    ),
                    confidence_reasons=(
                        ("ClinicalTrials.gov record 0.75", "-0.10 condition mapped by alias")
                        if alias
                        else ("ClinicalTrials.gov record 0.75",)
                    ),
                )
            )
        if not study_edges and "seed" not in (study.get("matched_queries") or []):
            dropped.append(nct)
            continue
        nodes.append(study_node(study))
        edges.extend(study_edges)
    return IngestResult(
        source=SOURCE,
        source_version=version,
        retrieved_at=str(meta["retrieved_at"]),
        nodes=merge_nodes(nodes),
        edges=dedupe_edges(edges),
        notes={
            "records": len(payload.get("studies") or {}),
            "query_counts": dict(payload.get("query_counts") or {}),
            "unmapped_conditions": dict(sorted(unmapped.items())),
            "dropped_studies_without_slice_condition": dropped,
        },
    )
