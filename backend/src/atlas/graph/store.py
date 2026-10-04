"""Read-only graph store over the committed snapshot (``data/snapshot/atlas-snapshot.json``).

Loaded once at startup (FastAPI lifespan). Nodes and edges are the frozen evidence-model
objects; the underlying ``networkx.MultiDiGraph`` is frozen, edge keys are the deterministic
edge ids. All accessors return tuples sorted deterministically.

Interface for API routes (#22):

* ``store.get_node(node_id) -> Node | None``
* ``store.get_edge(edge_id) -> Edge | None``
* ``store.edges_for(node_id, direction="both"|"out"|"in", relations=None) -> tuple[Edge, ...]``
* ``store.neighbors(node_id, direction="both", relations=None) -> tuple[Node, ...]``
* ``store.nodes(node_type=None) -> tuple[Node, ...]``
* ``store.graph`` (frozen MultiDiGraph, node attr ``node``, edge attr ``edge``, key = edge id)
* ``store.manifest`` / ``store.coverage`` (read-only mappings), ``store.snapshot_id``
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

import networkx as nx

from atlas.models.evidence import Edge, Node, NodeType, Relation

logger = logging.getLogger(__name__)

Direction = Literal["both", "out", "in"]
MANIFEST_FILE = "manifest.json"


class SnapshotError(RuntimeError):
    """The snapshot file is missing, unreadable or internally inconsistent."""


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


def thaw(value: Any) -> Any:
    """Plain (mutable, JSON-ready) copy of a frozen manifest/coverage value."""
    if isinstance(value, Mapping):
        return {k: thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [thaw(v) for v in value]
    return value


def _edge_sort_key(edge: Edge) -> tuple[str, str, str, str]:
    return (edge.source_id, edge.relation.value, edge.target_id, edge.id)


class GraphStore:
    """Immutable, in-memory view of one snapshot."""

    def __init__(
        self,
        nodes: Iterable[Node],
        edges: Iterable[Edge],
        manifest: Mapping[str, Any] | None = None,
        coverage: Mapping[str, Any] | None = None,
    ) -> None:
        graph = nx.MultiDiGraph()
        self._nodes: dict[str, Node] = {}
        for node in nodes:
            if node.id in self._nodes:
                raise SnapshotError(f"duplicate node id {node.id}")
            self._nodes[node.id] = node
            graph.add_node(node.id, node=node)
        self._edges: dict[str, Edge] = {}
        for edge in edges:
            missing = [i for i in (edge.source_id, edge.target_id) if i not in self._nodes]
            if missing:
                raise SnapshotError(f"edge {edge.id} has dangling endpoint(s) {missing}")
            if edge.id in self._edges:
                raise SnapshotError(f"duplicate edge id {edge.id}")
            self._edges[edge.id] = edge
            graph.add_edge(edge.source_id, edge.target_id, key=edge.id, edge=edge)
        self._graph = nx.freeze(graph)
        self._manifest: Mapping[str, Any] = _freeze(dict(manifest or {}))
        self._coverage: Mapping[str, Any] = _freeze(dict(coverage or {}))

    # ---- loading ------------------------------------------------------------------------

    @classmethod
    def from_snapshot(cls, path: Path) -> GraphStore:
        """Load and validate ``atlas-snapshot.json`` (+ ``manifest.json`` next to it, if any)."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise SnapshotError(f"snapshot not found: {path}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise SnapshotError(f"snapshot unreadable: {path}: {exc}") from exc
        try:
            nodes = [Node.model_validate(item) for item in data["nodes"]]
            edges = [Edge.model_validate(item) for item in data["edges"]]
        except (KeyError, TypeError, ValueError) as exc:
            raise SnapshotError(f"snapshot invalid: {path}: {exc}") from exc
        manifest_path = path.parent / MANIFEST_FILE
        manifest: dict[str, Any] = {}
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return cls(nodes, edges, manifest=manifest, coverage=data.get("coverage") or {})

    # ---- accessors ----------------------------------------------------------------------

    @property
    def graph(self) -> Any:
        """The frozen networkx.MultiDiGraph (mutation raises NetworkXError)."""
        return self._graph

    @property
    def manifest(self) -> Mapping[str, Any]:
        return self._manifest

    @property
    def coverage(self) -> Mapping[str, Any]:
        return self._coverage

    @property
    def snapshot_id(self) -> str | None:
        value = self._manifest.get("snapshot_id")
        return str(value) if value else None

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    def get_node(self, node_id: str) -> Node | None:
        return self._nodes.get(node_id)

    def get_edge(self, edge_id: str) -> Edge | None:
        return self._edges.get(edge_id)

    def nodes(self, node_type: NodeType | None = None) -> tuple[Node, ...]:
        return tuple(
            self._nodes[key]
            for key in sorted(self._nodes)
            if node_type is None or self._nodes[key].type is node_type
        )

    def edges_for(
        self,
        node_id: str,
        direction: Direction = "both",
        relations: Iterable[Relation] | None = None,
    ) -> tuple[Edge, ...]:
        """Edges touching ``node_id`` (unknown id -> empty tuple)."""
        if node_id not in self._nodes:
            return ()
        wanted = frozenset(relations) if relations is not None else None
        found: dict[str, Edge] = {}
        if direction in ("both", "out"):
            for _, _, edge in self._graph.out_edges(node_id, data="edge"):
                found[edge.id] = edge
        if direction in ("both", "in"):
            for _, _, edge in self._graph.in_edges(node_id, data="edge"):
                found[edge.id] = edge
        edges = (e for e in found.values() if wanted is None or e.relation in wanted)
        return tuple(sorted(edges, key=_edge_sort_key))

    def neighbors(
        self,
        node_id: str,
        direction: Direction = "both",
        relations: Iterable[Relation] | None = None,
    ) -> tuple[Node, ...]:
        """Distinct nodes one hop away, sorted by id."""
        ids = {
            edge.target_id if edge.source_id == node_id else edge.source_id
            for edge in self.edges_for(node_id, direction, relations)
        }
        ids.discard(node_id)
        return tuple(self._nodes[i] for i in sorted(ids))


@dataclass(frozen=True)
class SnapshotStatus:
    """What /health and /meta report about the loaded snapshot."""

    status: Literal["loaded", "missing", "error"]
    path: str
    detail: str | None = None


def load_store(path: Path) -> tuple[GraphStore | None, SnapshotStatus]:
    """Load the snapshot for the app; never raises (the API still starts without data)."""
    if not path.is_file():
        logger.warning("snapshot not found at %s; starting without graph data", path)
        return None, SnapshotStatus("missing", str(path), "snapshot file not found")
    try:
        store = GraphStore.from_snapshot(path)
    except SnapshotError as exc:
        logger.error("snapshot failed to load: %s", exc)
        return None, SnapshotStatus("error", str(path), str(exc))
    logger.info(
        "snapshot %s loaded: %d nodes, %d edges",
        store.snapshot_id,
        store.node_count,
        store.edge_count,
    )
    return store, SnapshotStatus("loaded", str(path))
