"""Repository for `User`."""

from __future__ import annotations

from sqlalchemy import select

from app.db.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        """Fetch a user by the unique email column."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def add(self, *, email: str, hashed_password: str) -> User:
        """Insert a user and flush it; the service commits."""
        user = User(email=email, hashed_password=hashed_password)
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user
