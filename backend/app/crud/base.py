"""Generic, model-agnostic CRUD operations.

Subclass and bind a model/schemas pair, then add domain-specific queries:

    class CRUDItem(CRUDBase[Item, ItemCreate, ItemUpdate]):
        ...
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: type[ModelType]) -> None:
        self.model = model

    async def get(self, db: AsyncSession, obj_id: Any) -> ModelType | None:
        """Return one row by primary key, or `None`."""
        return await db.get(self.model, obj_id)

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ModelType]:
        """Return a page of rows ordered by primary key."""
        result = await db.execute(
            select(self.model).order_by(self.model.id).offset(skip).limit(limit)  # type: ignore[attr-defined]
        )
        return list(result.scalars().all())

    async def count(self, db: AsyncSession) -> int:
        """Return the total number of rows, ignoring pagination."""
        result = await db.execute(select(func.count()).select_from(self.model))
        return int(result.scalar_one())

    async def create(self, db: AsyncSession, *, obj_in: CreateSchemaType) -> ModelType:
        """Insert a row and commit it."""
        db_obj = self.model(**obj_in.model_dump())
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: UpdateSchemaType | dict[str, Any],
    ) -> ModelType:
        """Apply a partial update to `db_obj` and commit it."""
        data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(db_obj, field, value)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def remove(self, db: AsyncSession, *, obj_id: Any) -> ModelType | None:
        """Delete a row by primary key; return the deleted instance or `None`."""
        db_obj = await db.get(self.model, obj_id)
        if db_obj is None:
            return None
        await db.delete(db_obj)
        await db.commit()
        return db_obj
