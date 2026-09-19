"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import engine

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hooks: release pooled connections on shutdown."""
    logger.info("%s starting (env=%s)", settings.app_name, settings.app_env)
    try:
        yield
    finally:
        await engine.dispose()
        logger.info("%s stopped", settings.app_name)


def create_app() -> FastAPI:
    """Build and configure the application.

    A factory (rather than a module-level literal) so tests can build isolated
    instances with overridden dependencies.
    """
    configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/health", tags=["health"], summary="Liveness probe (unversioned)")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", tags=["meta"], summary="Service metadata")
    async def root() -> dict[str, str]:
        return {
            "app": settings.app_name,
            "env": settings.app_env,
            "docs": "/docs",
            "api": settings.api_v1_prefix,
        }

    return app


app = create_app()
