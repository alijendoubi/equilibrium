"""Draft evidence model: typed, immutable nodes and provenance-carrying edges."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

CURIE_PATTERN = r"^[A-Za-z][A-Za-z0-9_.\-]*:\S+$"

_FROZEN = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class NodeType(StrEnum):
    """Kinds of entities in the atlas graph."""

    DISEASE = "disease"
    GENE = "gene"
    VARIANT = "variant"
    MECHANISM = "mechanism"
    PHENOTYPE = "phenotype"
    PATIENT_GROUP = "patient_group"
    PUBLICATION = "publication"
    STUDY = "study"
    ASSET = "asset"
    INVESTIGATOR = "investigator"
    FUNDER = "funder"


class EvidenceType(StrEnum):
    """How a claim was established."""

    OBSERVED = "observed"
    INFERRED = "inferred"
    CURATED = "curated"


class Provenance(BaseModel):
    """Where a claim came from and when it was retrieved."""

    model_config = _FROZEN

    source: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    url: HttpUrl | None = None
    retrieved_at: datetime


class Node(BaseModel):
    """A graph entity identified by a stable CURIE-like id, e.g. "MONDO:0007739"."""

    model_config = _FROZEN

    id: str = Field(pattern=CURIE_PATTERN)
    type: NodeType
    label: str = Field(min_length=1)
    synonyms: tuple[str, ...] = ()


class Edge(BaseModel):
    """A directed, provenance-backed relation between two nodes."""

    model_config = _FROZEN

    source_id: str = Field(pattern=CURIE_PATTERN)
    target_id: str = Field(pattern=CURIE_PATTERN)
    relation: str = Field(min_length=1)
    provenance: Provenance
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    evidence_type: EvidenceType
    contradicted_by: tuple[str, ...] = ()

    @field_validator("contradicted_by")
    @classmethod
    def _no_blank_contradictions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() for item in value):
            msg = "contradicted_by entries must be non-empty identifiers"
            raise ValueError(msg)
        return value
