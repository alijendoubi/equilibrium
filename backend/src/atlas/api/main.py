"""FastAPI application entrypoint: `atlas.api.main:app`."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas import __version__
from atlas.api.routes import router
from atlas.config import Settings, get_settings
from atlas.logging_config import configure_logging

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application from settings."""
    resolved = settings if settings is not None else get_settings()
    configure_logging(resolved.log_level)

    application = FastAPI(title="Equilibrium Atlas", version=__version__)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved.cors_origin_list),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    application.include_router(router)
    logger.info(
        "Atlas API configured (model=%s, openai_key_configured=%s, cors_origins=%d)",
        resolved.openai_model,
        resolved.has_openai_key,
        len(resolved.cors_origin_list),
    )
    return application


app = create_app()
