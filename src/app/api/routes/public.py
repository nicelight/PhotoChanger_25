"""Public download router stubs for temporary results and media.

Placeholder endpoints align with the public section of
``spec/contracts/openapi.yaml`` while real media streaming is deferred.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Path, status
from fastapi.responses import JSONResponse

from .responses import endpoint_not_implemented

router = APIRouter(prefix="/public", tags=["Public"])


@router.get(
    "/media/{media_id}",
    status_code=status.HTTP_200_OK,
)
async def get_public_media(
    media_id: UUID = Path(..., description="Идентификатор media_object"),
) -> JSONResponse:
    """Получить временный файл по публичной ссылке."""

    _ = media_id
    return endpoint_not_implemented("getPublicMedia")


@router.get(
    "/results/{job_id}",
    status_code=status.HTTP_200_OK,
)
async def download_public_result(
    job_id: UUID = Path(..., description="Идентификатор Job с успешным результатом."),
) -> JSONResponse:
    """Скачать итоговый файл обработки."""

    _ = job_id
    return endpoint_not_implemented("downloadPublicResult")


__all__ = ["router", "get_public_media", "download_public_result"]
