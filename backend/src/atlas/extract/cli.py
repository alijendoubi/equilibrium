"""OpenAI Extract precompute.

    uv run python -m atlas.extract.cli fetch     # PubMed -> data/cache/pubmed/abstracts.json
    uv run python -m atlas.extract.cli run       # OpenAI -> data/cache/extract/claims.json
    uv run python -m atlas.extract.cli report    # counts per relation / certainty
    uv run python -m atlas.extract.cli eval      # precision/recall vs data/eval/gold_claims.jsonl

``run`` needs OPENAI_API_KEY; without it (or with ATLAS_OFFLINE=1) nothing is written.
Rerunning is free: cached (model, prompt, PMID, candidate set) combinations make no calls.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from atlas.config import get_settings
from atlas.extract.claims import (
    DEFAULT_CLAIMS_PATH,
    ClaimsCache,
    candidate_nodes,
    extract_abstract,
)
from atlas.extract.eval import DEFAULT_GOLD_PATH, evaluate, load_gold
from atlas.extract.pubmed import (
    DEFAULT_ABSTRACTS_PATH,
    fetch_corpus,
    load_abstracts,
    polite_client,
    write_abstracts,
)
from atlas.ingest.common import merge_nodes
from atlas.models.evidence import Node
from atlas.reconcile.embeddings import is_offline
from atlas.reconcile.usage import UsageRecord

NO_KEY_MESSAGE = (
    "No OPENAI_API_KEY (or ATLAS_OFFLINE=1): nothing written to the claims cache; "
    "the pipeline uses whatever data/cache/extract/claims.json already holds."
)
SAVE_EVERY = 10


def graph_nodes() -> tuple[Node, ...]:
    """Nodes the pipeline builds from the source cache (the candidate vocabulary)."""
    from atlas.pipeline.build import normalize_all

    return merge_nodes(node for result in normalize_all() for node in result.nodes)


def _client() -> Any:
    settings = get_settings()
    if is_offline() or not settings.has_openai_key:
        return None
    from atlas.extract.openai_client import create_openai_client

    return create_openai_client(settings).with_options(timeout=60.0, max_retries=2)


def cmd_fetch(abstracts_path: Path) -> int:
    key = get_settings().ncbi_api_key
    api_key = key.get_secret_value().strip() if key is not None else None
    with polite_client(api_key) as client:
        payload = fetch_corpus(client, api_key=api_key or None)
    path = write_abstracts(payload, abstracts_path)
    print(f"pubmed: {len(payload['abstracts'])} abstracts -> {path}")
    return 0


def run(
    nodes: Sequence[Node],
    abstracts_path: Path,
    claims_path: Path,
    client: Any,
    model: str,
    limit: int | None = None,
) -> int:
    """Extract claims for every cached abstract; returns an exit code."""
    if client is None:
        print(NO_KEY_MESSAGE)
        return 0
    candidates = candidate_nodes(nodes)
    cache = ClaimsCache.load(claims_path)
    usage = UsageRecord()
    counts = Counter[str]()
    for index, abstract in enumerate(load_abstracts(abstracts_path)[:limit]):
        before = len(cache)
        extraction, cache, used = extract_abstract(
            abstract, candidates, client=client, model=model, cache=cache
        )
        usage = usage.merge(used)
        counts["live" if len(cache) > before else "cached"] += 1
        if extraction is not None:
            counts["claims"] += len(extraction.claims)
            counts["dropped"] += extraction.dropped
        if counts["live"] and index % SAVE_EVERY == 0:
            cache.save()
    if counts["live"]:
        cache.save()
    print(f"extract run: {dict(sorted(counts.items()))}; cache entries={len(cache)}")
    print(f"openai usage: {json.dumps(usage.as_dict())}")
    return 0


def report(claims_path: Path, abstracts_path: Path) -> dict[str, Any]:
    cache = ClaimsCache.load(claims_path)
    extractions = [e for _, e in cache.items()]
    claims = [c for e in extractions for c in e.claims]
    return {
        "abstracts_cached": len(load_abstracts(abstracts_path)),
        "extractions": len(extractions),
        "abstracts_with_claims": sum(1 for e in extractions if e.claims),
        "claims": len(claims),
        "dropped": sum(e.dropped for e in extractions),
        "by_relation": dict(sorted(Counter(c.relation for c in claims).items())),
        "by_certainty": dict(sorted(Counter(c.certainty for c in claims).items())),
        "by_polarity": dict(sorted(Counter(c.polarity for c in claims).items())),
    }


def cmd_eval(gold_path: Path, claims_path: Path) -> int:
    gold = load_gold(gold_path)
    if not gold:
        print(f"no gold claims in {gold_path}; label some first (see docs/ARCHITECTURE.md)")
        return 0
    extractions = [e for _, e in ClaimsCache.load(claims_path).items()]
    print(json.dumps(evaluate(extractions, gold).as_dict(), indent=2))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="atlas.extract.cli")
    parser.add_argument("--abstracts", type=Path, default=DEFAULT_ABSTRACTS_PATH)
    parser.add_argument("--claims", type=Path, default=DEFAULT_CLAIMS_PATH)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fetch", help="fetch the PubMed corpus into the cache")
    run_cmd = sub.add_parser("run", help="OpenAI extraction over the cached abstracts")
    run_cmd.add_argument("--limit", type=int, default=None)
    sub.add_parser("report", help="counts of cached claims")
    ev = sub.add_parser("eval", help="precision/recall against gold claims")
    ev.add_argument("--gold", type=Path, default=DEFAULT_GOLD_PATH)
    args = parser.parse_args(argv)
    if args.command == "fetch":
        return cmd_fetch(args.abstracts)
    if args.command == "run":
        settings = get_settings()
        return run(
            graph_nodes(),
            args.abstracts,
            args.claims,
            _client(),
            settings.openai_model_extract,
            args.limit,
        )
    if args.command == "report":
        print(json.dumps(report(args.claims, args.abstracts), indent=2))
        return 0
    return cmd_eval(args.gold, args.claims)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
