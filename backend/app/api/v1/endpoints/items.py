"""Item endpoints. HTTP concerns only — logic lives in `ItemService`."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import ItemServiceDep, PaginationDep
from app.schemas.common import Page
from app.schemas.item import ItemCreate, ItemRead, ItemUpdate
from app.services.item import ItemConflictError, ItemNotFoundError

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=Page[ItemRead], summary="List items")
async def list_items(service: ItemServiceDep, pagination: PaginationDep) -> Page[ItemRead]:
    items, total = await service.list_items(skip=pagination.skip, limit=pagination.limit)
    return Page[ItemRead](
        items=[ItemRead.model_validate(item) for item in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.skip,
    )


@router.post(
    "",
    response_model=ItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an item",
    responses={status.HTTP_409_CONFLICT: {"description": "Name already taken"}},
)
async def create_item(payload: ItemCreate, service: ItemServiceDep) -> ItemRead:
    try:
        item = await service.create_item(payload)
    except ItemConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ItemRead.model_validate(item)


@router.get(
    "/{item_id}",
    response_model=ItemRead,
    summary="Get an item",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Item not found"}},
)
async def get_item(item_id: int, service: ItemServiceDep) -> ItemRead:
    try:
        item = await service.get_item(item_id)
    except ItemNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ItemRead.model_validate(item)


@router.patch(
    "/{item_id}",
    response_model=ItemRead,
    summary="Partially update an item",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Item not found"},
        status.HTTP_409_CONFLICT: {"description": "Name already taken"},
    },
)
async def update_item(item_id: int, payload: ItemUpdate, service: ItemServiceDep) -> ItemRead:
    try:
        item = await service.update_item(item_id, payload)
    except ItemNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ItemConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ItemRead.model_validate(item)


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an item",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Item not found"}},
)
async def delete_item(item_id: int, service: ItemServiceDep) -> None:
    try:
        await service.delete_item(item_id)
    except ItemNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
