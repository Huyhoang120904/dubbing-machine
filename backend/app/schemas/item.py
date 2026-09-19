"""Request/response schemas for `Item`."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ItemBase(BaseModel):
    name: str = Field(min_length=1, max_length=255, examples=["Widget"])
    description: str | None = Field(default=None, max_length=2000, examples=["A shiny widget"])


class ItemCreate(ItemBase):
    """Payload for `POST /items`."""


class ItemUpdate(BaseModel):
    """Payload for `PATCH /items/{id}` — every field is optional."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class ItemRead(ItemBase):
    """Item as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
