"""Slot management router stubs mirroring administrative operations."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, Path, Query, status
from fastapi.responses import JSONResponse

from ..schemas import Slot, SlotIdentifier, SlotListResponse, SlotUpdateRequest, SlotUpdateResponse
from .dependencies import require_bearer_authentication
from .responses import authentication_not_configured, endpoint_not_implemented

router = APIRouter(prefix="/api", tags=["Slots"])


@router.get(
    "/slots",
    response_model=SlotListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_slots(
    authenticated: Annotated[bool, Depends(require_bearer_authentication)],
    provider_id: Annotated[Optional[str], Query(description="Фильтр по провайдеру")] = None,
    operation_id: Annotated[Optional[str], Query(description="Фильтр по операции провайдера")] = None,
    search: Annotated[Optional[str], Query(description="Поиск по имени слота")] = None,
) -> JSONResponse:
    """Получить список статических ingest-слотов."""

    if not authenticated:
        return authentication_not_configured()
    return endpoint_not_implemented("listSlots")


@router.get(
    "/slots/{slot_id}",
    response_model=Slot,
    status_code=status.HTTP_200_OK,
)
async def get_slot(
    authenticated: Annotated[bool, Depends(require_bearer_authentication)],
    slot_id: Annotated[SlotIdentifier, Path(description="Идентификатор статического ingest-слота")],
) -> JSONResponse:
    """Получить данные конкретного слота вместе с последними результатами."""

    if not authenticated:
        return authentication_not_configured()
    return endpoint_not_implemented("getSlot")


@router.put(
    "/slots/{slot_id}",
    response_model=SlotUpdateResponse,
    status_code=status.HTTP_200_OK,
)
async def update_slot(
    authenticated: Annotated[bool, Depends(require_bearer_authentication)],
    slot_id: Annotated[SlotIdentifier, Path(description="Идентификатор статического ingest-слота")],
    payload: SlotUpdateRequest,
    if_match: Annotated[
        Optional[str],
        Header(alias="If-Match", description="Текущая версия слота в формате ETag."),
    ] = None,
) -> JSONResponse:
    """Обновить настройки слота с учётом проверки версии."""

    _ = (slot_id, payload, if_match)
    if not authenticated:
        return authentication_not_configured()
    return endpoint_not_implemented("updateSlot")


@router.post(
    "/slots/{slot_id}/reset_stats",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def reset_slot_stats(
    authenticated: Annotated[bool, Depends(require_bearer_authentication)],
    slot_id: Annotated[SlotIdentifier, Path(description="Идентификатор статического ingest-слота")],
) -> JSONResponse:
    """Сбросить статистику указанного слота."""

    _ = slot_id
    if not authenticated:
        return authentication_not_configured()
    return endpoint_not_implemented("resetSlotStats")


__all__ = ["router", "list_slots", "get_slot", "update_slot", "reset_slot_stats"]
