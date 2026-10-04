"""Explain orchestration: cache -> live OpenAI call (validated, one retry) -> template.

Offline (ATLAS_OFFLINE=1) or without a client, only the cache and the template are used, so
the demo never depends on a live call.
"""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from openai import OpenAIError
from pydantic import ValidationError

from atlas.config import Settings
from atlas.explain.cache import ExplanationCache, explanation_key
from atlas.explain.models import Audience, ExplainResponse, ExplainStep
from atlas.explain.prompt import PROMPT_VERSION, build_context, instructions_for, response_schema
from atlas.explain.templates import template_explanation
from atlas.explain.validate import Draft, ExplanationRejectedError, validate_output
from atlas.extract.openai_client import create_openai_client
from atlas.models.evidence import Edge, Node
from atlas.reconcile.embeddings import is_offline
from atlas.reconcile.usage import UsageRecord, usage_from_response

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2  # first try + one retry, then the template
LIVE_TIMEOUT_S = 30.0
MAX_OUTPUT_TOKENS = 1500


def explain_client(settings: Settings) -> Any:
    """An OpenAI client for live Explain calls, or None when offline or no key is set."""
    if is_offline() or not settings.has_openai_key:
        return None
    return create_openai_client(settings).with_options(timeout=LIVE_TIMEOUT_S, max_retries=0)


@dataclass(frozen=True)
class ExplainOutcome:
    """The response, the (possibly extended) cache and the OpenAI usage it cost."""

    response: ExplainResponse
    cache: ExplanationCache
    usage: UsageRecord


def _from_cache(entry: Mapping[str, Any]) -> ExplainResponse | None:
    try:
        return ExplainResponse(
            steps=[ExplainStep.model_validate(step) for step in entry["steps"]],
            summary=str(entry["summary"]),
            caveats=[str(c) for c in entry["caveats"]],
            source="cache",
            model=str(entry["model"]),
            prompt_version=str(entry["prompt_version"]),
            ai_generated=True,
        )
    except (KeyError, TypeError, ValidationError):
        logger.warning("ignoring malformed explain cache entry")
        return None


def _live_response(draft: Draft, model: str) -> ExplainResponse:
    return ExplainResponse(
        steps=[
            ExplainStep(text=s.text, edge_ids=list(s.edge_ids), is_hypothesis=s.is_hypothesis)
            for s in draft.steps
        ],
        summary=draft.summary,
        caveats=list(draft.caveats),
        source="live",
        model=model,
        prompt_version=PROMPT_VERSION,
        ai_generated=True,
    )


def _cache_entry(
    response: ExplainResponse, audience: Audience, edges: Sequence[Edge]
) -> dict[str, Any]:
    payload = response.model_dump(
        include={"steps", "summary", "caveats", "model", "prompt_version"}
    )
    return {**payload, "audience": audience, "edge_ids": [e.id for e in edges]}


def _call_model(
    client: Any, model: str, audience: Audience, edges: Sequence[Edge], context: str
) -> tuple[Draft | None, UsageRecord]:
    """Up to MAX_ATTEMPTS validated calls; None when every attempt fails."""
    usage = UsageRecord()
    schema = response_schema([e.id for e in edges])
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            raw = client.responses.create(
                model=model,
                instructions=instructions_for(audience),
                input=context,
                text=schema,
                max_output_tokens=MAX_OUTPUT_TOKENS,
            )
            usage = usage.merge(UsageRecord.single(model, usage_from_response(raw)))
            return validate_output(raw.output_text, edges, context), usage
        except ExplanationRejectedError as exc:
            logger.warning("explain attempt %d rejected: %s", attempt, exc)
        except (OpenAIError, AttributeError, TypeError) as exc:
            logger.warning("explain attempt %d failed: %s", attempt, type(exc).__name__)
    return None, usage


def explain_edges(
    edges: Sequence[Edge],
    nodes: Mapping[str, Node],
    *,
    audience: Audience,
    client: Any,
    model: str,
    cache: ExplanationCache,
) -> ExplainOutcome:
    """Explain ``edges`` (path order). Never raises for model problems: falls back to template."""
    key = explanation_key(model, audience, edges, nodes)
    entry = cache.get(key)
    if entry is not None:
        cached = _from_cache(entry)
        if cached is not None:
            return ExplainOutcome(cached, cache, UsageRecord())
    if client is None or is_offline():
        return ExplainOutcome(template_explanation(edges, nodes, audience), cache, UsageRecord())
    draft, usage = _call_model(client, model, audience, edges, build_context(edges, nodes))
    if draft is None:
        logger.warning("explain falling back to template after %d attempts", MAX_ATTEMPTS)
        return ExplainOutcome(template_explanation(edges, nodes, audience), cache, usage)
    response = _live_response(draft, model)
    return ExplainOutcome(
        response, cache.with_entry(key, _cache_entry(response, audience, edges)), usage
    )
