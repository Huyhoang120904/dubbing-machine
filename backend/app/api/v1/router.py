"""Aggregate router for API version 1."""

from fastapi import APIRouter

from app.api.v1.endpoints import health, items

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(items.router)

__all__ = ["api_router"]
