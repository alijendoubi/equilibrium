"""Curated contradictions (``data/curated/contradictions.yaml``) -> ``contradicts`` edges.

Each entry becomes one curated ``contradicts`` edge between two nodes (for example two trials
of the same drug with opposite outcomes, or a replication letter and the disease it disputes).
The edges an entry ``bears_on`` are the disputed claims: each gets the ``contradicts`` edge id
in ``contradicted_by`` (and the rubric penalty), and the ``contradicts`` edge lists them back,
so the link can be followed from either side.

``bears_on`` items are either ``{edge_id: E:...}`` or ``{source_id, relation, target_id}``
(every edge with that triple, from any source). An item that matches nothing is an error:
the contradiction would silently stop applying after a data change.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any

from pydantic import HttpUrl

from atlas.ingest.common import clean_text
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
EXTRACTOR = "curated:contradictions"
VERIFICATION_VALUES = frozenset({"verified", "unverified"})
_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_EDGE_ID = re.compile(r"^E:[0-9a-f]{16}$")


class ContradictionError(ValueError):
    """An entry in contradictions.yaml breaks the rules in data/curated/README.md."""


@dataclass(frozen=True)
class Evidence:
    url: str
    quote: str
    retrieved: date


@dataclass(frozen=True)
class Contradiction:
    id: str
    summary: str
    verification: str
    source_id: str
    target_id: str
    bears_on: tuple[Mapping[str, str], ...]
    evidence: tuple[Evidence, ...]
    curator: str
    notes: str
    new_nodes: tuple[Node, ...]


def _fail(entry_id: object, problem: str) -> ContradictionError:
    return ContradictionError(f"contradiction {entry_id!r}: {problem}")


def _day(entry_id: str, value: object) -> date:
    try:
        return value if isinstance(value, date) else date.fromisoformat(str(value))
    except ValueError as exc:
        raise _fail(entry_id, f"bad retrieved date {value!r}") from exc


def _evidence(entry_id: str, items: object) -> tuple[Evidence, ...]:
    if not isinstance(items, list) or not items:
        raise _fail(entry_id, "needs at least one evidence item")
    parsed: list[Evidence] = []
    for item in items:
        url = str((item or {}).get("url") or "")
        if not url.startswith(("https://", "http://")):
            raise _fail(entry_id, "every evidence item needs an http(s) url")
        quote = clean_text(item.get("quote"))
        if not quote or not item.get("retrieved"):
            raise _fail(entry_id, "every evidence item needs a quote and a retrieved date")
        parsed.append(Evidence(url, quote, _day(entry_id, item["retrieved"])))
    return tuple(parsed)


def _bears_on(entry_id: str, items: object) -> tuple[Mapping[str, str], ...]:
    parsed: list[Mapping[str, str]] = []
    for item in items or []:  # type: ignore[attr-defined]
        if not isinstance(item, Mapping):
            raise _fail(entry_id, "bears_on items must be mappings")
        if "edge_id" in item:
            if not _EDGE_ID.match(str(item["edge_id"])):
                raise _fail(entry_id, f"bad edge id {item['edge_id']!r}")
            parsed.append({"edge_id": str(item["edge_id"])})
            continue
        keys = ("source_id", "relation", "target_id")
        if any(not item.get(key) for key in keys):
            raise _fail(entry_id, "bears_on needs edge_id or source_id/relation/target_id")
        try:
            Relation(str(item["relation"]))
        except ValueError as exc:
            raise _fail(entry_id, f"unknown relation {item['relation']!r}") from exc
        parsed.append({key: str(item[key]) for key in keys})
    return tuple(parsed)


def _new_nodes(entry_id: str, items: object) -> tuple[Node, ...]:
    nodes: list[Node] = []
    for item in items or []:  # type: ignore[attr-defined]
        url = str(item.get("url") or "")
        if not url.startswith(("https://", "http://")):
            raise _fail(entry_id, f"new node {item.get('id')!r} needs an http(s) url")
        try:
            nodes.append(
                Node(
                    id=str(item["id"]),
                    type=NodeType(str(item["type"])),
                    label=clean_text(item["label"]),
                    xrefs=(str(item["id"]),) if str(item["id"]).startswith("PMID:") else (),
                    attributes=FrozenStrMap({"url": url, "curated_by": entry_id}),
                )
            )
        except (KeyError, ValueError) as exc:
            raise _fail(entry_id, f"bad new node: {exc}") from exc
    return tuple(nodes)


def parse(document: Mapping[str, Any] | None) -> tuple[Contradiction, ...]:
    """Validate the YAML document; raises ContradictionError on the first broken entry."""
    entries = (document or {}).get("contradictions") or []
    seen: set[str] = set()
    parsed: list[Contradiction] = []
    for entry in entries:
        entry_id = str(entry.get("id") or "")
        if not _ID.match(entry_id) or entry_id in seen:
            raise _fail(entry_id, "id must be a unique kebab-case slug")
        seen.add(entry_id)
        verification = str(entry.get("verification") or "")
        if verification not in VERIFICATION_VALUES:
            raise _fail(entry_id, f"verification must be one of {sorted(VERIFICATION_VALUES)}")
        edge = entry.get("contradicts") or {}
        if not edge.get("source_id") or not edge.get("target_id"):
            raise _fail(entry_id, "contradicts needs source_id and target_id")
        for key in ("summary", "curator"):
            if not clean_text(entry.get(key)):
                raise _fail(entry_id, f"missing {key}")
        parsed.append(
            Contradiction(
                id=entry_id,
                summary=clean_text(entry["summary"]),
                verification=verification,
                source_id=str(edge["source_id"]),
                target_id=str(edge["target_id"]),
                bears_on=_bears_on(entry_id, entry.get("bears_on")),
                evidence=_evidence(entry_id, entry.get("evidence")),
                curator=clean_text(entry["curator"]),
                notes=clean_text(entry.get("notes")),
                new_nodes=_new_nodes(entry_id, entry.get("new_nodes")),
            )
        )
    return tuple(parsed)


def contradicts_edge(item: Contradiction, disputed: Sequence[str] = ()) -> Edge:
    first = item.evidence[0]
    qualifiers = {
        "contradiction_id": item.id,
        "summary": item.summary,
        "verification": item.verification,
        "evidence_urls": " ".join(e.url for e in item.evidence),
        "curator": item.curator,
    }
    if item.notes:
        qualifiers["notes"] = item.notes
    return Edge(
        source_id=item.source_id,
        target_id=item.target_id,
        relation=Relation.CONTRADICTS,
        provenance=Provenance(
            source=SOURCE,
            source_record_id=f"contradiction:{item.id}",
            url=HttpUrl(first.url),
            retrieved_at=datetime.combine(max(e.retrieved for e in item.evidence), time(), UTC),
            evidence_quote=" | ".join(e.quote for e in item.evidence),
            extractor=EXTRACTOR,
        ),
        confidence=0.5,
        evidence_type=EvidenceType.CURATED,
        contradicted_by=tuple(sorted(disputed)),
        qualifiers=FrozenStrMap(qualifiers),
        confidence_reasons=("curated contradiction (scored by the trust rubric)",),
    )


def _matches(edge: Edge, selector: Mapping[str, str]) -> bool:
    if "edge_id" in selector:
        return edge.id == selector["edge_id"]
    return (edge.source_id, edge.relation.value, edge.target_id) == (
        selector["source_id"],
        selector["relation"],
        selector["target_id"],
    )


def apply(
    items: Sequence[Contradiction], nodes: Iterable[Node], edges: Iterable[Edge]
) -> tuple[tuple[Node, ...], tuple[Edge, ...]]:
    """Add the new nodes and ``contradicts`` edges; fill ``contradicted_by`` both ways."""
    node_list = list(nodes)
    edge_list = list(edges)
    added_nodes = [n for item in items for n in item.new_nodes]
    known = {n.id for n in (*node_list, *added_nodes)}
    disputes: dict[str, set[str]] = {}
    new_edges: list[Edge] = []
    for item in items:
        for endpoint in (item.source_id, item.target_id):
            if endpoint not in known:
                raise _fail(item.id, f"unknown node {endpoint}")
        disputed = sorted(
            {e.id for selector in item.bears_on for e in edge_list if _matches(e, selector)}
        )
        for selector in item.bears_on:
            if not any(_matches(e, selector) for e in edge_list):
                raise _fail(item.id, f"bears_on {dict(selector)} matches no edge")
        edge = contradicts_edge(item, disputed)
        new_edges.append(edge)
        for edge_id in disputed:
            disputes.setdefault(edge_id, set()).add(edge.id)
    updated = [
        e.model_copy(
            update={"contradicted_by": tuple(sorted({*e.contradicted_by, *disputes[e.id]}))}
        )
        if e.id in disputes
        else e
        for e in edge_list
    ]
    return (*node_list, *added_nodes), (*updated, *new_edges)
