"""Request/response schemas for the auth flow."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.core.config import get_settings

SECONDS_PER_DAY = 24 * 60 * 60


class LoginRequest(BaseModel):
    """Payload for `POST /auth/login`."""

    email: EmailStr
    # Deliberately not min_length=8: a too-short password must fail as 401, not 422, so
    # login never leaks the registration policy.
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    """Payload for `POST /auth/refresh`."""

    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    """Payload for `POST /auth/logout`."""

    refresh_token: str = Field(min_length=1)


class TokenPair(BaseModel):
    """What a successful login or refresh returns, inside `UnifiedResponse.data`."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access-token lifetime in seconds")
    refresh_expires_in: int = Field(description="Refresh-session lifetime in seconds")

    @classmethod
    def from_tokens(cls, access_token: str, refresh_token: str) -> TokenPair:
        """Report the configured lifetimes, so no route does that arithmetic itself."""
        settings = get_settings()
        return cls(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
            refresh_expires_in=settings.refresh_token_expire_days * SECONDS_PER_DAY,
        )
