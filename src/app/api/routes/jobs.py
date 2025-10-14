"""Jobs monitoring router stubs."""

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.responses import JSONResponse

from ..schemas import JobDetailResponse, JobListResponse, SlotIdentifier
from .dependencies import require_bearer_authentication
from .responses import authentication_not_configured, endpoint_not_implemented

router = APIRouter(prefix="/api", tags=["Jobs"])


@router.get(
    "/jobs",
    response_model=JobListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_jobs(
    authenticated: Annotated[bool, Depends(require_bearer_authentication)],
    status_filter: Annotated[
        Optional[str],
        Query(
            alias="status",
            description="Фильтр по текущему промежуточному статусу задачи.",
        ),
    ] = None,
    is_finalized: Annotated[
        Optional[bool],
        Query(description="Ограничить выборку финализированными или активными задачами."),
    ] = None,
    failure_reason: Annotated[
        Optional[str],
        Query(description="Показать только задачи с указанной причиной неуспеха."),
    ] = None,
    slot_id: Annotated[
        Optional[SlotIdentifier],
        Query(description="Фильтр по идентификатору слота (`slot-001` … `slot-015`)."),
    ] = None,
    page: Annotated[int, Query(ge=1, description="Номер страницы постраничного просмотра.")] = 1,
    page_size: Annotated[
        int,
        Query(ge=1, le=100, description="Количество записей на страницу."),
    ] = 20,
    sort_by: Annotated[
        str,
        Query(description="Поле сортировки списка задач."),
    ] = "expires_at",
    sort_order: Annotated[
        str,
        Query(description="Направление сортировки."),
    ] = "asc",
) -> JSONResponse:
    """Получить список задач ingest-очереди."""

    _ = (
        status_filter,
        is_finalized,
        failure_reason,
        slot_id,
        page,
        page_size,
        sort_by,
        sort_order,
    )
    if not authenticated:
        return authentication_not_configured()
    return endpoint_not_implemented("listJobs")


@router.get(
    "/jobs/{job_id}",
    response_model=JobDetailResponse,
    status_code=status.HTTP_200_OK,
)
async def get_job(
    authenticated: Annotated[bool, Depends(require_bearer_authentication)],
    job_id: Annotated[UUID, Path(description="Идентификатор задачи")],
) -> JSONResponse:
    """Получить подробную информацию о задаче."""

    if not authenticated:
        return authentication_not_configured()
    return endpoint_not_implemented("getJob")


__all__ = ["router", "list_jobs", "get_job"]
