"""Password hashing and token primitives.

Pure functions: no database session, no FastAPI types. Everything the auth flow
needs to turn a password into a hash, or a user id into a token, lives here.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import bcrypt
import jwt

from app.core.config import get_settings

ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"
_REFRESH_TOKEN_BYTES = 32


def utcnow() -> datetime:
    """The single clock the auth flow uses."""
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """SQLite hands back naive datetimes even for `timezone=True` columns."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def hash_password(password: str) -> str:
    """A bcrypt hash with a fresh per-password salt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """False for a wrong password, and also for a malformed or over-long input."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        return False


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    """A throwaway hash, computed once, used to burn the same time as a real check."""
    return hash_password(secrets.token_urlsafe(16))


def verify_password_or_dummy(password: str, hashed_password: str | None) -> bool:
    """Always run a bcrypt check: an unknown email must not answer faster than a wrong password."""
    return verify_password(password, hashed_password or _dummy_hash())


def create_access_token(subject: int, *, expires_delta: timedelta | None = None) -> str:
    """Sign an access token for `subject` (the user id).

    `expires_delta` overrides the configured lifetime and exists for tests, e.g.
    `timedelta(minutes=-1)` mints an already-expired token.
    """
    settings = get_settings()
    issued_at = utcnow()
    expires_at = issued_at + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    return jwt.encode(
        {
            "sub": str(subject),
            "typ": ACCESS_TOKEN_TYPE,
            "iat": int(issued_at.timestamp()),
            "exp": int(expires_at.timestamp()),
            "jti": secrets.token_urlsafe(16),
        },
        settings.jwt_secret_key,
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> int | None:
    """Return the user id of a valid access token, or `None`.

    Every failure — bad signature, expired, malformed, wrong `typ` — collapses to `None`
    so no caller can branch on the difference and leak which one it was.
    """
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[ALGORITHM],  # pinned: never trust the token's own `alg` header
            options={"require": ["exp", "sub", "typ"]},
        )
    except jwt.PyJWTError:
        return None
    if claims.get("typ") != ACCESS_TOKEN_TYPE:
        return None
    try:
        return int(claims["sub"])
    except (TypeError, ValueError):
        return None


def new_refresh_token() -> str:
    """An opaque refresh token. Only its digest is ever stored."""
    return secrets.token_urlsafe(_REFRESH_TOKEN_BYTES)


def hash_refresh_token(token: str) -> str:
    """SHA-256 hex digest.

    Not bcrypt: the input is already high-entropy, so there is nothing to brute-force,
    and a refresh lookup must stay one indexed query.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
