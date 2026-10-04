"""Validate a model explanation before it is served or cached (PROJECT_PLAN 8d).

Rejects: unparseable/empty output, a step with no citation, a citation outside the request,
a multi-digit number or decimal that does not appear in the edge facts, and a contradicted
edge that no step cites.
"""

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass

from atlas.models.evidence import Edge

# Single digits ("type 2") are allowed; 2+ digit numbers and decimals must come from the edges.
_NUMBER = re.compile(r"\d+\.\d+|\d{2,}")


class ExplanationRejectedError(ValueError):
    """The model output broke a citation or faithfulness rule."""


@dataclass(frozen=True)
class DraftStep:
    text: str
    edge_ids: tuple[str, ...]
    is_hypothesis: bool


@dataclass(frozen=True)
class Draft:
    """A validated model explanation (not yet wrapped in an ExplainResponse)."""

    steps: tuple[DraftStep, ...]
    summary: str
    caveats: tuple[str, ...]


def _parse(output_text: str) -> Draft:
    try:
        data = json.loads(output_text)
        steps = tuple(
            DraftStep(
                text=str(item["text"]).strip(),
                edge_ids=tuple(str(i).strip() for i in item["edge_ids"]),
                is_hypothesis=bool(item["is_hypothesis"]),
            )
            for item in data["steps"]
        )
        summary = str(data["summary"]).strip()
        caveats = tuple(str(c).strip() for c in data["caveats"] if str(c).strip())
    except (ValueError, KeyError, TypeError) as exc:
        raise ExplanationRejectedError(f"unparseable model output: {exc}") from exc
    return Draft(steps=steps, summary=summary, caveats=caveats)


def _check_numbers(text: str, context: str) -> None:
    for number in _NUMBER.findall(text):
        if number not in context:
            raise ExplanationRejectedError(f"number {number!r} is not in the edge facts")


def validate_output(output_text: str, edges: Sequence[Edge], context: str) -> Draft:
    """Parse and check the model output against the requested edges; raise if it fails."""
    draft = _parse(output_text)
    allowed = {edge.id for edge in edges}
    if not draft.steps or not draft.summary:
        raise ExplanationRejectedError("empty explanation")
    cited: set[str] = set()
    for step in draft.steps:
        if not step.text:
            raise ExplanationRejectedError("empty step text")
        if not step.edge_ids:
            raise ExplanationRejectedError("a step cites no edge")
        unknown = [i for i in step.edge_ids if i not in allowed]
        if unknown:
            raise ExplanationRejectedError(f"step cites unknown edge ids {unknown}")
        _check_numbers(step.text, context)
        cited.update(step.edge_ids)
    _check_numbers(draft.summary, context)
    uncited_contradicted = [e.id for e in edges if e.contradicted_by and e.id not in cited]
    if uncited_contradicted:
        raise ExplanationRejectedError(f"contradicted edges not mentioned: {uncited_contradicted}")
    return draft
