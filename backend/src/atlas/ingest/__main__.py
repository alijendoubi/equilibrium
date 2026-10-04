"""``python -m atlas.ingest fetch [--source NAME ...]``: refresh the committed source cache."""

from __future__ import annotations

import argparse
import logging

from atlas.ingest.refresh import SOURCES, refresh


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m atlas.ingest")
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch", help="fetch sources online and rewrite data/cache/")
    fetch.add_argument("--source", action="append", choices=SOURCES, help="repeatable")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    refresh(tuple(args.source or SOURCES))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
