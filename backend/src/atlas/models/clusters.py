"""Cluster API response models (issue #20); mirrored in frontend/src/lib/api/types.ts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from atlas.models.evidence import Node

_FROZEN = ConfigDict(frozen=True)

ClusterEdgeKind = Literal["within", "bridge"]


class ClusterSummary(BaseModel):
    model_config = _FROZEN

    id: str
    label: str
    size: int = Field(ge=1)
    member_ids: tuple[str, ...]


class ClusterMethod(BaseModel):
    """How the clusters were computed, so the UI can say it plainly."""

    model_config = _FROZEN

    description: str
    weights: dict[str, float]
    phenotype_ic_floor: float
    edge_threshold: float
    seed: int


class ClustersResponse(BaseModel):
    model_config = _FROZEN

    clusters: tuple[ClusterSummary, ...]
    method: ClusterMethod


class ClusterNode(BaseModel):
    """A disease drawn in a cluster view: a member, or the far end of a bridge/counterexample."""

    model_config = _FROZEN

    node: Node
    cluster_id: str
    is_member: bool
    degree: int = Field(ge=0)


class SharedFeature(BaseModel):
    """A gene, GO mechanism or phenotype shared by two or more members."""

    model_config = _FROZEN

    node: Node
    member_ids: tuple[str, ...]
    ic: float | None = None


class ClusterFeatures(BaseModel):
    model_config = _FROZEN

    genes: tuple[SharedFeature, ...]
    mechanisms: tuple[SharedFeature, ...]
    phenotypes: tuple[SharedFeature, ...]


class ClusterEdge(BaseModel):
    """A similarity link to draw: ``within`` the cluster (solid) or a ``bridge`` (dashed)."""

    model_config = _FROZEN

    source_id: str
    target_id: str
    kind: ClusterEdgeKind
    score: float = Field(ge=0.0, le=1.0)
    phenotype_score: float = Field(ge=0.0, le=1.0)
    gene_score: float = Field(ge=0.0, le=1.0)
    mechanism_score: float = Field(ge=0.0, le=1.0)
    reasons: tuple[str, ...]


class Bridge(BaseModel):
    """One of the strongest similarities from a member to a disease in another cluster."""

    model_config = _FROZEN

    member_id: str
    other_id: str
    other_cluster_id: str
    score: float = Field(ge=0.0, le=1.0)
    reasons: tuple[str, ...]


class Counterexample(BaseModel):
    """Same gene, different cluster: the gene alone does not decide the grouping."""

    model_config = _FROZEN

    gene: Node
    member_id: str
    other_id: str
    other_cluster_id: str
    score: float = Field(ge=0.0, le=1.0)
    note: str


class ClusterDetail(BaseModel):
    model_config = _FROZEN

    id: str
    label: str
    size: int = Field(ge=1)
    member_ids: tuple[str, ...]
    nodes: tuple[ClusterNode, ...]
    features: ClusterFeatures
    edges: tuple[ClusterEdge, ...]
    bridges: tuple[Bridge, ...]
    counterexamples: tuple[Counterexample, ...]
