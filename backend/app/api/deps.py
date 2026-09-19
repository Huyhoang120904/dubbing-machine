"""Shared FastAPI dependencies (annotated types for clean endpoint signatures)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.item import ItemService

SessionDep = Annotated[AsyncSession, Depends(get_db)]


class PaginationParams:
    """Validated `skip`/`limit` query parameters."""

    def __init__(
        self,
        skip: int = Query(0, ge=0, description="Number of rows to skip"),
        limit: int = Query(100, ge=1, le=500, description="Maximum rows to return"),
    ) -> None:
        self.skip = skip
        self.limit = limit


PaginationDep = Annotated[PaginationParams, Depends()]


def get_item_service(db: SessionDep) -> ItemService:
    """Provide an `ItemService` bound to the request-scoped session."""
    return ItemService(db)


ItemServiceDep = Annotated[ItemService, Depends(get_item_service)]
