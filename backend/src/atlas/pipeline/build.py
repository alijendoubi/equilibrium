"""Snapshot build: normalize cached sources -> merge/dedup -> validate -> snapshot + manifest.

The build is a pure function of ``data/cache/`` and ``data/curated/``: the same inputs give a
byte-identical ``atlas-snapshot.json`` and ``manifest.json``. ``created_at`` in the manifest is
therefore the latest ``retrieved_at`` among the sources (when the data was fetched), not the
wall-clock time of the build.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from atlas.ingest import clinicaltrials, clinvar, curated, go, hpo, monarch
from atlas.ingest.common import CACHE_DIR, DATA_DIR, IngestResult, dedupe_edges, merge_nodes
from atlas.ingest.common import read_cache as read_source_cache
from atlas.ingest.refresh import CACHE_NAME
from atlas.ingest.seeds import (
    GAP_DISEASE,
    HERO_DISEASES,
    PARTNER_DISEASE,
    SEED_DISEASES,
    SLICE_SLUG,
)
from atlas.models.evidence import Edge, Node

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1"
SNAPSHOT_DIR = DATA_DIR / "snapshot"
SNAPSHOT_FILE = "atlas-snapshot.json"
MANIFEST_FILE = "manifest.json"
RUBRIC_VERSION = "ingest-v1"
OPENAI_USAGE_PLACEHOLDER: dict[str, Any] = {
    "calls": 0,
    "input_tokens": 0,
    "output_tokens": 0,
    "batch_jobs": 0,
    "models": {},
    "note": "no OpenAI step in this build yet; Extract/Reconcile fill this in",
}


class SnapshotValidationError(ValueError):
    """The merged graph breaks an integrity rule (dangling endpoint, type clash, bad model)."""

    def __init__(self, problems: Sequence[str]) -> None:
        self.problems = tuple(problems)
        shown = "; ".join(self.problems[:10])
        more = f" (+{len(self.problems) - 10} more)" if len(self.problems) > 10 else ""
        super().__init__(f"snapshot validation failed: {shown}{more}")


@dataclass(frozen=True)
class BuildOutput:
    snapshot_bytes: bytes
    manifest_bytes: bytes
    snapshot_id: str
    manifest: Mapping[str, Any]


def normalize_all(
    cache_dir: Path | None = None, curated_dir: Path | None = None
) -> list[IngestResult]:
    """Run every normalizer over the cached payloads, in merge-precedence order."""
    cache = cache_dir or CACHE_DIR
    curated_payload = curated.load_all(curated_dir)

    def read(source: str) -> dict[str, Any]:
        return read_source_cache(source, CACHE_NAME, cache)

    monarch_result = monarch.normalize(read("monarch"))
    return [
        monarch_result,
        hpo.normalize(read("hpo")),
        go.normalize(read("go"), curated.mechanisms(curated_payload)),
        clinvar.normalize(read("clinvar")),
        clinicaltrials.normalize(
            read("clinicaltrials"),
            monarch_result.nodes,
            curated.condition_aliases(curated_payload),
        ),
        curated.normalize(curated_payload),
    ]


def validate(nodes: Sequence[Node], edges: Sequence[Edge], all_nodes: Iterable[Node] = ()) -> None:
    """Raise SnapshotValidationError on any integrity problem; returns None when clean."""
    problems: list[str] = []
    types: dict[str, set[str]] = {}
    for node in (*all_nodes, *nodes):
        types.setdefault(node.id, set()).add(node.type.value)
    problems += [
        f"node {nid} has conflicting types {sorted(t)}" for nid, t in types.items() if len(t) > 1
    ]
    node_ids = {node.id for node in nodes}
    edge_ids = {edge.id for edge in edges}
    if len(node_ids) != len(nodes):
        problems.append("duplicate node ids after merge")
    if len(edge_ids) != len(edges):
        problems.append("duplicate edge ids after merge")
    for edge in edges:
        for endpoint in (edge.source_id, edge.target_id):
            if endpoint not in node_ids:
                problems.append(
                    f"edge {edge.id} ({edge.relation.value}) has dangling endpoint {endpoint}"
                )
        problems += [
            f"edge {edge.id} supports on missing edge {sid}"
            for sid in edge.provenance.supporting_edge_ids
            if sid not in edge_ids
        ]
    for node in nodes:
        try:
            Node.model_validate(node.model_dump(mode="json"))
        except ValueError as exc:  # pragma: no cover - models already validated on creation
            problems.append(f"node {node.id} does not round-trip: {exc}")
    for edge in edges:
        try:
            Edge.model_validate(edge.model_dump(mode="json"))
        except ValueError as exc:  # pragma: no cover
            problems.append(f"edge {edge.id} does not round-trip: {exc}")
    if problems:
        raise SnapshotValidationError(problems)


def _dumps(data: Any) -> bytes:
    return (
        json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode()


def _pretty(data: Any) -> bytes:
    return (json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def coverage_seeds(results: Sequence[IngestResult], edges: Sequence[Edge]) -> dict[str, Any]:
    """Facts the coverage report (#21) needs: what was searched and what came back empty."""
    notes = {result.source: result.notes for result in results}
    studied = {e.target_id for e in edges if e.relation.value == "studies_condition"}
    represented = {e.target_id for e in edges if e.relation.value == "represents"}
    ct = notes.get("clinicaltrials", {})
    return {
        "hero_diseases": list(HERO_DISEASES),
        "partner_disease": PARTNER_DISEASE,
        "gap_disease": GAP_DISEASE,
        "no_dedicated_org_found": notes.get("curated", {}).get("no_dedicated_org_found", []),
        "clinicaltrials_query_counts": ct.get("query_counts", {}),
        "clinicaltrials_unmapped_conditions": ct.get("unmapped_conditions", {}),
        "clinicaltrials_dropped_studies": ct.get("dropped_studies_without_slice_condition", []),
        "go_genes_without_whitelisted_terms": notes.get("go", {}).get(
            "genes_without_whitelisted_terms", []
        ),
        "seed_diseases_without_studies": sorted(set(SEED_DISEASES) - studied),
        "seed_diseases_without_patient_group": sorted(set(SEED_DISEASES) - represented),
    }


def _source_entry(result: IngestResult, cache_dir: Path) -> dict[str, Any]:
    url = None
    if result.source != "curated":
        url = read_source_cache(result.source, CACHE_NAME, cache_dir)["meta"].get("url")
    return {
        "source": result.source,
        "source_version": result.source_version,
        "retrieved_at": result.retrieved_at,
        "url": url,
        "records": result.notes.get("records"),
        "nodes": len(result.nodes),
        "edges": len(result.edges),
    }


def build(cache_dir: Path | None = None, curated_dir: Path | None = None) -> BuildOutput:
    """Build snapshot + manifest bytes from the cache (no network, deterministic)."""
    cache = cache_dir or CACHE_DIR
    results = normalize_all(cache, curated_dir)
    all_nodes = [node for result in results for node in result.nodes]
    nodes = merge_nodes(all_nodes)
    edges = dedupe_edges(edge for result in results for edge in result.edges)
    validate(nodes, edges, all_nodes)

    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "slice": SLICE_SLUG,
        "nodes": [node.model_dump(mode="json") for node in nodes],
        "edges": [edge.model_dump(mode="json") for edge in edges],
        "coverage": coverage_seeds(results, edges),
    }
    snapshot_bytes = _dumps(snapshot)
    snapshot_id = f"sha256:{hashlib.sha256(snapshot_bytes).hexdigest()}"
    manifest = {
        "snapshot_id": snapshot_id,
        "schema_version": SCHEMA_VERSION,
        "slice": SLICE_SLUG,
        "created_at": max(result.retrieved_at for result in results),
        "created_at_note": "latest source retrieved_at (deterministic, not wall-clock)",
        "snapshot_file": SNAPSHOT_FILE,
        "snapshot_bytes": len(snapshot_bytes),
        "rubric_version": RUBRIC_VERSION,
        "sources": [_source_entry(result, cache) for result in results],
        "counts": {
            "nodes": len(nodes),
            "edges": len(edges),
            "nodes_by_type": dict(sorted(Counter(n.type.value for n in nodes).items())),
            "edges_by_relation": dict(sorted(Counter(e.relation.value for e in edges).items())),
            "edges_by_evidence_type": dict(
                sorted(Counter(e.evidence_type.value for e in edges).items())
            ),
        },
        "openai_usage": OPENAI_USAGE_PLACEHOLDER,
    }
    return BuildOutput(snapshot_bytes, _pretty(manifest), snapshot_id, manifest)


def write(output: BuildOutput, out_dir: Path | None = None) -> tuple[Path, Path]:
    target = out_dir or SNAPSHOT_DIR
    target.mkdir(parents=True, exist_ok=True)
    snapshot_path = target / SNAPSHOT_FILE
    manifest_path = target / MANIFEST_FILE
    snapshot_path.write_bytes(output.snapshot_bytes)
    manifest_path.write_bytes(output.manifest_bytes)
    return snapshot_path, manifest_path
