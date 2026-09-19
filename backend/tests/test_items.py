"""End-to-end tests for the `Item` CRUD endpoints."""

from __future__ import annotations

from httpx import AsyncClient

ITEMS_URL = "/api/v1/items"


async def _create_item(client: AsyncClient, name: str = "Widget", description: str | None = None):
    payload: dict[str, object] = {"name": name}
    if description is not None:
        payload["description"] = description
    return await client.post(ITEMS_URL, json=payload)


async def test_create_item_returns_201_and_persisted_fields(client: AsyncClient) -> None:
    response = await _create_item(client, "Widget", "A shiny widget")

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Widget"
    assert body["description"] == "A shiny widget"
    assert isinstance(body["id"], int)
    assert body["created_at"] and body["updated_at"]


async def test_create_item_rejects_duplicate_name_with_409(client: AsyncClient) -> None:
    assert (await _create_item(client, "Widget")).status_code == 201

    duplicate = await _create_item(client, "Widget")

    assert duplicate.status_code == 409
    assert "already exists" in duplicate.json()["detail"]


async def test_create_item_validates_empty_name(client: AsyncClient) -> None:
    response = await _create_item(client, "")

    assert response.status_code == 422


async def test_get_item_by_id(client: AsyncClient) -> None:
    item_id = (await _create_item(client, "Widget")).json()["id"]

    response = await client.get(f"{ITEMS_URL}/{item_id}")

    assert response.status_code == 200
    assert response.json()["id"] == item_id


async def test_get_missing_item_returns_404(client: AsyncClient) -> None:
    response = await client.get(f"{ITEMS_URL}/424242")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


async def test_list_items_paginates_and_reports_total(client: AsyncClient) -> None:
    for index in range(5):
        assert (await _create_item(client, f"Widget {index}")).status_code == 201

    response = await client.get(ITEMS_URL, params={"skip": 1, "limit": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert body["limit"] == 2
    assert body["offset"] == 1
    assert [item["name"] for item in body["items"]] == ["Widget 1", "Widget 2"]


async def test_list_items_rejects_out_of_range_limit(client: AsyncClient) -> None:
    response = await client.get(ITEMS_URL, params={"limit": 1000})

    assert response.status_code == 422


async def test_patch_item_updates_only_provided_fields(client: AsyncClient) -> None:
    created = (await _create_item(client, "Widget", "original")).json()

    response = await client.patch(f"{ITEMS_URL}/{created['id']}", json={"description": "updated"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Widget"
    assert body["description"] == "updated"


async def test_patch_missing_item_returns_404(client: AsyncClient) -> None:
    response = await client.patch(f"{ITEMS_URL}/424242", json={"name": "Nope"})

    assert response.status_code == 404


async def test_patch_to_duplicate_name_returns_409(client: AsyncClient) -> None:
    await _create_item(client, "Widget")
    other_id = (await _create_item(client, "Gadget")).json()["id"]

    response = await client.patch(f"{ITEMS_URL}/{other_id}", json={"name": "Widget"})

    assert response.status_code == 409


async def test_delete_item_removes_it(client: AsyncClient) -> None:
    item_id = (await _create_item(client, "Widget")).json()["id"]

    deleted = await client.delete(f"{ITEMS_URL}/{item_id}")
    fetched = await client.get(f"{ITEMS_URL}/{item_id}")

    assert deleted.status_code == 204
    assert deleted.content == b""
    assert fetched.status_code == 404


async def test_delete_missing_item_returns_404(client: AsyncClient) -> None:
    response = await client.delete(f"{ITEMS_URL}/424242")

    assert response.status_code == 404
