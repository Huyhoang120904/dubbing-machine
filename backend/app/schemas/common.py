"""Shared response schemas."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class UnifiedResponse(BaseModel, Generic[T]):
    """The one response envelope: auth successes and every error response."""

    status_code: int = Field(description="Mirrors the HTTP status code")
    message: str = Field(description="Human-readable result", examples=["OK"])
    data: T | None = Field(default=None, description="Payload; None on errors")


def unified(
    data: T | None = None,
    *,
    status_code: int = 200,
    message: str = "OK",
) -> UnifiedResponse[T]:
    """Build the envelope, so every call site stays a single readable expression."""
    return UnifiedResponse[T](status_code=status_code, message=message, data=data)
