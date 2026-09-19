"""Authentication business logic.

The only layer that commits: repositories flush, and this class decides what one
transaction means. Routes translate its typed errors into HTTP status codes.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    ensure_utc,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    utcnow,
    verify_password_or_dummy,
)
from app.db.models.user import User
from app.db.models.user_session import UserSession
from app.repositories.session import UserSessionRepository
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest
from app.schemas.user import UserCreate


class EmailAlreadyRegisteredError(RuntimeError):
    """Raised when registration hits an existing email."""


class InvalidCredentialsError(RuntimeError):
    """Raised when an email/password pair does not match an account."""


class InvalidSessionError(RuntimeError):
    """Raised for an unknown, expired, revoked, or foreign refresh token."""


def _normalize_email(email: str) -> str:
    """The single place that decides the stored form of an email address."""
    return email.strip().lower()


class AuthService:
    def __init__(
        self,
        db: AsyncSession,
        users: UserRepository,
        sessions: UserSessionRepository,
    ) -> None:
        self.db = db
        self.users = users
        self.sessions = sessions

    async def register(self, payload: UserCreate) -> User:
        """Create an account, or raise `EmailAlreadyRegisteredError`."""
        email = _normalize_email(payload.email)
        if await self.users.get_by_email(email) is not None:
            raise EmailAlreadyRegisteredError("An account with this email already exists")

        user = await self.users.add(email=email, hashed_password=hash_password(payload.password))
        try:
            await self.db.commit()
        except IntegrityError as exc:
            # Two concurrent registrations for one email: the unique index wins the race.
            await self.db.rollback()
            raise EmailAlreadyRegisteredError("An account with this email already exists") from exc
        return user

    async def login(self, payload: LoginRequest) -> tuple[str, str]:
        """Return `(access_token, refresh_token)`, or raise `InvalidCredentialsError`."""
        user = await self.users.get_by_email(_normalize_email(payload.email))
        # Always run a bcrypt check, so an unknown email is not identifiable by timing.
        if not verify_password_or_dummy(payload.password, user.hashed_password if user else None):
            raise InvalidCredentialsError("Invalid email or password")

        tokens = await self._issue_tokens(user.id)
        await self.db.commit()
        return tokens

    async def refresh(self, refresh_token: str) -> tuple[str, str]:
        """Rotate a session: revoke the presented token and issue a fresh pair."""
        session = await self._live_session(refresh_token)
        await self.sessions.revoke(session, when=utcnow())
        tokens = await self._issue_tokens(session.user_id)
        await self.db.commit()  # the revoke and the replacement land together
        return tokens

    async def logout(self, user: User, refresh_token: str) -> None:
        """Revoke one of `user`'s own sessions, or raise `InvalidSessionError`."""
        session = await self._live_session(refresh_token)
        if session.user_id != user.id:
            raise InvalidSessionError("Invalid refresh token")

        await self.sessions.revoke(session, when=utcnow())
        await self.db.commit()

    async def get_user(self, user_id: int) -> User | None:
        """Load a user by id; `None` when the account no longer exists."""
        return await self.users.get(user_id)

    async def _issue_tokens(self, user_id: int) -> tuple[str, str]:
        """Mint an access token plus a new session row. Deliberately does not commit."""
        settings = get_settings()
        refresh_token = new_refresh_token()
        await self.sessions.add(
            user_id=user_id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=utcnow() + timedelta(days=settings.refresh_token_expire_days),
        )
        return create_access_token(user_id), refresh_token

    async def _live_session(self, refresh_token: str) -> UserSession:
        """Return the session behind a usable refresh token.

        Every rejection carries the same message: the client learns that the token is
        unusable, never whether it was unknown, expired, or already revoked.
        """
        session = await self.sessions.get_by_token_hash(hash_refresh_token(refresh_token))
        if session is None:
            raise InvalidSessionError("Invalid refresh token")
        if session.revoked_at is not None:
            raise InvalidSessionError("Invalid refresh token")
        if ensure_utc(session.expires_at) <= utcnow():
            raise InvalidSessionError("Invalid refresh token")
        return session
