"""HPO phenotype information content (IC) from the whole ``phenotype.hpoa`` corpus.

IC(t) = -ln(n(t) / N), where N is the number of diseases with at least one phenotype annotation
and n(t) is the number of those diseases annotated to t *or any descendant of t* (annotations
are propagated up the ``is_a`` hierarchy of ``hp.obo``). NOT-qualified annotations are ignored.
A term with no annotated disease gets the maximum IC, -ln(1 / N).

The full release files (about 60 MB) go to ``data/raw/hpo/`` (gitignored). Only the IC map for
the phenotypes used in the slice is committed, in ``data/cache/hpo/ic.json``.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from atlas.ingest.common import (
    RAW_DIR,
    IngestResult,
    JsonDict,
    PoliteClient,
    make_meta,
    merge_nodes,
)
from atlas.models.evidence import FrozenStrMap, Node, NodeType

SOURCE = "hpo"
RELEASE = "https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download"
HPOA_URL = f"{RELEASE}/phenotype.hpoa"
OBO_URL = f"{RELEASE}/hp.obo"
IC_METHOD = "-ln(diseases annotated to term or descendants / all annotated diseases), hpoa"
IC_DECIMALS = 4

_VERSION_RE = re.compile(r"^#(?:version|date):\s*(\S+)")
_DATA_VERSION_RE = re.compile(r"^data-version:\s*(\S+)")


def download(client: PoliteClient, url: str, target: Path) -> Path:
    """Download ``url`` to ``target`` unless it already exists (raw files are never committed)."""
    if target.is_file() and target.stat().st_size > 0:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(client.get(url).content)
    return target


def parse_obo(lines: Iterable[str]) -> tuple[dict[str, str], dict[str, set[str]], dict[str, str]]:
    """Return (names, is_a parents, alt_id -> primary id) for non-obsolete HP terms."""
    names: dict[str, str] = {}
    parents: dict[str, set[str]] = defaultdict(set)
    alt_ids: dict[str, str] = {}
    current: str | None = None
    obsolete = False
    in_term = False

    def close() -> None:
        if current and obsolete:
            names.pop(current, None)
            parents.pop(current, None)

    for raw in lines:
        line = raw.strip()
        if line.startswith("["):
            close()
            in_term = line == "[Term]"
            current, obsolete = None, False
            continue
        if not in_term or ":" not in line:
            continue
        key, _, value = line.partition(": ")
        if key == "id":
            current = value
        elif current is None:
            continue
        elif key == "name":
            names[current] = value
        elif key == "is_a":
            parents[current].add(value.split(" ! ")[0].strip())
        elif key == "alt_id":
            alt_ids[value] = current
        elif key == "is_obsolete" and value == "true":
            obsolete = True
    close()
    return names, dict(parents), alt_ids


def ancestors_of(
    term: str, parents: Mapping[str, set[str]], memo: dict[str, frozenset[str]]
) -> frozenset[str]:
    """The term itself plus all is_a ancestors (iterative, memoized)."""
    if term in memo:
        return memo[term]
    result: set[str] = {term}
    stack = [term]
    while stack:
        for parent in parents.get(stack.pop(), ()):
            if parent not in result:
                if parent in memo:
                    result |= memo[parent]
                else:
                    result.add(parent)
                    stack.append(parent)
    memo[term] = frozenset(result)
    return memo[term]


def parse_hpoa(
    lines: Iterable[str], alt_ids: Mapping[str, str]
) -> tuple[dict[str, set[str]], str | None]:
    """Return (disease id -> directly annotated HP terms, release version) for aspect P."""
    by_disease: dict[str, set[str]] = defaultdict(set)
    version: str | None = None
    columns: list[str] | None = None
    for raw in lines:
        line = raw.rstrip("\n")
        if line.startswith("#"):
            match = _VERSION_RE.match(line)
            if match and version is None:
                version = match.group(1)
            continue
        fields = line.split("\t")
        if columns is None:
            columns = fields
            continue
        row = dict(zip(columns, fields, strict=False))
        if row.get("aspect") != "P" or row.get("qualifier") == "NOT":
            continue
        term = row.get("hpo_id", "")
        by_disease[row.get("database_id", "")].add(alt_ids.get(term, term))
    return dict(by_disease), version


def information_content(
    by_disease: Mapping[str, set[str]], parents: Mapping[str, set[str]], terms: Iterable[str]
) -> tuple[dict[str, float], int]:
    """IC for ``terms`` with annotations propagated to ancestors; returns (ic map, N)."""
    memo: dict[str, frozenset[str]] = {}
    counts: dict[str, int] = defaultdict(int)
    for annotated in by_disease.values():
        closure: set[str] = set()
        for term in annotated:
            closure |= ancestors_of(term, parents, memo)
        for term in closure:
            counts[term] += 1
    total = len(by_disease)
    if total == 0:
        raise ValueError("phenotype.hpoa contained no phenotype annotations")
    return {term: -math.log(max(counts.get(term, 0), 1) / total) for term in terms}, total


def fetch(client: PoliteClient, hp_ids: Iterable[str], raw_dir: Path | None = None) -> JsonDict:
    """Download the HPO release, compute IC for ``hp_ids`` and return the compact payload."""
    base = (raw_dir or RAW_DIR) / SOURCE
    hpoa = download(client, HPOA_URL, base / "phenotype.hpoa")
    obo = download(client, OBO_URL, base / "hp.obo")
    return compute_payload(
        hpoa.read_text(encoding="utf-8").splitlines(),
        obo.read_text(encoding="utf-8").splitlines(),
        hp_ids,
    )


def compute_payload(hpoa_lines: list[str], obo_lines: list[str], hp_ids: Iterable[str]) -> JsonDict:
    names, parents, alt_ids = parse_obo(obo_lines)
    obo_version = next((m.group(1) for m in map(_DATA_VERSION_RE.match, obo_lines[:30]) if m), None)
    by_disease, hpoa_version = parse_hpoa(hpoa_lines, alt_ids)
    wanted = sorted({alt_ids.get(term, term) for term in hp_ids})
    ic, total = information_content(by_disease, parents, wanted)
    meta = make_meta(HPOA_URL, hpoa_version)
    return {
        "meta": meta,
        "ontology_version": obo_version,
        "method": IC_METHOD,
        "annotated_diseases": total,
        "ic": {term: f"{value:.{IC_DECIMALS}f}" for term, value in sorted(ic.items())},
        "labels": {term: names[term] for term in wanted if term in names},
    }


def normalize(payload: Mapping[str, Any]) -> IngestResult:
    """Phenotype nodes carrying ``attributes["ic"]`` (merged with Monarch's by id downstream)."""
    meta = payload["meta"]
    labels: Mapping[str, str] = payload.get("labels") or {}
    nodes = [
        Node(
            id=term,
            type=NodeType.PHENOTYPE,
            label=labels.get(term, term),
            attributes=FrozenStrMap(
                {
                    "ic": str(value),
                    "ic_source": f"hpo {meta.get('source_version') or 'unknown'}",
                    "hpo_url": f"https://hpo.jax.org/browse/term/{term}",
                }
            ),
        )
        for term, value in sorted((payload.get("ic") or {}).items())
    ]
    return IngestResult(
        source=SOURCE,
        source_version=meta.get("source_version"),
        retrieved_at=str(meta["retrieved_at"]),
        nodes=merge_nodes(nodes),
        edges=(),
        notes={
            "records": len(nodes),
            "annotated_diseases": payload.get("annotated_diseases"),
            "ontology_version": payload.get("ontology_version"),
            "method": payload.get("method"),
        },
    )
