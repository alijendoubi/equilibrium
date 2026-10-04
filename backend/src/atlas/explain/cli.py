"""Precompute Explain answers into the committed cache.

    uv run python -m atlas.explain.cli golden            # golden Gaucher -> ASPro-PD path
    uv run python -m atlas.explain.cli precompute --paths paths.json   # [["E:..", ...], ...]

Both need OPENAI_API_KEY. Without it (or with ATLAS_OFFLINE=1) nothing is written; the API
then serves the deterministic template.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import get_args

from atlas.config import get_settings
from atlas.explain.cache import DEFAULT_CACHE_PATH, ExplanationCache
from atlas.explain.golden import golden_edges, nodes_for
from atlas.explain.models import Audience
from atlas.explain.service import explain_client, explain_edges
from atlas.graph.store import GraphStore
from atlas.models.evidence import Edge
from atlas.reconcile.usage import UsageRecord

AUDIENCES: tuple[Audience, ...] = get_args(Audience)
NO_KEY_MESSAGE = (
    "No OPENAI_API_KEY (or ATLAS_OFFLINE=1): nothing written to the explain cache; "
    "the API will serve template explanations."
)


def _resolve(store: GraphStore, edge_ids: Sequence[str]) -> tuple[Edge, ...]:
    edges = []
    for edge_id in edge_ids:
        edge = store.get_edge(edge_id)
        if edge is None:
            raise SystemExit(f"unknown edge id {edge_id}")
        edges.append(edge)
    return tuple(edges)


def precompute(paths: Sequence[Sequence[Edge]], store: GraphStore, cache_path: Path) -> int:
    """Explain every path for both audiences; save new live answers. Returns an exit code."""
    settings = get_settings()
    client = explain_client(settings)
    if client is None:
        print(NO_KEY_MESSAGE)
        return 0
    cache = ExplanationCache.load(cache_path)
    usage = UsageRecord()
    counts = {"cache": 0, "live": 0, "template": 0}
    for edges in paths:
        nodes = nodes_for(store, edges)
        for audience in AUDIENCES:
            outcome = explain_edges(
                edges,
                nodes,
                audience=audience,
                client=client,
                model=settings.openai_model_explain,
                cache=cache,
            )
            cache, usage = outcome.cache, usage.merge(outcome.usage)
            counts[outcome.response.source] += 1
    if counts["live"]:
        cache.save()
    print(f"explain precompute: {counts}; cache entries={len(cache)} at {cache_path}")
    print(f"openai usage: {json.dumps(usage.as_dict())}")
    return 1 if counts["template"] else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="atlas.explain.cli")
    parser.add_argument("--snapshot", type=Path, default=None)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE_PATH)
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("precompute", help="explain edge-id lists from a JSON file")
    pre.add_argument("--paths", type=Path, required=True)
    sub.add_parser("golden", help="find and explain the golden Gaucher -> ASPro-PD path")
    args = parser.parse_args(argv)

    store = GraphStore.from_snapshot(args.snapshot or get_settings().snapshot_path)
    if args.command == "golden":
        edges = golden_edges(store)
        if not edges:
            print("golden path not found in the snapshot")
            return 1
        print("golden edge ids:", json.dumps([e.id for e in edges]))
        return precompute([edges], store, args.cache)
    raw = json.loads(args.paths.read_text(encoding="utf-8"))
    paths = [_resolve(store, [str(i) for i in path]) for path in raw]
    return precompute(paths, store, args.cache)


if __name__ == "__main__":
    sys.exit(main())
