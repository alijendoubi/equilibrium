"""Top-level API routes: health check and service metadata."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from atlas import __version__
from atlas.api.deps import OptionalStoreDep, SnapshotStatusDep
from atlas.graph.store import SnapshotStatus, thaw

SERVICE_NAME = "Equilibrium Atlas"
PLANNED_SOURCES: tuple[str, ...] = (
    "omim",
    "hpo",
    "mondo",
    "clinvar",
    "pubmed",
    "clinicaltrials",
    "nih_reporter",
    "orphanet",
)
NOT_LOADED = "not_loaded"

router = APIRouter()


class HealthResponse(BaseModel):
    """Liveness payload. ``snapshot`` is loaded, missing, error or not_loaded."""

    model_config = ConfigDict(frozen=True)

    status: str
    version: str
    snapshot: str


class SnapshotMeta(BaseModel):
    """The loaded snapshot, from its manifest."""

    model_config = ConfigDict(frozen=True)

    status: str
    snapshot_id: str | None = None
    slice: str | None = None
    created_at: str | None = None
    counts: dict[str, Any] = {}
    sources: list[dict[str, Any]] = []
    openai_usage: dict[str, Any] = {}
    detail: str | None = None


class MetaResponse(BaseModel):
    """Service metadata payload."""

    model_config = ConfigDict(frozen=True)

    name: str
    sources: tuple[str, ...]
    snapshot: SnapshotMeta


def _status_name(status: SnapshotStatus | None) -> str:
    return status.status if status is not None else NOT_LOADED


@router.get("/health", response_model=HealthResponse)
def health(status: SnapshotStatusDep) -> HealthResponse:
    """Liveness probe; also says whether the graph snapshot is loaded."""
    return HealthResponse(status="ok", version=__version__, snapshot=_status_name(status))


@router.get("/api/v1/meta", response_model=MetaResponse)
def meta(store: OptionalStoreDep, status: SnapshotStatusDep) -> MetaResponse:
    """Service name, the planned data sources and the loaded snapshot (id, counts, sources)."""
    if store is None:
        snapshot = SnapshotMeta(
            status=_status_name(status), detail=status.detail if status else None
        )
    else:
        manifest = thaw(store.manifest)
        snapshot = SnapshotMeta(
            status=_status_name(status),
            snapshot_id=store.snapshot_id,
            slice=manifest.get("slice"),
            created_at=manifest.get("created_at"),
            counts=manifest.get("counts") or {"nodes": store.node_count, "edges": store.edge_count},
            sources=[
                {
                    key: source.get(key)
                    for key in ("source", "source_version", "retrieved_at", "nodes", "edges")
                }
                for source in manifest.get("sources") or []
            ],
            openai_usage=manifest.get("openai_usage") or {},
        )
    return MetaResponse(name=SERVICE_NAME, sources=PLANNED_SOURCES, snapshot=snapshot)
