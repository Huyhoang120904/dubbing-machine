"""Item business logic.

Endpoints depend on this layer, not on the session directly, so validation and
conflict rules live in one place and stay easy to test.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.item import item as item_crud
from app.db.models.item import Item
from app.schemas.item import ItemCreate, ItemUpdate


class ItemNotFoundError(LookupError):
    """Raised when an item does not exist."""


class ItemConflictError(RuntimeError):
    """Raised when an item violates a uniqueness constraint."""


class ItemService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_items(self, *, skip: int = 0, limit: int = 100) -> tuple[list[Item], int]:
        """Return `(page_of_items, total_count)`."""
        items = await item_crud.get_multi(self.db, skip=skip, limit=limit)
        total = await item_crud.count(self.db)
        return items, total

    async def get_item(self, item_id: int) -> Item:
        db_item = await item_crud.get(self.db, item_id)
        if db_item is None:
            raise ItemNotFoundError(f"Item {item_id} not found")
        return db_item

    async def create_item(self, payload: ItemCreate) -> Item:
        try:
            return await item_crud.create(self.db, obj_in=payload)
        except IntegrityError as exc:
            await self.db.rollback()
            raise ItemConflictError(f"An item named {payload.name!r} already exists") from exc

    async def update_item(self, item_id: int, payload: ItemUpdate) -> Item:
        db_item = await self.get_item(item_id)
        try:
            return await item_crud.update(self.db, db_obj=db_item, obj_in=payload)
        except IntegrityError as exc:
            await self.db.rollback()
            raise ItemConflictError("Item update violates a uniqueness constraint") from exc

    async def delete_item(self, item_id: int) -> None:
        deleted = await item_crud.remove(self.db, obj_id=item_id)
        if deleted is None:
            raise ItemNotFoundError(f"Item {item_id} not found")
