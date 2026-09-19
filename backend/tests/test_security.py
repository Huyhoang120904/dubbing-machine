"""Unit tests for the token primitives."""

from __future__ import annotations

from datetime import timedelta

import jwt
from app.core.security import (
    ALGORITHM,
    create_access_token,
    decode_access_token,
    hash_password,
    utcnow,
    verify_password,
)


def test_hash_password_produces_a_verifiable_bcrypt_hash() -> None:
    hashed = hash_password("supersecret")

    assert hashed.startswith("$2b$")
    assert "supersecret" not in hashed
    assert verify_password("supersecret", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_expired_access_token_is_rejected() -> None:
    expired = create_access_token(42, expires_delta=timedelta(minutes=-1))

    assert decode_access_token(expired) is None


def test_token_signed_with_another_secret_is_rejected() -> None:
    forged = jwt.encode(
        {
            "sub": "42",
            "typ": "access",
            "exp": int((utcnow() + timedelta(minutes=5)).timestamp()),
        },
        "not-the-configured-secret",
        algorithm=ALGORITHM,
    )

    assert decode_access_token(forged) is None
