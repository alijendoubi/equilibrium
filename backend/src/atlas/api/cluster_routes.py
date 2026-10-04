"""Cluster read API (issue #20): GET /api/v1/clusters and GET /api/v1/clusters/{id}.

The index is computed once at startup (``app.state.cluster_index``); built lazily from the
store if missing. 503 without a snapshot, like every graph route.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from atlas.api.deps import StoreDep
from atlas.graph.clusters import METHOD, ClusterIndex, build_cluster_index
from atlas.models.clusters import ClusterDetail, ClustersResponse

router = APIRouter(prefix="/api/v1", tags=["clusters"])


def get_cluster_index(request: Request, store: StoreDep) -> ClusterIndex:
    """The index built at startup; built (and cached) here if the app state has none."""
    index: ClusterIndex | None = getattr(request.app.state, "cluster_index", None)
    if index is None:
        index = build_cluster_index(store)
        request.app.state.cluster_index = index
    return index


ClusterIndexDep = Annotated[ClusterIndex, Depends(get_cluster_index)]


@router.get("/clusters", response_model=ClustersResponse)
def list_clusters(index: ClusterIndexDep) -> ClustersResponse:
    """Every cluster: id, label, size, member ids; plus how they were computed."""
    return ClustersResponse(clusters=index.summaries, method=METHOD)


@router.get("/clusters/{cluster_id}", response_model=ClusterDetail)
def cluster_detail(cluster_id: str, index: ClusterIndexDep) -> ClusterDetail:
    """Members, shared features, drawing edges, bridges and counterexamples of one cluster."""
    detail = index.get(cluster_id.strip())
    if detail is None:
        raise HTTPException(status_code=404, detail=f"unknown cluster {cluster_id}")
    return detail
