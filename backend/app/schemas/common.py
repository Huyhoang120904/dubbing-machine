"""Shared pydantic response schemas."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Envelope for paginated list responses."""

    items: list[T]
    total: int = Field(description="Total rows matching the query, ignoring pagination")
    limit: int = Field(description="Maximum rows requested per page")
    offset: int = Field(description="Number of rows skipped")


class ErrorDetail(BaseModel):
    """Response body for error responses."""

    detail: str
