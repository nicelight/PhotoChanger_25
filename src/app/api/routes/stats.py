"""Statistics router stubs exposing monitoring endpoints.

These placeholders reflect the analytics endpoints described in
``spec/contracts/openapi.yaml`` for slot-scoped and global aggregates.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.responses import JSONResponse

from ..schemas import GlobalStatsResponse, SlotIdentifier, SlotStatsResponse
from .dependencies import (
    AdminPrincipal,
    ensure_permissions,
    require_bearer_authentication,
)
from .responses import endpoint_not_implemented

router = APIRouter(prefix="/api", tags=["Stats"])


@router.get(
    "/stats/{slot_id}",
    response_model=SlotStatsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_slot_stats(
    principal: Annotated[AdminPrincipal, Depends(require_bearer_authentication)],
    slot_id: Annotated[SlotIdentifier, Path(description="Идентификатор слота")],
    from_dt: Annotated[
        Optional[datetime],
        Query(
            alias="from",
            description="Начало диапазона (UTC). Максимальная длительность — 31 день.",
        ),
    ] = None,
    to_dt: Annotated[
        Optional[datetime],
        Query(alias="to", description="Конец диапазона (UTC)"),
    ] = None,
    group_by: Annotated[
        Literal["hour", "day", "week"],
        Query(description="Гранулярность агрегации"),
    ] = "day",
) -> JSONResponse:
    """Получить статистику по слоту."""

    _ = (slot_id, from_dt, to_dt, group_by)
    ensure_permissions(principal, "stats:read")
    return endpoint_not_implemented("getSlotStats")


@router.get(
    "/stats/global",
    response_model=GlobalStatsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_global_stats(
    principal: Annotated[AdminPrincipal, Depends(require_bearer_authentication)],
    from_dt: Annotated[
        Optional[datetime],
        Query(alias="from", description="Начало диапазона (UTC). Максимум 90 дней."),
    ] = None,
    to_dt: Annotated[
        Optional[datetime],
        Query(alias="to", description="Конец диапазона (UTC)"),
    ] = None,
    group_by: Annotated[
        Literal["day", "week", "month"],
        Query(description="Гранулярность агрегирования"),
    ] = "week",
    page: Annotated[
        int, Query(ge=1, description="Номер страницы постраничного просмотра.")
    ] = 1,
    page_size: Annotated[
        int,
        Query(ge=1, le=50, description="Количество агрегатов на страницу."),
    ] = 10,
    sort_by: Annotated[
        Literal["period_start", "success", "errors", "ingest_count"],
        Query(description="Поле сортировки агрегированной статистики."),
    ] = "period_start",
    sort_order: Annotated[
        Literal["asc", "desc"],
        Query(description="Направление сортировки агрегатов."),
    ] = "desc",
    provider_id: Annotated[
        Optional[str], Query(description="Фильтр по провайдеру")
    ] = None,
    slot_id: Annotated[
        Optional[SlotIdentifier], Query(description="Фильтр по конкретному слоту")
    ] = None,
) -> JSONResponse:
    """Получить агрегированную статистику по слотам."""

    _ = (
        from_dt,
        to_dt,
        group_by,
        page,
        page_size,
        sort_by,
        sort_order,
        provider_id,
        slot_id,
    )
    ensure_permissions(principal, "stats:read")
    return endpoint_not_implemented("getGlobalStats")


__all__ = ["router", "get_slot_stats", "get_global_stats"]
