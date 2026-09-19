"""Health/metadata endpoint tests."""

from __future__ import annotations

from httpx import AsyncClient


async def test_root_returns_service_metadata(client: AsyncClient) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert set(response.json()) == {"app", "env", "docs", "api"}


async def test_unversioned_health_is_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_versioned_health_reports_app_and_env(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "app" in body and "env" in body


async def test_database_readiness_check(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "reachable"}


async def test_openapi_schema_is_served(client: AsyncClient) -> None:
    response = await client.get("/api/v1/openapi.json")

    assert response.status_code == 200
    assert "/api/v1/items" in response.json()["paths"]


async def test_unknown_path_returns_an_enveloped_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"status_code", "message", "data"}
    assert body["status_code"] == 404
    assert body["data"] is None
