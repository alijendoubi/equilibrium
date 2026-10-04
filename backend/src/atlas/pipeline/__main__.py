"""``python -m atlas.pipeline build [--offline] [--out DIR]`` and ``... report [--dir DIR]``.

``build`` (online, default): refresh every source into ``data/cache/`` first, then build.
``build --offline``: build from the committed cache only (no network, deterministic).
``build --no-with-extract``: skip the cached OpenAI Extract claims.
``report``: print the manifest counts and the hero-path / gap story checks as JSON.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from atlas.ingest.refresh import refresh
from atlas.pipeline.build import MANIFEST_FILE, SNAPSHOT_DIR, SNAPSHOT_FILE, build, write
from atlas.pipeline.checks import story_checks

logger = logging.getLogger("atlas.pipeline")


def _build(offline: bool, out: Path | None, with_extract: bool | None = None) -> int:
    if not offline:
        refresh()
    output = build(with_extract=with_extract)
    snapshot_path, manifest_path = write(output, out)
    counts = output.manifest["counts"]
    logger.info(
        "snapshot %s: %d nodes, %d edges -> %s (%s)",
        output.snapshot_id,
        counts["nodes"],
        counts["edges"],
        snapshot_path,
        manifest_path.name,
    )
    return 0


def _report(directory: Path) -> int:
    snapshot = json.loads((directory / SNAPSHOT_FILE).read_text(encoding="utf-8"))
    manifest = json.loads((directory / MANIFEST_FILE).read_text(encoding="utf-8"))
    checks = story_checks(snapshot)
    report = {
        "snapshot_id": manifest["snapshot_id"],
        "counts": manifest["counts"],
        "sources": manifest["sources"],
        "story_checks": checks,
    }
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    return 0 if checks["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m atlas.pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("build", help="build data/snapshot/ from the source cache")
    cmd.add_argument("--offline", action="store_true", help="use the committed cache only")
    cmd.add_argument(
        "--with-extract",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="add cached OpenAI Extract claims (default: on when data/cache/extract has claims)",
    )
    cmd.add_argument("--out", type=Path, default=None, help="output dir (default data/snapshot)")
    rep = sub.add_parser("report", help="print snapshot counts and story checks")
    rep.add_argument("--dir", type=Path, default=SNAPSHOT_DIR, help="snapshot directory")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if args.command == "report":
        return _report(args.dir)
    return _build(args.offline, args.out, args.with_extract)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
