"""Evidence model v2: typed, immutable nodes and provenance-carrying edges.

See docs/EVIDENCE_MODEL.md for the contract. If code and that document disagree, fix one of
them in the same PR.
"""

import hashlib
import json
from collections.abc import Iterator, Mapping
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    GetCoreSchemaHandler,
    HttpUrl,
    ModelWrapValidatorHandler,
    StringConstraints,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_core import core_schema

CURIE_PATTERN = r"^[A-Za-z][A-Za-z0-9_.\-]*:\S+$"
EDGE_ID_PREFIX = "E:"
EDGE_ID_HEX_LENGTH = 16
EDGE_ID_PATTERN = rf"^{EDGE_ID_PREFIX}[0-9a-f]{{{EDGE_ID_HEX_LENGTH}}}$"
EXTRACTOR_PATTERN = r"^[a-z][a-z0-9_\-]*:\S+$"
LLM_EXTRACTOR_PREFIX = "openai:"

_FROZEN = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

Curie = Annotated[str, StringConstraints(strip_whitespace=True, pattern=CURIE_PATTERN)]
EdgeId = Annotated[str, StringConstraints(strip_whitespace=True, pattern=EDGE_ID_PATTERN)]
NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class FrozenStrMap(Mapping[str, str]):
    """An immutable, hashable str -> str mapping usable as a field on frozen models.

    Validates from any mapping (keys must be non-blank), serializes back to a plain dict.
    """

    __slots__ = ("_data",)

    def __init__(self, data: Mapping[str, str] | None = None) -> None:
        self._data: dict[str, str] = dict(data or {})

    def __getitem__(self, key: str) -> str:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __hash__(self) -> int:
        return hash(frozenset(self._data.items()))

    def __repr__(self) -> str:
        return f"FrozenStrMap({self._data!r})"

    @classmethod
    def _validate(cls, value: dict[str, str]) -> "FrozenStrMap":
        stripped = {key.strip(): item.strip() for key, item in value.items()}
        if any(not key for key in stripped):
            raise ValueError("mapping keys must be non-empty")
        return cls(stripped)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        from_dict = core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.dict_schema(core_schema.str_schema(), core_schema.str_schema()),
        )
        return core_schema.json_or_python_schema(
            json_schema=from_dict,
            python_schema=core_schema.union_schema(
                [core_schema.is_instance_schema(cls), from_dict]
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(dict),
        )


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


class Relation(StrEnum):
    """Controlled edge vocabulary. Direction is always source_id -> target_id.

    Extend by adding a member here and a row to docs/EVIDENCE_MODEL.md in the same PR.
    """

    CAUSED_BY = "caused_by"
    RISK_FACTOR_FOR = "risk_factor_for"
    HAS_VARIANT = "has_variant"
    VARIANT_ASSOCIATED_WITH = "variant_associated_with"
    HAS_MECHANISM = "has_mechanism"
    PARTICIPATES_IN = "participates_in"
    HAS_PHENOTYPE = "has_phenotype"
    SHARES_MECHANISM_WITH = "shares_mechanism_with"
    SIMILAR_PHENOTYPE_TO = "similar_phenotype_to"
    MENTIONS = "mentions"
    CLAIMS = "claims"
    AUTHORED_BY = "authored_by"
    STUDIES_CONDITION = "studies_condition"
    TESTS_INTERVENTION = "tests_intervention"
    INVESTIGATES = "investigates"
    FUNDS = "funds"
    WORKS_ON = "works_on"
    REPRESENTS = "represents"
    OPERATES = "operates"
    CONTRADICTS = "contradicts"


class Provenance(BaseModel):
    """Where a claim came from, which release, and who or what extracted it."""

    model_config = _FROZEN

    source: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    url: HttpUrl | None = None
    retrieved_at: datetime
    source_version: str | None = Field(default=None, min_length=1)
    evidence_quote: str | None = Field(default=None, min_length=1)
    extractor: str | None = Field(default=None, pattern=EXTRACTOR_PATTERN)
    supporting_edge_ids: tuple[EdgeId, ...] = ()


class Node(BaseModel):
    """A graph entity identified by a stable CURIE-like id, e.g. "HGNC:4177" (GBA1)."""

    model_config = _FROZEN

    id: str = Field(pattern=CURIE_PATTERN)
    type: NodeType
    label: str = Field(min_length=1)
    synonyms: tuple[str, ...] = ()
    xrefs: tuple[Curie, ...] = ()
    attributes: FrozenStrMap = Field(default_factory=FrozenStrMap)


def compute_edge_id(
    source_id: str,
    relation: str,
    target_id: str,
    provenance_source: str,
    source_record_id: str,
) -> str:
    """Deterministic edge id: same assertion from the same record -> same id.

    Hashes a canonical JSON array so field values containing separators cannot collide.
    """
    canonical = json.dumps(
        [source_id, str(relation), target_id, provenance_source, source_record_id],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{EDGE_ID_PREFIX}{digest[:EDGE_ID_HEX_LENGTH]}"


class Edge(BaseModel):
    """A directed, provenance-backed relation between two nodes."""

    model_config = _FROZEN

    source_id: str = Field(pattern=CURIE_PATTERN)
    target_id: str = Field(pattern=CURIE_PATTERN)
    relation: Relation
    provenance: Provenance
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    evidence_type: EvidenceType
    contradicted_by: tuple[str, ...] = ()
    qualifiers: FrozenStrMap = Field(default_factory=FrozenStrMap)
    confidence_reasons: tuple[NonBlank, ...] = ()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def id(self) -> str:
        """Deterministic id derived from the assertion and its source record."""
        return compute_edge_id(
            self.source_id,
            self.relation.value,
            self.target_id,
            self.provenance.source,
            self.provenance.source_record_id,
        )

    @field_validator("contradicted_by")
    @classmethod
    def _no_blank_contradictions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() for item in value):
            msg = "contradicted_by entries must be non-empty identifiers"
            raise ValueError(msg)
        return value

    @model_validator(mode="wrap")
    @classmethod
    def _accept_matching_id(cls, data: Any, handler: ModelWrapValidatorHandler[Self]) -> Self:
        """Allow a serialized edge (which carries `id`) to round-trip, if the id still matches."""
        claimed_id: object = None
        if isinstance(data, Mapping) and "id" in data:
            data = dict(data)
            claimed_id = data.pop("id")
        edge = handler(data)
        if claimed_id is not None and claimed_id != edge.id:
            msg = f"edge id {claimed_id!r} does not match its content (expected {edge.id!r})"
            raise ValueError(msg)
        return edge

    @model_validator(mode="after")
    def _evidence_is_checkable(self) -> Self:
        """Observed/curated edges need a URL; inferred edges without one need supporting edges."""
        provenance = self.provenance
        if provenance.url is None:
            if self.evidence_type is not EvidenceType.INFERRED:
                msg = f"{self.evidence_type.value} edges must have provenance.url"
                raise ValueError(msg)
            if not provenance.supporting_edge_ids:
                msg = "inferred edges without provenance.url must list supporting_edge_ids"
                raise ValueError(msg)
        extractor = provenance.extractor or ""
        if extractor.startswith(LLM_EXTRACTOR_PREFIX) and self.evidence_type is not (
            EvidenceType.INFERRED
        ):
            msg = "LLM-extracted edges must have evidence_type 'inferred'"
            raise ValueError(msg)
        if self.id in provenance.supporting_edge_ids:
            raise ValueError("an edge cannot list itself in supporting_edge_ids")
        return self
