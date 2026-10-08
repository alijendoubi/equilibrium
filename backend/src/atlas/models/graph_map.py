"""Response models for GET /api/v1/graph (the evidence map).

Nodes and edges are the evidence-model objects themselves; a map node adds its degree and
cluster. Mirrors ``GraphMapResponse`` in frontend/src/lib/api/types.ts.
"""

from pydantic import BaseModel, ConfigDict, Field

from atlas.models.evidence import Edge, Node

_FROZEN = ConfigDict(frozen=True)


class MapNode(BaseModel):
    """A node drawn on the map."""

    model_config = _FROZEN

    node: Node
    # Edges touching the node inside this map (drives node size).
    degree: int = Field(ge=0)
    # Edges touching the node in the whole snapshot.
    total_degree: int = Field(ge=0)
    # Disease cluster (diseases only), else null.
    cluster_id: str | None
    # Hops from the center (0 = center); null on the overview.
    distance: int | None = Field(default=None, ge=0)


class MapTruncation(BaseModel):
    """What the map left out, so the UI can say "+41 phenotypes" instead of hiding it."""

    model_config = _FROZEN

    by_type: dict[str, int]
    nodes_hidden: int = Field(ge=0)
    edges_hidden: int = Field(ge=0)


class MapLegend(BaseModel):
    """Counts of what is drawn, per node type, relation and evidence type."""

    model_config = _FROZEN

    node_types: dict[str, int]
    relations: dict[str, int]
    evidence_types: dict[str, int]


class GraphMapResponse(BaseModel):
    model_config = _FROZEN

    center: str | None
    depth: int = Field(ge=0, le=2)
    nodes: tuple[MapNode, ...]
    edges: tuple[Edge, ...]
    # Edges that are a `contradicts` claim or that another edge contradicts.
    contradiction_edge_ids: tuple[str, ...]
    truncated: MapTruncation
    legend: MapLegend
