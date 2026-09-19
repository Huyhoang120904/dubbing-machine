"""Liveness/readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import text

from app.api.deps import SessionDep
from app.core.config import get_settings

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health", status_code=status.HTTP_200_OK, summary="Health check")
async def health() -> dict[str, str]:
    """Cheap liveness probe — does not touch the database."""
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


@router.get("/health/db", status_code=status.HTTP_200_OK, summary="Database readiness check")
async def health_db(db: SessionDep) -> dict[str, str]:
    """Readiness probe: verifies a working round-trip to the database."""
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}
