"""Shared FastAPI dependencies (annotated types for clean endpoint signatures)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.models.user import User
from app.db.session import get_db
from app.repositories.session import UserSessionRepository
from app.repositories.user import UserRepository
from app.services.auth import AuthService

SessionDep = Annotated[AsyncSession, Depends(get_db)]

# auto_error=False so a missing or malformed header becomes our enveloped 401, not
# FastAPI's 403.
bearer_scheme = HTTPBearer(auto_error=False)

_INVALID_TOKEN = "Invalid or expired token"


def get_auth_service(db: SessionDep) -> AuthService:
    """Provide an `AuthService` bound to the request-scoped session and its repositories."""
    return AuthService(db, UserRepository(db), UserSessionRepository(db))


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


async def get_current_user(
    service: AuthServiceDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    """Resolve the bearer token to a live user, or raise 401.

    The signature check is stateless; the one primary-key lookup on top is what stops a
    deleted user from carrying on with a token that has not expired yet.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_TOKEN,
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await service.get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_TOKEN,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
