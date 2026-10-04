"""NIH RePORTER API v2: funded projects and investigators for the slice's genes and diseases.

``fetch`` POSTs a bounded set of text searches (``QUERIES``) to
``https://api.reporter.nih.gov/v2/projects/search`` (fiscal years ``FISCAL_YEARS``, about one
request per second), keeps one record per core project (the latest fiscal year), caps the
total at ``MAX_PROJECTS`` and stores only the fields the normalizer needs.

``normalize`` turns the payload into:

* ``investigator`` nodes ``investigator:<profile_id>`` (label = PI name; attributes: latest
  organization, city/state/country, project count);
* ``funder`` nodes ``funder:reporter-<ic>`` for the administering institute (NIH ICs, and VA
  for VA-funded records RePORTER also lists);
* observed ``investigates`` edges investigator -> seed gene/disease, one per pair, backed by
  the PI's latest matching project (``source_record_id`` = project number, url =
  ``https://reporter.nih.gov/project-details/<appl_id>``);
* observed ``funds`` edges funder -> investigator, backed by the same kind of project record.

A project is linked to the targets of the queries that returned it (RePORTER searched its title,
terms and abstract). Queries with no target (``ambroxol``) only add projects to the counts.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
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
from atlas.models.evidence import (
    Edge,
    EvidenceType,
    FrozenStrMap,
    Node,
    NodeType,
    Provenance,
    Relation,
)

SOURCE = "reporter"
EXTRACTOR = "ingest:reporter"
API = "https://api.reporter.nih.gov/v2/projects/search"
PROJECT_URL = "https://reporter.nih.gov/project-details/{appl_id}"
INVESTIGATOR_PREFIX = "investigator:"
FUNDER_PREFIX = "funder:reporter-"
MIN_INTERVAL_S = 1.0
PAGE_SIZE = 100
PER_QUERY_MAX = 200
MAX_PROJECTS = 150
FISCAL_YEARS: tuple[int, ...] = tuple(range(2019, 2027))
TITLE_MAX = 200
INCLUDE_FIELDS = (
    "ApplId",
    "ProjectNum",
    "CoreProjectNum",
    "ProjectTitle",
    "FiscalYear",
    "PrincipalInvestigators",
    "Organization",
    "AgencyIcAdmin",
)

# (name, search text, target node ids), most specific first: the cap keeps every hit of the
# small queries and fills the rest from the broad ones. Phrases are quoted so RePORTER does not
# split "LIMP2"; "PSAP" alone is not queried (it also names an unrelated mitochondrial protein).
QUERIES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("saposin_c_deficiency", '"saposin C deficiency"', ("MONDO:0012517",)),
    ("scarb2", "SCARB2", ("HGNC:1665",)),
    ("limp2", '"LIMP2"', ("HGNC:1665",)),
    ("prosaposin", "prosaposin", ("HGNC:9498",)),
    ("gba_parkinson", "GBA Parkinson", ("HGNC:4177", "MONDO:0008199")),
    ("ambroxol", "ambroxol", ()),
    ("gba1", "GBA1", ("HGNC:4177",)),
    ("gaucher", "Gaucher", ("MONDO:0018150",)),
    ("glucocerebrosidase", "glucocerebrosidase", ("HGNC:4177",)),
)
QUERY_TARGETS: Mapping[str, tuple[str, ...]] = {name: targets for name, _, targets in QUERIES}

_SLUG = re.compile(r"[^a-z0-9]+")


# --------------------------------------------------------------------------------------------
# fetch
# --------------------------------------------------------------------------------------------


def _body(text: str, offset: int, limit: int) -> JsonDict:
    return {
        "criteria": {
            "advanced_text_search": {
                "operator": "and",
                "search_field": "projecttitle,terms,abstracttext",
                "search_text": text,
            },
            "fiscal_years": list(FISCAL_YEARS),
        },
        "include_fields": list(INCLUDE_FIELDS),
        "sort_field": "fiscal_year",
        "sort_order": "desc",
        "offset": offset,
        "limit": limit,
    }


def _trim(project: Mapping[str, Any]) -> JsonDict:
    org = project.get("organization") or {}
    ic = project.get("agency_ic_admin") or {}
    return {
        "appl_id": project.get("appl_id"),
        "project_num": project.get("project_num"),
        "core_project_num": project.get("core_project_num") or project.get("project_num"),
        "title": clean_text(project.get("project_title"), TITLE_MAX),
        "fiscal_year": project.get("fiscal_year"),
        "organization": {
            "name": clean_text(org.get("org_name")),
            "city": clean_text(org.get("org_city")),
            "state": clean_text(org.get("org_state")),
            "country": clean_text(org.get("org_country")),
        },
        "ic": {
            "abbreviation": clean_text(ic.get("abbreviation")),
            "name": clean_text(ic.get("name")),
        },
        "investigators": [
            {
                "profile_id": pi.get("profile_id"),
                "name": clean_text(pi.get("full_name")),
                "is_contact_pi": bool(pi.get("is_contact_pi")),
            }
            for pi in project.get("principal_investigators") or []
            if pi.get("profile_id")
        ],
    }


def _newer(candidate: Mapping[str, Any], current: Mapping[str, Any]) -> bool:
    return (candidate["fiscal_year"] or 0, candidate["appl_id"] or 0) > (
        current["fiscal_year"] or 0,
        current["appl_id"] or 0,
    )


def collect(results: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, JsonDict]:
    """One record per core project (latest fiscal year), with the queries that matched it.

    Deterministic: query order, then fiscal year desc, then project number; capped at
    ``MAX_PROJECTS``.
    """
    projects: dict[str, JsonDict] = {}
    for name, _, _ in QUERIES:
        for raw in results.get(name) or ():
            item = _trim(raw)
            core = str(item["core_project_num"] or "")
            if not core or not item["appl_id"]:
                continue
            current = projects.get(core)
            matched = sorted({name, *(current or {}).get("matched_queries", [])})
            if current is None and len(projects) >= MAX_PROJECTS:
                continue
            if current is None or _newer(item, current):
                projects[core] = {**item, "matched_queries": matched}
            else:
                projects[core] = {**current, "matched_queries": matched}
    return dict(sorted(projects.items()))


def search(client: PoliteClient, text: str) -> tuple[list[JsonDict], int]:
    """Newest-first records for one text search, up to ``PER_QUERY_MAX``; plus the API total."""
    found: list[JsonDict] = []
    total = 0
    while len(found) < PER_QUERY_MAX:
        data = client.post_json(API, _body(text, len(found), PAGE_SIZE))
        page = list(data.get("results") or [])
        total = int((data.get("meta") or {}).get("total") or 0)
        found.extend(page)
        if len(page) < PAGE_SIZE or len(found) >= total:
            break
    return found[:PER_QUERY_MAX], total


def fetch(client: PoliteClient) -> JsonDict:
    """Run every query and build the compact payload."""
    results: dict[str, list[JsonDict]] = {}
    totals: dict[str, int] = {}
    for name, text, _ in QUERIES:
        results[name], totals[name] = search(client, text)
    projects = collect(results)
    return {
        "meta": make_meta(API, f"fiscal years {FISCAL_YEARS[0]}-{FISCAL_YEARS[-1]}"),
        "query_text": {name: text for name, text, _ in QUERIES},
        "query_totals": totals,
        "query_returned": {name: len(items) for name, items in results.items()},
        "projects": projects,
    }


# --------------------------------------------------------------------------------------------
# normalize
# --------------------------------------------------------------------------------------------


def investigator_id(profile_id: object) -> str:
    return f"{INVESTIGATOR_PREFIX}{profile_id}"


def funder_id(abbreviation: str) -> str:
    return f"{FUNDER_PREFIX}{_SLUG.sub('-', abbreviation.casefold()).strip('-')}"


def _latest_first(projects: Mapping[str, JsonDict]) -> list[JsonDict]:
    return sorted(
        projects.values(),
        key=lambda p: (-(p["fiscal_year"] or 0), str(p["project_num"])),
    )


def _provenance(project: Mapping[str, Any], retrieved: str, version: str | None) -> Provenance:
    return Provenance(
        source=SOURCE,
        source_record_id=str(project["project_num"]),
        url=HttpUrl(PROJECT_URL.format(appl_id=project["appl_id"])),
        retrieved_at=parse_time(retrieved),
        source_version=version,
        extractor=EXTRACTOR,
    )


def _investigator_node(profile_id: str, items: Sequence[tuple[JsonDict, JsonDict]]) -> Node:
    project, pi = items[0]
    org = project["organization"]
    attributes = {
        "reporter_profile_id": profile_id,
        "organization": org.get("name") or "",
        "institution": org.get("name") or "",
        "city": org.get("city") or "",
        "state": org.get("state") or "",
        "country": org.get("country") or "",
        "projects": str(len({p["core_project_num"] for p, _ in items})),
        "latest_fiscal_year": str(project["fiscal_year"] or ""),
    }
    return Node(
        id=investigator_id(profile_id),
        type=NodeType.INVESTIGATOR,
        label=pi["name"] or investigator_id(profile_id),
        attributes=FrozenStrMap({k: v for k, v in attributes.items() if v}),
    )


def normalize(payload: Mapping[str, Any], known_nodes: Sequence[str] = ()) -> IngestResult:
    """Investigator/funder nodes and observed ``investigates`` / ``funds`` edges.

    ``known_nodes`` (when given) limits targets to nodes present in the graph, so an edge never
    dangles; targets dropped this way are listed in the notes.
    """
    meta = payload["meta"]
    retrieved = str(meta["retrieved_at"])
    version = meta.get("source_version")
    known = frozenset(known_nodes)
    projects = _latest_first(payload.get("projects") or {})
    by_pi: dict[str, list[tuple[JsonDict, JsonDict]]] = defaultdict(list)
    for project in projects:
        for pi in project["investigators"]:
            by_pi[str(pi["profile_id"])].append((project, pi))
    nodes: list[Node] = []
    edges: list[Edge] = []
    target_projects: dict[str, set[str]] = defaultdict(set)
    skipped: set[str] = set()
    for profile_id, items in sorted(by_pi.items()):
        nodes.append(_investigator_node(profile_id, items))
        pi_node = investigator_id(profile_id)
        linked: dict[str, list[JsonDict]] = defaultdict(list)
        for project, _ in items:
            for query in project["matched_queries"]:
                for target in QUERY_TARGETS.get(query, ()):
                    if known and target not in known:
                        skipped.add(target)
                        continue
                    linked[target].append(project)
                    target_projects[target].add(str(project["core_project_num"]))
        for target, matched in sorted(linked.items()):
            latest = matched[0]
            numbers = sorted({str(p["core_project_num"]) for p in matched})
            edges.append(
                Edge(
                    source_id=pi_node,
                    target_id=target,
                    relation=Relation.INVESTIGATES,
                    provenance=_provenance(latest, retrieved, version),
                    confidence=0.75,
                    evidence_type=EvidenceType.OBSERVED,
                    qualifiers=FrozenStrMap(
                        {
                            "projects": ",".join(numbers[:5]),
                            "project_count": str(len(numbers)),
                            "matched_queries": ",".join(
                                sorted({q for p in matched for q in p["matched_queries"]})
                            ),
                            "latest_title": str(latest["title"]),
                        }
                    ),
                    confidence_reasons=("NIH RePORTER project record 0.75",),
                )
            )
        latest_project = items[0][0]
        ic = latest_project["ic"]
        if ic.get("abbreviation"):
            funder = funder_id(ic["abbreviation"])
            nodes.append(
                Node(
                    id=funder,
                    type=NodeType.FUNDER,
                    label=ic.get("name") or ic["abbreviation"],
                    attributes=FrozenStrMap(
                        {"abbreviation": ic["abbreviation"], "via": "NIH RePORTER"}
                    ),
                )
            )
            edges.append(
                Edge(
                    source_id=funder,
                    target_id=pi_node,
                    relation=Relation.FUNDS,
                    provenance=_provenance(latest_project, retrieved, version),
                    confidence=0.75,
                    evidence_type=EvidenceType.OBSERVED,
                    qualifiers=FrozenStrMap({"project_num": str(latest_project["project_num"])}),
                    confidence_reasons=("NIH RePORTER project record 0.75",),
                )
            )
    return IngestResult(
        source=SOURCE,
        source_version=version,
        retrieved_at=retrieved,
        nodes=merge_nodes(nodes),
        edges=dedupe_edges(edges),
        notes={
            "records": len(projects),
            "url": meta.get("url"),
            "query_totals": dict(payload.get("query_totals") or {}),
            "projects_by_target": {k: len(v) for k, v in sorted(target_projects.items())},
            "targets_not_in_graph": sorted(skipped),
        },
    )
