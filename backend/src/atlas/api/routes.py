"""Top-level API routes: health check and service metadata."""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from atlas import __version__

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

router = APIRouter()


class HealthResponse(BaseModel):
    """Liveness payload."""

    model_config = ConfigDict(frozen=True)

    status: str
    version: str


class MetaResponse(BaseModel):
    """Service metadata payload."""

    model_config = ConfigDict(frozen=True)

    name: str
    sources: tuple[str, ...]


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe."""
    return HealthResponse(status="ok", version=__version__)


@router.get("/api/v1/meta", response_model=MetaResponse)
def meta() -> MetaResponse:
    """Service name and the planned data sources."""
    return MetaResponse(name=SERVICE_NAME, sources=PLANNED_SOURCES)
