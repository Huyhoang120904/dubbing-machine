"""Auth routes. HTTP only: validate input, delegate to `AuthService`, translate its errors."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import AuthServiceDep, CurrentUserDep
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, TokenPair
from app.schemas.common import UnifiedResponse, unified
from app.schemas.user import UserCreate, UserRead
from app.services.auth import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidSessionError,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_UNAUTHORIZED: dict[int | str, dict[str, object]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": UnifiedResponse[None]}
}
_VALIDATION: dict[int | str, dict[str, object]] = {
    status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": UnifiedResponse[list]}
}


@router.post(
    "/register",
    response_model=UnifiedResponse[UserRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
    responses={status.HTTP_409_CONFLICT: {"model": UnifiedResponse[None]}, **_VALIDATION},
)
async def register(payload: UserCreate, service: AuthServiceDep) -> UnifiedResponse[UserRead]:
    """Create an account. Tokens come from `POST /auth/login`, not from here."""
    try:
        user = await service.register(payload)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return unified(
        UserRead.model_validate(user),
        status_code=status.HTTP_201_CREATED,
        message="User registered",
    )


@router.post(
    "/login",
    response_model=UnifiedResponse[TokenPair],
    summary="Exchange credentials for a token pair",
    responses=_UNAUTHORIZED,
)
async def login(payload: LoginRequest, service: AuthServiceDep) -> UnifiedResponse[TokenPair]:
    """Verify credentials and issue an access token plus a refresh session."""
    try:
        access_token, refresh_token = await service.login(payload)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return unified(
        TokenPair.from_tokens(access_token, refresh_token),
        message="Login successful",
    )


@router.post(
    "/refresh",
    response_model=UnifiedResponse[TokenPair],
    summary="Rotate a refresh token",
    responses=_UNAUTHORIZED,
)
async def refresh(payload: RefreshRequest, service: AuthServiceDep) -> UnifiedResponse[TokenPair]:
    """Revoke the presented refresh token and issue a fresh pair."""
    try:
        access_token, refresh_token = await service.refresh(payload.refresh_token)
    except InvalidSessionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return unified(
        TokenPair.from_tokens(access_token, refresh_token),
        message="Token refreshed",
    )


@router.post(
    "/logout",
    response_model=UnifiedResponse[None],
    summary="Revoke a refresh token",
    responses=_UNAUTHORIZED,
)
async def logout(
    payload: LogoutRequest,
    user: CurrentUserDep,
    service: AuthServiceDep,
) -> UnifiedResponse[None]:
    """Revoke one of the caller's own sessions. Answers 200 with `data: null`."""
    try:
        await service.logout(user, payload.refresh_token)
    except InvalidSessionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return unified(message="Logged out")


@router.get(
    "/me",
    response_model=UnifiedResponse[UserRead],
    summary="The authenticated user",
    responses=_UNAUTHORIZED,
)
async def me(user: CurrentUserDep) -> UnifiedResponse[UserRead]:
    """Return the account behind the bearer token."""
    return unified(UserRead.model_validate(user), message="OK")
