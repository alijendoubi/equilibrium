"""Online refresh: fetch every source and rewrite the committed cache in ``data/cache/``."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

from atlas.config import get_settings
from atlas.ingest import clinicaltrials, clinvar, curated, go, hpo, monarch, reporter
from atlas.ingest.common import CACHE_DIR, JsonDict, PoliteClient, read_cache, write_cache

logger = logging.getLogger(__name__)

SOURCES: tuple[str, ...] = ("monarch", "hpo", "go", "clinvar", "clinicaltrials", "reporter")
CACHE_NAME = "payload"
DEFAULT_INTERVAL_S = 0.25


def _ncbi_key() -> str | None:
    key = get_settings().ncbi_api_key
    return key.get_secret_value() if key is not None else None


def _interval(name: str) -> float:
    if name == "clinicaltrials":
        return clinicaltrials.MIN_INTERVAL_S
    if name == "clinvar":
        return clinvar.min_interval(_ncbi_key())
    if name == "reporter":
        return reporter.MIN_INTERVAL_S
    return DEFAULT_INTERVAL_S


def fetch_source(name: str, client: PoliteClient, cache_dir: Path) -> JsonDict:
    """Fetch one source online (HPO reads the Monarch cache for its phenotype ids)."""
    if name == "monarch":
        return monarch.fetch(client)
    if name == "hpo":
        monarch_payload = read_cache("monarch", CACHE_NAME, cache_dir)
        return hpo.fetch(client, monarch.phenotype_ids(monarch_payload))
    if name == "go":
        whitelist = [str(m["id"]) for m in curated.mechanisms(curated.load_all())]
        return go.fetch(client, whitelist)
    if name == "clinvar":
        return clinvar.fetch(client, _ncbi_key())
    if name == "clinicaltrials":
        return clinicaltrials.fetch(client)
    if name == "reporter":
        return reporter.fetch(client)
    raise ValueError(f"unknown source {name!r}; expected one of {SOURCES}")


def refresh(sources: Sequence[str] = SOURCES, cache_dir: Path | None = None) -> None:
    """Fetch ``sources`` in dependency order and rewrite their cache files."""
    target = cache_dir or CACHE_DIR
    for name in (s for s in SOURCES if s in sources):
        with PoliteClient(min_interval_s=_interval(name)) as client:
            payload = fetch_source(name, client, target)
        path = write_cache(payload, name, CACHE_NAME, target)
        logger.info("cached %s -> %s", name, path)
