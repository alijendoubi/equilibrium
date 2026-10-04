"""Extraction quality scaffold (PROJECT_PLAN 8e, issue #35).

Gold format, one JSON object per line in ``data/eval/gold_claims.jsonl``::

    {"pmid": "PMID:12345", "subject_id": "HGNC:4177", "relation": "risk_factor_for",
     "object_id": "MONDO:0008199"}

Only PMIDs that appear in the gold file are scored, so a partially labelled corpus gives
honest numbers: precision = matched / predicted, recall = matched / gold (exact triples).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from atlas.extract.claims import Extraction
from atlas.ingest.common import DATA_DIR

DEFAULT_GOLD_PATH = DATA_DIR / "eval" / "gold_claims.jsonl"

Triple = tuple[str, str, str, str]


@dataclass(frozen=True)
class EvalResult:
    gold: int
    predicted: int
    matched: int
    pmids: int

    @property
    def precision(self) -> float:
        return self.matched / self.predicted if self.predicted else 0.0

    @property
    def recall(self) -> float:
        return self.matched / self.gold if self.gold else 0.0

    @property
    def f1(self) -> float:
        total = self.precision + self.recall
        return 2 * self.precision * self.recall / total if total else 0.0

    def as_dict(self) -> dict[str, float | int]:
        return {
            "pmids_scored": self.pmids,
            "gold": self.gold,
            "predicted": self.predicted,
            "matched": self.matched,
            "precision": round(self.precision, 3),
            "recall": round(self.recall, 3),
            "f1": round(self.f1, 3),
        }


def _pmid(value: object) -> str:
    text = str(value).strip()
    return text if text.startswith("PMID:") else f"PMID:{text}"


def load_gold(path: Path = DEFAULT_GOLD_PATH) -> tuple[Triple, ...]:
    if not path.is_file():
        return ()
    triples = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        triples.append((_pmid(row["pmid"]), row["subject_id"], row["relation"], row["object_id"]))
    return tuple(triples)


def predicted_triples(extractions: Iterable[Extraction]) -> set[Triple]:
    return {
        (_pmid(e.pmid), c.subject_id, c.relation, c.object_id)
        for e in extractions
        for c in e.claims
    }


def evaluate(extractions: Sequence[Extraction], gold: Sequence[Triple]) -> EvalResult:
    gold_set = set(gold)
    scored = {t[0] for t in gold_set}
    predicted = {t for t in predicted_triples(extractions) if t[0] in scored}
    return EvalResult(
        gold=len(gold_set),
        predicted=len(predicted),
        matched=len(predicted & gold_set),
        pmids=len(scored),
    )
