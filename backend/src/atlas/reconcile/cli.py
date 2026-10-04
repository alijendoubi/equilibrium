"""Reconcile CLI.

  uv run python -m atlas.reconcile.cli embed --nodes ../data/snapshot/atlas-snapshot.json
  uv run python -m atlas.reconcile.cli resolve --nodes <snapshot.json> "Gaucher type II" ...

`embed` precomputes OpenAI embeddings for every node label and synonym into the committed
cache so search and resolution run offline during the demo.
"""

import argparse
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from atlas.config import get_settings
from atlas.extract.openai_client import OpenAIKeyMissingError, create_openai_client
from atlas.models.evidence import Node
from atlas.reconcile.embeddings import EmbeddingCache
from atlas.reconcile.llm_choice import DecisionCache
from atlas.reconcile.resolver import node_texts, resolve

logger = logging.getLogger(__name__)

DEFAULT_CACHE_ROOT = Path(__file__).resolve().parents[4] / "data" / "cache"
EXIT_USAGE = 2


def load_nodes(path: Path) -> tuple[Node, ...]:
    """Read nodes from a snapshot ({"nodes": [...]}) or a bare JSON list."""
    if not path.exists():
        msg = f"Snapshot not found: {path}. Build it first (make data-offline)."
        raise FileNotFoundError(msg)
    raw: Any = json.loads(path.read_text(encoding="utf-8"))
    items = raw["nodes"] if isinstance(raw, dict) else raw
    return tuple(Node.model_validate(item) for item in items)


def _client_or_none() -> Any:
    try:
        return create_openai_client()
    except OpenAIKeyMissingError:
        logger.warning("OPENAI_API_KEY not set: using cached data only")
        return None


def cmd_embed(nodes: Sequence[Node], cache_root: Path) -> dict[str, Any]:
    settings = get_settings()
    cache = EmbeddingCache.load(settings.openai_embed_model, cache_root / "embeddings")
    texts = [t for n in nodes for t in node_texts(n)]
    updated, usage = cache.with_fetched(texts, _client_or_none())
    updated.save()
    return {
        "model": updated.model,
        "vectors": len(updated),
        "still_missing": len(updated.missing(texts)),
        "openai_usage": usage.as_dict(),
    }


def cmd_resolve(nodes: Sequence[Node], mentions: Sequence[str], cache_root: Path) -> list[Any]:
    settings = get_settings()
    client = _client_or_none()
    embeddings, _ = EmbeddingCache.load(
        settings.openai_embed_model, cache_root / "embeddings"
    ).with_fetched(mentions, client)
    decisions = DecisionCache.load(cache_root / "reconcile" / "decisions.json")
    result = resolve(
        mentions,
        nodes,
        embeddings=embeddings,
        decisions=decisions,
        client=client,
        model=settings.openai_model_reconcile,
    )
    if result.decisions is not None and len(result.decisions) > len(decisions):
        result.decisions.save()
    embeddings.save()
    return [
        {
            "mention": r.mention,
            "node_id": r.node_id,
            "method": r.method,
            "score": round(r.score, 4),
            "candidates": [[i, round(s, 4)] for i, s in r.candidates],
            "rationale": r.rationale,
        }
        for r in result.resolutions
    ]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="atlas.reconcile.cli")
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    embed = sub.add_parser("embed", help="precompute embeddings for all node names")
    embed.add_argument("--nodes", type=Path, required=True)
    res = sub.add_parser("resolve", help="resolve names to node ids")
    res.add_argument("--nodes", type=Path, required=True)
    res.add_argument("mentions", nargs="+")
    args = parser.parse_args(argv)
    try:
        nodes = load_nodes(args.nodes)
    except FileNotFoundError as exc:
        sys.stderr.write(f"{exc}\n")
        return EXIT_USAGE
    if args.command == "embed":
        output: Any = cmd_embed(nodes, args.cache_root)
    else:
        output = cmd_resolve(nodes, args.mentions, args.cache_root)
    sys.stdout.write(json.dumps(output, indent=2) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
