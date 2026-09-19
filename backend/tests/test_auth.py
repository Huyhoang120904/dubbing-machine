"""End-to-end tests for the auth endpoints, including the response envelope."""

from __future__ import annotations

from datetime import timedelta

import jwt
from app.core.config import Settings
from app.core.security import ALGORITHM, create_access_token, utcnow
from httpx import AsyncClient

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
LOGOUT_URL = "/api/v1/auth/logout"
ME_URL = "/api/v1/auth/me"
PASSWORD = "supersecret"
ENVELOPE_KEYS = {"status_code", "message", "data"}


async def _register(client: AsyncClient, email: str = "user@example.com", password: str = PASSWORD):
    return await client.post(REGISTER_URL, json={"email": email, "password": password})


async def _login(client: AsyncClient, email: str = "user@example.com", password: str = PASSWORD):
    return await client.post(LOGIN_URL, json={"email": email, "password": password})


async def _token_pair(client: AsyncClient, email: str = "user@example.com") -> dict[str, str]:
    await _register(client, email)
    response = await _login(client, email)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _bearer(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def test_register_returns_201_with_an_envelope_and_no_hash(client: AsyncClient) -> None:
    response = await _register(client, "  User@Example.COM ")

    assert response.status_code == 201
    body = response.json()
    assert set(body) == ENVELOPE_KEYS
    assert body["status_code"] == 201
    assert body["message"] == "User registered"
    assert body["data"]["email"] == "user@example.com"
    assert "hashed_password" not in body["data"]
    assert set(body["data"]) == {"id", "email", "created_at", "updated_at"}


async def test_register_rejects_a_duplicate_email(client: AsyncClient) -> None:
    await _register(client)

    response = await _register(client, "USER@example.com")

    assert response.status_code == 409
    body = response.json()
    assert set(body) == ENVELOPE_KEYS
    assert body["status_code"] == 409
    assert body["data"] is None
    assert "already exists" in body["message"]


async def test_register_validates_email_and_password_length(client: AsyncClient) -> None:
    invalid_email = await _register(client, "not-an-email")
    short_password = await _register(client, "user@example.com", "short")
    long_password = await _register(client, "user@example.com", "x" * 73)

    assert invalid_email.status_code == 422
    assert short_password.status_code == 422
    assert long_password.status_code == 422
    assert invalid_email.json()["status_code"] == 422
    assert invalid_email.json()["message"] == "Validation error"
    assert isinstance(invalid_email.json()["data"], list)  # the pydantic error list


async def test_login_returns_a_token_pair_in_the_envelope(client: AsyncClient) -> None:
    await _register(client)

    response = await _login(client)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == ENVELOPE_KEYS
    assert body["status_code"] == 200
    assert body["message"] == "Login successful"
    assert set(body["data"]) == {
        "access_token",
        "refresh_token",
        "token_type",
        "expires_in",
        "refresh_expires_in",
    }
    assert body["data"]["token_type"] == "bearer"
    assert body["data"]["expires_in"] == 15 * 60
    assert body["data"]["refresh_expires_in"] == 30 * 24 * 60 * 60


async def test_login_rejects_a_wrong_password_and_an_unknown_email_identically(
    client: AsyncClient,
) -> None:
    await _register(client)

    wrong_password = await _login(client, password="wrong-password")
    unknown_email = await _login(client, "nobody@example.com")

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.json()["message"] == unknown_email.json()["message"]
    assert wrong_password.json()["data"] is None


async def test_me_returns_the_authenticated_user(client: AsyncClient) -> None:
    tokens = await _token_pair(client)

    response = await client.get(ME_URL, headers=_bearer(tokens["access_token"]))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == ENVELOPE_KEYS
    assert body["data"]["email"] == "user@example.com"
    assert "hashed_password" not in body["data"]


async def test_me_rejects_every_kind_of_bad_token(client: AsyncClient) -> None:
    tokens = await _token_pair(client)
    settings = Settings(_env_file=None)
    wrong_typ = jwt.encode(
        {
            "sub": "1",
            "typ": "refresh",
            "exp": int((utcnow() + timedelta(minutes=5)).timestamp()),
        },
        settings.jwt_secret_key,
        algorithm=ALGORITHM,
    )

    missing_header = await client.get(ME_URL)
    garbage = await client.get(ME_URL, headers=_bearer("not-a-jwt"))
    expired = await client.get(
        ME_URL, headers=_bearer(create_access_token(1, expires_delta=timedelta(minutes=-1)))
    )
    refresh_as_bearer = await client.get(ME_URL, headers=_bearer(tokens["refresh_token"]))
    wrong_type_claim = await client.get(ME_URL, headers=_bearer(wrong_typ))

    for response in (
        missing_header,
        garbage,
        expired,
        refresh_as_bearer,
        wrong_type_claim,
    ):
        assert response.status_code == 401, response.text
        assert set(response.json()) == ENVELOPE_KEYS
        assert response.json()["data"] is None


async def test_refresh_rotates_and_invalidates_the_presented_token(client: AsyncClient) -> None:
    tokens = await _token_pair(client)

    rotated = await client.post(REFRESH_URL, json={"refresh_token": tokens["refresh_token"]})
    replayed = await client.post(REFRESH_URL, json={"refresh_token": tokens["refresh_token"]})

    assert rotated.status_code == 200
    assert rotated.json()["message"] == "Token refreshed"
    assert rotated.json()["data"]["refresh_token"] != tokens["refresh_token"]
    assert replayed.status_code == 401

    still_valid = await client.get(ME_URL, headers=_bearer(rotated.json()["data"]["access_token"]))
    assert still_valid.status_code == 200


async def test_logout_revokes_the_session_and_returns_an_empty_envelope(
    client: AsyncClient,
) -> None:
    tokens = await _token_pair(client)

    response = await client.post(
        LOGOUT_URL,
        json={"refresh_token": tokens["refresh_token"]},
        headers=_bearer(tokens["access_token"]),
    )
    afterwards = await client.post(REFRESH_URL, json={"refresh_token": tokens["refresh_token"]})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == ENVELOPE_KEYS
    assert body["message"] == "Logged out"
    assert body["data"] is None
    assert afterwards.status_code == 401
