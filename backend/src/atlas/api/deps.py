"""Request dependencies shared by API routes."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from atlas.graph.store import GraphStore, SnapshotStatus

SNAPSHOT_UNAVAILABLE = "graph snapshot is not loaded; see /health"


def get_snapshot_status(request: Request) -> SnapshotStatus | None:
    status: SnapshotStatus | None = getattr(request.app.state, "snapshot_status", None)
    return status


def get_store_or_none(request: Request) -> GraphStore | None:
    store: GraphStore | None = getattr(request.app.state, "store", None)
    return store


def get_store(request: Request) -> GraphStore:
    """Route dependency (use ``store: StoreDep``); 503 when no snapshot is loaded."""
    store = get_store_or_none(request)
    if store is None:
        raise HTTPException(status_code=503, detail=SNAPSHOT_UNAVAILABLE)
    return store


StoreDep = Annotated[GraphStore, Depends(get_store)]
OptionalStoreDep = Annotated[GraphStore | None, Depends(get_store_or_none)]
SnapshotStatusDep = Annotated[SnapshotStatus | None, Depends(get_snapshot_status)]
