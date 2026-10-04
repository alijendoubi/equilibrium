"""OpenAI Extract: one abstract -> validated claims between known snapshot nodes.

The Responses API is called with a strict JSON schema whose subject/object ids are an enum of
the candidate node ids and whose relation is an enum of a whitelist, so the model cannot name
an entity outside the graph. Every claim is validated again here: unknown ids, relations
outside the whitelist and quotes that are not a verbatim substring of the abstract (after
whitespace normalisation) are dropped and counted, never repaired.

Results are cached per (model, prompt version, PMID, candidate-set hash) in
``data/cache/extract/claims.json`` together with the token usage that produced them, so the
offline pipeline is deterministic and can still report real OpenAI usage.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

from atlas.extract.pubmed import Abstract
from atlas.ingest.common import CACHE_DIR
from atlas.models.evidence import Node, NodeType, Relation
from atlas.reconcile.embeddings import is_offline
from atlas.reconcile.usage import ModelUsage, UsageRecord, usage_from_response

logger = logging.getLogger(__name__)

PROMPT_VERSION = "extract-v1"
CACHE_FORMAT_VERSION = 1
DEFAULT_CLAIMS_PATH = CACHE_DIR / "extract" / "claims.json"
CANDIDATE_TYPES = frozenset({NodeType.GENE, NodeType.DISEASE, NodeType.MECHANISM})
ALLOWED_RELATIONS: tuple[Relation, ...] = (
    Relation.CAUSED_BY,
    Relation.RISK_FACTOR_FOR,
    Relation.PARTICIPATES_IN,
    Relation.HAS_MECHANISM,
    Relation.SHARES_MECHANISM_WITH,
    Relation.CLAIMS,
    Relation.MENTIONS,
)
POLARITIES = ("supports", "contradicts")
CERTAINTIES = ("low", "medium", "high")
MAX_SYNONYMS = 4
INSTRUCTIONS = (
    "You are a biomedical curator. Extract only relations that the abstract itself states "
    "between entities from the candidate list. Use only candidate ids. Directions: "
    "disease caused_by gene; gene risk_factor_for disease; gene participates_in mechanism; "
    "disease has_mechanism mechanism; disease shares_mechanism_with disease. "
    "'quote' must be copied verbatim from the abstract (one sentence or clause). "
    "polarity is 'contradicts' when the text argues against the relation. certainty reflects "
    "the hedging of the text (may/suggests -> low). Return an empty list if nothing qualifies."
)

Polarity = Literal["supports", "contradicts"]
Certainty = Literal["low", "medium", "high"]
_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class Claim:
    """A validated claim: both ids are known nodes, the quote is in the abstract."""

    subject_id: str
    relation: str
    object_id: str
    quote: str
    polarity: Polarity
    certainty: Certainty


@dataclass(frozen=True)
class Extraction:
    """Validated claims for one abstract, how many were dropped, and the usage it cost."""

    pmid: str
    model: str
    claims: tuple[Claim, ...]
    dropped: int
    usage: ModelUsage
    prompt_version: str = PROMPT_VERSION

    def as_json(self) -> dict[str, Any]:
        return {
            "pmid": self.pmid,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "claims": [asdict(c) for c in self.claims],
            "dropped": self.dropped,
            "usage": asdict(self.usage),
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> Extraction:
        return cls(
            pmid=str(data["pmid"]),
            model=str(data["model"]),
            prompt_version=str(data.get("prompt_version", PROMPT_VERSION)),
            claims=tuple(Claim(**c) for c in data.get("claims", ())),
            dropped=int(data.get("dropped", 0)),
            usage=ModelUsage(**data.get("usage", {})),
        )


def candidate_nodes(nodes: Sequence[Node]) -> tuple[Node, ...]:
    """Genes, diseases and mechanisms of the slice, sorted by id (the extraction vocabulary)."""
    return tuple(sorted((n for n in nodes if n.type in CANDIDATE_TYPES), key=lambda n: n.id))


def candidate_hash(candidates: Sequence[Node]) -> str:
    material = json.dumps(sorted([c.id, c.label] for c in candidates))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def claims_key(model: str, pmid: str, candidates: Sequence[Node]) -> str:
    material = json.dumps([model, PROMPT_VERSION, pmid, candidate_hash(candidates)])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class ClaimsCache:
    """Read-only map key -> Extraction; ``with_extraction`` returns a new cache."""

    def __init__(self, path: Path, entries: Mapping[str, Extraction] | None = None):
        self.path = path
        self._entries: Mapping[str, Extraction] = MappingProxyType(dict(entries or {}))

    @classmethod
    def load(cls, path: Path = DEFAULT_CLAIMS_PATH) -> ClaimsCache:
        if not path.is_file():
            return cls(path)
        raw = json.loads(path.read_text(encoding="utf-8")).get("extractions", {})
        return cls(path, {key: Extraction.from_json(value) for key, value in raw.items()})

    def __len__(self) -> int:
        return len(self._entries)

    def get(self, key: str) -> Extraction | None:
        return self._entries.get(key)

    def items(self) -> tuple[tuple[str, Extraction], ...]:
        return tuple(sorted(self._entries.items()))

    def with_extraction(self, key: str, extraction: Extraction) -> ClaimsCache:
        return ClaimsCache(self.path, {**self._entries, key: extraction})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format_version": CACHE_FORMAT_VERSION,
            "extractions": {key: value.as_json() for key, value in self.items()},
        }
        text = json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
        self.path.write_text(text, encoding="utf-8", newline="\n")


def schema(candidate_ids: Sequence[str]) -> dict[str, Any]:
    """Strict structured-output schema; ids and relations are closed enums."""
    claim = {
        "type": "object",
        "properties": {
            "subject_id": {"type": "string", "enum": list(candidate_ids)},
            "relation": {"type": "string", "enum": [r.value for r in ALLOWED_RELATIONS]},
            "object_id": {"type": "string", "enum": list(candidate_ids)},
            "quote": {"type": "string"},
            "polarity": {"type": "string", "enum": list(POLARITIES)},
            "certainty": {"type": "string", "enum": list(CERTAINTIES)},
        },
        "required": ["subject_id", "relation", "object_id", "quote", "polarity", "certainty"],
        "additionalProperties": False,
    }
    return {
        "format": {
            "type": "json_schema",
            "name": "extract_claims",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {"claims": {"type": "array", "items": claim}},
                "required": ["claims"],
                "additionalProperties": False,
            },
        }
    }


def prompt(abstract: Abstract, candidates: Sequence[Node]) -> str:
    lines = ["Candidates (id [type] label; synonyms):"]
    for c in candidates:
        synonyms = "; ".join(c.synonyms[:MAX_SYNONYMS]) or "-"
        lines.append(f"- {c.id} [{c.type.value}] {c.label}; {synonyms}")
    lines += ["", f"PMID {abstract.pmid}. Title: {abstract.title}", "Abstract:", abstract.abstract]
    return "\n".join(lines)


def normalize_ws(text: str) -> str:
    return _WS.sub(" ", text).strip()


def validate_claims(
    raw_claims: Sequence[Any], abstract_text: str, candidate_ids: Sequence[str]
) -> tuple[tuple[Claim, ...], int]:
    """Keep claims with known ids, an allowed relation and a verbatim quote; count the rest."""
    known = frozenset(candidate_ids)
    relations = frozenset(r.value for r in ALLOWED_RELATIONS)
    haystack = normalize_ws(abstract_text)
    kept: dict[tuple[str, str, str], Claim] = {}
    dropped = 0
    for item in raw_claims:
        try:
            claim = Claim(
                subject_id=str(item["subject_id"]),
                relation=str(item["relation"]),
                object_id=str(item["object_id"]),
                quote=normalize_ws(str(item["quote"])),
                polarity=item["polarity"],
                certainty=item["certainty"],
            )
        except (KeyError, TypeError):
            dropped += 1
            continue
        ok = (
            claim.subject_id in known
            and claim.object_id in known
            and claim.subject_id != claim.object_id
            and claim.relation in relations
            and claim.polarity in POLARITIES
            and claim.certainty in CERTAINTIES
            and bool(claim.quote)
            and claim.quote in haystack
        )
        triple = (claim.subject_id, claim.relation, claim.object_id)
        if not ok or triple in kept:
            dropped += 1
            continue
        kept[triple] = claim
    return tuple(kept[t] for t in sorted(kept)), dropped


def parse_output(output_text: str) -> list[Any]:
    try:
        data = json.loads(output_text)
    except ValueError:
        return []
    claims = data.get("claims") if isinstance(data, dict) else None
    return claims if isinstance(claims, list) else []


def extract_abstract(
    abstract: Abstract,
    candidates: Sequence[Node],
    *,
    client: Any,
    model: str,
    cache: ClaimsCache,
) -> tuple[Extraction | None, ClaimsCache, UsageRecord]:
    """Cache first; never calls the API offline or without a client (returns None then)."""
    key = claims_key(model, abstract.pmid, candidates)
    cached = cache.get(key)
    if cached is not None:
        return cached, cache, UsageRecord()
    if client is None or is_offline():
        return None, cache, UsageRecord()
    ids = [c.id for c in candidates]
    response = client.responses.create(
        model=model,
        instructions=INSTRUCTIONS,
        input=prompt(abstract, candidates),
        text=schema(ids),
    )
    usage = usage_from_response(response)
    raw = parse_output(response.output_text)
    claims, dropped = validate_claims(raw, abstract.abstract, ids)
    if dropped:
        logger.info("PMID %s: dropped %d invalid claim(s)", abstract.pmid, dropped)
    extraction = Extraction(abstract.pmid, model, claims, dropped, usage)
    return extraction, cache.with_extraction(key, extraction), UsageRecord.single(model, usage)
