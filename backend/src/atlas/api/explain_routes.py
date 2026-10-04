"""POST /api/v1/explain: cited plain-language explanation of a path (OpenAI, cache, template)."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from atlas.api.deps import StoreDep
from atlas.api.ratelimit import RateLimiter, client_ip
from atlas.config import Settings, get_settings
from atlas.explain.cache import ExplanationCache
from atlas.explain.golden import nodes_for
from atlas.explain.models import ExplainRequest, ExplainResponse
from atlas.explain.service import explain_client, explain_edges

logger = logging.getLogger(__name__)

explain_router = APIRouter(prefix="/api/v1", tags=["explain"])


def _cache(request: Request, settings: Settings) -> ExplanationCache:
    """The app's explain cache, loaded once from disk (live answers are kept in memory)."""
    cache: ExplanationCache | None = getattr(request.app.state, "explain_cache", None)
    if cache is None:
        default = settings.cache_dir / "explain" / "explanations.json"
        path = getattr(request.app.state, "explain_cache_path", None) or default
        cache = ExplanationCache.load(path)
        request.app.state.explain_cache = cache
    return cache


@explain_router.post("/explain", response_model=ExplainResponse)
def explain(
    body: ExplainRequest,
    request: Request,
    store: StoreDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ExplainResponse:
    """Explain the given edges. 404 if any edge id is unknown, 429 if rate limited."""
    limiter: RateLimiter | None = getattr(request.app.state, "explain_limiter", None)
    if limiter is None:
        limiter = RateLimiter(settings.explain_rate_per_minute, window_s=60.0)
        request.app.state.explain_limiter = limiter
    if not limiter.allow(client_ip(request)):
        raise HTTPException(status_code=429, detail="Too many explain requests; try again soon.")
    edges = tuple(store.get_edge(edge_id) for edge_id in body.edge_ids)
    missing = [edge_id for edge_id, edge in zip(body.edge_ids, edges, strict=True) if edge is None]
    if missing:
        raise HTTPException(status_code=404, detail=f"unknown edge id(s): {', '.join(missing)}")
    resolved = tuple(edge for edge in edges if edge is not None)
    outcome = explain_edges(
        resolved,
        nodes_for(store, resolved),
        audience=body.audience,
        client=explain_client(settings) if settings.explain_live else None,
        model=settings.openai_model_explain,
        cache=_cache(request, settings),
    )
    if settings.explain_live:
        request.app.state.explain_cache = outcome.cache
    if outcome.usage.total_calls:
        logger.info("explain openai usage: %s", outcome.usage.as_dict())
    return outcome.response
