"""Request/response schemas for `User`."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

BCRYPT_MAX_BYTES = 72


class UserCreate(BaseModel):
    """Payload for `POST /auth/register`."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def _strip_surrounding_whitespace(cls, value: object) -> object:
        """`EmailStr` rejects padded input, and people paste padded input."""
        return value.strip() if isinstance(value, str) else value

    @field_validator("password")
    @classmethod
    def _reject_passwords_bcrypt_would_truncate(cls, value: str) -> str:
        """bcrypt ignores everything past 72 bytes, so a longer password is rejected, never cut."""
        if len(value.encode("utf-8")) > BCRYPT_MAX_BYTES:
            raise ValueError(f"password must be at most {BCRYPT_MAX_BYTES} bytes")
        return value


class UserRead(BaseModel):
    """A user as returned by the API. The password hash is never serialised."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    created_at: datetime
    updated_at: datetime
