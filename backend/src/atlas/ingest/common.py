"""Shared ingest plumbing: polite HTTP client, the committed JSON cache, and result helpers.

Every connector follows the same shape:

* ``fetch(client, ...) -> dict``: call the source API and return a *compact* JSON-able payload
  (only the fields the normalizer needs), with a ``meta`` block (``retrieved_at``,
  ``source_version``, ``url``). The pipeline writes it to ``data/cache/<source>/<name>.json``.
* ``normalize(payload) -> IngestResult``: a pure function from that payload to evidence-model
  nodes and edges. No network, no clock: the same payload always gives the same output.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from atlas import __version__
from atlas.models.evidence import Edge, Node

logger = logging.getLogger(__name__)

USER_AGENT = (
    f"equilibrium-atlas/{__version__} "
    "(+https://github.com/alijendoubi/equilibrium; Hack-Nation rare disease atlas)"
)
DEFAULT_TIMEOUT_S = 30.0
DEFAULT_RETRIES = 4
DEFAULT_BACKOFF_S = 1.0
RETRY_STATUS = frozenset({429, 500, 502, 503, 504})

REPO_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = Path(os.environ.get("ATLAS_DATA_DIR", REPO_ROOT / "data"))
CACHE_DIR = DATA_DIR / "cache"
RAW_DIR = DATA_DIR / "raw"
CURATED_DIR = DATA_DIR / "curated"

JsonDict = dict[str, Any]


class FetchError(RuntimeError):
    """A source could not be fetched after all retries."""


class PoliteClient:
    """A small httpx wrapper: identifying User-Agent, timeouts, rate limit, retry with backoff."""

    def __init__(
        self,
        min_interval_s: float = 0.25,
        retries: int = DEFAULT_RETRIES,
        backoff_s: float = DEFAULT_BACKOFF_S,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=timeout_s,
            follow_redirects=True,
            transport=transport,
        )
        self._min_interval_s = min_interval_s
        self._retries = retries
        self._backoff_s = backoff_s
        self._sleep = sleep
        self._last_request = 0.0

    def __enter__(self) -> PoliteClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _throttle(self) -> None:
        wait = self._min_interval_s - (time.monotonic() - self._last_request)
        if wait > 0:
            self._sleep(wait)
        self._last_request = time.monotonic()

    def get(self, url: str, params: Mapping[str, Any] | None = None) -> httpx.Response:
        """GET with retries on transport errors and 429/5xx; raises FetchError when exhausted."""
        return self._request("GET", url, params=params)

    def post(self, url: str, json_body: Any) -> httpx.Response:
        """POST a JSON body with the same throttle, retries and errors as ``get``."""
        return self._request("POST", url, json_body=json_body)

    def _request(
        self,
        method: str,
        url: str,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
    ) -> httpx.Response:
        last_error: str = "no attempt made"
        for attempt in range(self._retries + 1):
            self._throttle()
            try:
                response = self._client.request(method, url, params=params, json=json_body)
            except httpx.TransportError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code not in RETRY_STATUS:
                    response.raise_for_status()
                    return response
                last_error = f"HTTP {response.status_code}"
            if attempt < self._retries:
                delay = self._backoff_s * (2**attempt)
                logger.warning("%s %s failed (%s); retry in %.1fs", method, url, last_error, delay)
                self._sleep(delay)
        raise FetchError(f"{method} {url} failed after {self._retries + 1} attempts: {last_error}")

    def get_json(self, url: str, params: Mapping[str, Any] | None = None) -> Any:
        return self.get(url, params).json()

    def post_json(self, url: str, json_body: Any) -> Any:
        return self.post(url, json_body).json()


@dataclass(frozen=True)
class IngestResult:
    """Normalized output of one source: nodes, edges and free-form notes (coverage, gaps)."""

    source: str
    source_version: str | None
    retrieved_at: str
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    notes: Mapping[str, Any] = field(default_factory=dict)


def utc_now_iso() -> str:
    """Current UTC time, second precision, ISO 8601 with a Z suffix."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def cache_path(source: str, name: str, cache_dir: Path | None = None) -> Path:
    return (cache_dir or CACHE_DIR) / source / f"{name}.json"


def write_cache(payload: JsonDict, source: str, name: str, cache_dir: Path | None = None) -> Path:
    """Write a payload as deterministic, compact-ish JSON (sorted keys, one level indent)."""
    path = cache_path(source, name, cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, sort_keys=True, indent=1, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def read_cache(source: str, name: str, cache_dir: Path | None = None) -> JsonDict:
    path = cache_path(source, name, cache_dir)
    if not path.is_file():
        raise FileNotFoundError(f"no cached payload at {path}; run the online build first")
    data: JsonDict = json.loads(path.read_text(encoding="utf-8"))
    return data


def make_meta(url: str, source_version: str | None, retrieved_at: str | None = None) -> JsonDict:
    return {
        "url": url,
        "source_version": source_version,
        "retrieved_at": retrieved_at or utc_now_iso(),
    }


_WS = re.compile(r"\s+")


def clean_text(value: object, max_len: int | None = None) -> str:
    """Collapse whitespace; optionally truncate on a word boundary with an ellipsis."""
    text = _WS.sub(" ", str(value or "")).strip()
    if max_len is not None and len(text) > max_len:
        cut = text[:max_len].rsplit(" ", 1)[0]
        text = f"{cut}..."
    return text


def merge_nodes(nodes: Iterable[Node]) -> tuple[Node, ...]:
    """Deduplicate nodes by id, merging synonyms/xrefs/attributes; output sorted by id.

    The first node seen for an id keeps its type and label, and its attribute values win on
    key conflicts. Callers control precedence through the order of ``nodes``.
    """
    merged: dict[str, Node] = {}
    for node in nodes:
        current = merged.get(node.id)
        if current is None:
            merged[node.id] = node
            continue
        synonyms = _ordered_union(current.synonyms, node.synonyms, exclude=current.label)
        xrefs = _ordered_union(current.xrefs, node.xrefs)
        attributes = {**dict(node.attributes), **dict(current.attributes)}
        merged[node.id] = current.model_copy(
            update={
                "synonyms": synonyms,
                "xrefs": xrefs,
                "attributes": type(current.attributes)(dict(sorted(attributes.items()))),
            }
        )
    return tuple(merged[key] for key in sorted(merged))


def _ordered_union(
    first: Iterable[str], second: Iterable[str], exclude: str | None = None
) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for item in (*first, *second):
        if item and item != exclude:
            seen.setdefault(item, None)
    return tuple(seen)


def dedupe_edges(edges: Iterable[Edge]) -> tuple[Edge, ...]:
    """Keep the first edge per deterministic id; output sorted by (source, relation, target, id)."""
    by_id: dict[str, Edge] = {}
    for edge in edges:
        by_id.setdefault(edge.id, edge)
    return tuple(
        sorted(
            by_id.values(),
            key=lambda e: (e.source_id, e.relation.value, e.target_id, e.id),
        )
    )


def unique_sorted(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if value}))
