"""Generic, model-agnostic data access.

Subclass and set `model`, then add domain-specific queries:

    class UserRepository(BaseRepository[User]):
        model = User

A repository owns query construction and nothing else: no business decisions, and no
`commit()` — services own the transaction boundary. That is what lets `AuthService.refresh`
revoke the old session and insert its replacement in a single transaction.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base class for every repository. Subclasses must set `model`."""

    model: type[ModelType]

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, obj_id: Any) -> ModelType | None:
        """Return one row by primary key, or `None`."""
        return await self.db.get(self.model, obj_id)

    async def get_multi(self, *, skip: int = 0, limit: int = 100) -> list[ModelType]:
        """Return a page of rows ordered by primary key."""
        result = await self.db.execute(
            select(self.model).order_by(self.model.id).offset(skip).limit(limit)  # type: ignore[attr-defined]
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        """Return the total number of rows, ignoring pagination."""
        result = await self.db.execute(select(func.count()).select_from(self.model))
        return int(result.scalar_one())

    async def create(self, *, obj_in: BaseModel) -> ModelType:
        """Insert a row and flush it; the service commits."""
        db_obj = self.model(**obj_in.model_dump())
        self.db.add(db_obj)
        await self.db.flush()
        await self.db.refresh(db_obj)
        return db_obj

    async def update(self, *, db_obj: ModelType, obj_in: BaseModel | dict[str, Any]) -> ModelType:
        """Apply a partial update to `db_obj` and flush it."""
        data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(db_obj, field, value)
        await self.db.flush()
        await self.db.refresh(db_obj)
        return db_obj

    async def remove(self, *, obj_id: Any) -> ModelType | None:
        """Delete a row by primary key; return the deleted instance or `None`."""
        db_obj = await self.get(obj_id)
        if db_obj is None:
            return None
        await self.db.delete(db_obj)
        await self.db.flush()
        return db_obj
