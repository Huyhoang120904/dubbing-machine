"""CRUD operations for `Item`."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.db.models.item import Item
from app.schemas.item import ItemCreate, ItemUpdate


class CRUDItem(CRUDBase[Item, ItemCreate, ItemUpdate]):
    async def get_by_name(self, db: AsyncSession, *, name: str) -> Item | None:
        """Fetch an item by its unique name."""
        result = await db.execute(select(Item).where(Item.name == name))
        return result.scalar_one_or_none()


item = CRUDItem(Item)
