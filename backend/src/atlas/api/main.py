"""FastAPI application entrypoint: `atlas.api.main:app`."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas import __version__
from atlas.api.cluster_routes import router as cluster_router
from atlas.api.explain_routes import explain_router
from atlas.api.graph_routes import router as graph_router
from atlas.api.map_routes import router as map_router
from atlas.api.routes import router
from atlas.config import Settings, get_settings
from atlas.graph.clusters import build_cluster_index
from atlas.graph.store import GraphStore, load_store
from atlas.logging_config import configure_logging
from atlas.reconcile.embeddings import EmbeddingCache
from atlas.reconcile.search import SearchIndex

logger = logging.getLogger(__name__)


def build_search_index(store: GraphStore | None, settings: Settings) -> SearchIndex | None:
    """Search index over the snapshot; semantic hits only from the committed embedding cache."""
    if store is None:
        return None
    cache_dir = settings.snapshot_path.parent.parent / "cache" / "embeddings"
    embeddings: EmbeddingCache | None = None
    try:
        embeddings = EmbeddingCache.load(settings.openai_embed_model, cache_dir)
    except (OSError, ValueError) as exc:
        logger.warning("embedding cache unreadable (%s); search is lexical only", exc)
    if embeddings is not None and len(embeddings) == 0:
        embeddings = None
    return SearchIndex.build(store.nodes(), embeddings)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application from settings."""
    resolved = settings if settings is not None else get_settings()
    configure_logging(resolved.log_level)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        # Load the snapshot once; the app still starts (and /health says why) if it is missing.
        store, status = load_store(resolved.snapshot_path)
        application.state.store = store
        application.state.snapshot_status = status
        application.state.search_index = build_search_index(store, resolved)
        application.state.cluster_index = build_cluster_index(store) if store else None
        yield

    application = FastAPI(title="Equilibrium Atlas", version=__version__, lifespan=lifespan)
    application.state.store = None
    application.state.snapshot_status = None
    application.state.search_index = None
    application.state.cluster_index = None
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved.cors_origin_list),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    application.include_router(router)
    application.include_router(graph_router)
    application.include_router(cluster_router)
    application.include_router(map_router)
    application.include_router(explain_router)
    logger.info(
        "Atlas API configured (models: extract=%s explain=%s reconcile=%s embed=%s, "
        "openai_key_configured=%s, cors_origins=%d)",
        resolved.openai_model_extract,
        resolved.openai_model_explain,
        resolved.openai_model_reconcile,
        resolved.openai_embed_model,
        resolved.has_openai_key,
        len(resolved.cors_origin_list),
    )
    return application


app = create_app()
