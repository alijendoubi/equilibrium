"""Evidence map API: GET /api/v1/graph (a capped, explainable subgraph for drawing).

Without ``center`` it returns an overview of the slice; with ``center`` the neighbourhood up to
``depth`` hops. Hidden nodes are counted per type in ``truncated``. See atlas.graph.evidence_map.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from atlas.api.cluster_routes import ClusterIndexDep
from atlas.api.deps import StoreDep
from atlas.api.graph_routes import _enum_set, enforce_query_rate
from atlas.config import Settings, get_settings
from atlas.graph.evidence_map import MAX_DEPTH, MAX_NODES, MapQuery, build_map
from atlas.models.evidence import NodeType, Relation
from atlas.models.graph_map import GraphMapResponse

router = APIRouter(prefix="/api/v1", tags=["graph"])


@router.get("/graph", response_model=GraphMapResponse)
def evidence_map(
    request: Request,
    store: StoreDep,
    clusters: ClusterIndexDep,
    settings: Annotated[Settings, Depends(get_settings)],
    center: Annotated[str | None, Query(max_length=200)] = None,
    depth: Annotated[int, Query(ge=1, le=MAX_DEPTH)] = 1,
    types: Annotated[list[str] | None, Query()] = None,
    relations: Annotated[list[str] | None, Query()] = None,
    min_confidence: Annotated[float, Query(ge=0.0, le=1.0)] = 0.0,
    limit: Annotated[int, Query(ge=1, le=MAX_NODES)] = MAX_NODES,
) -> GraphMapResponse:
    """Nodes (with degree and cluster), edges with full provenance, what was hidden, a legend."""
    enforce_query_rate(request, settings)
    query = MapQuery(
        center=center.strip() or None if center is not None else None,
        depth=depth,
        types=_enum_set(types, NodeType, "node type"),
        relations=_enum_set(relations, Relation, "relation"),
        min_confidence=min_confidence,
        limit=limit,
    )
    try:
        return build_map(store, query, clusters.cluster_of)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown node {center}") from exc
