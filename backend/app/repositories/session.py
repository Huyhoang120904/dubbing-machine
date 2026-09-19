"""Repository for refresh-token sessions."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.db.models.user_session import UserSession
from app.repositories.base import BaseRepository


class UserSessionRepository(BaseRepository[UserSession]):
    model = UserSession

    async def get_by_token_hash(self, token_hash: str) -> UserSession | None:
        """Look a session up by the SHA-256 digest of its refresh token."""
        result = await self.db.execute(
            select(UserSession).where(UserSession.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def add(self, *, user_id: int, token_hash: str, expires_at: datetime) -> UserSession:
        """Insert a session row and flush it; the service commits."""
        session = UserSession(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def revoke(self, session: UserSession, *, when: datetime) -> UserSession:
        """Mark a session revoked. The row is kept, never deleted."""
        session.revoked_at = when
        await self.db.flush()
        await self.db.refresh(session)
        return session
