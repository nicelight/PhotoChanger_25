"""Public endpoints serving finalized result artefacts with strict TTLs."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import format_datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, status
from fastapi.responses import JSONResponse, RedirectResponse, Response

from ...services import JobService, MediaService
from .ingest import get_job_service, get_media_service
from .responses import endpoint_not_implemented

router = APIRouter(prefix="/public", tags=["Public"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_datetime(dt: datetime) -> str:
    return (
        dt.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _result_not_found(job_id: UUID) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": {
                "code": "result_not_found",
                "message": "Result artefact is not available for the requested job.",
                "details": {"job_id": str(job_id)},
            }
        },
    )


def _result_expired(job_id: UUID, *, expires_at: datetime) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_410_GONE,
        content={
            "error": {
                "code": "result_expired",
                "message": "Result link TTL elapsed.",
                "details": {
                    "job_id": str(job_id),
                    "result_expires_at": _serialize_datetime(expires_at),
                },
            }
        },
    )


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
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
)
async def download_public_result(
    job_service: Annotated[JobService, Depends(get_job_service)],
    media_service: Annotated[MediaService, Depends(get_media_service)],
    job_id: UUID = Path(..., description="Идентификатор Job с успешным результатом."),
) -> Response:
    """Issue a temporary redirect to the finalized job artefact.

    The redirect is only valid until ``job.result_expires_at``. Once the TTL
    elapses the endpoint responds with ``410 Gone`` as mandated by ADR-0002.
    """

    job = job_service.get_job(job_id)
    if job is None:
        return _result_not_found(job_id)

    if not job.is_finalized or job.failure_reason is not None:
        return _result_not_found(job_id)

    if not job.result_file_path:
        return _result_not_found(job_id)

    expires_at = job.result_expires_at
    if expires_at is None:
        return _result_not_found(job_id)

    now = _utcnow()
    if expires_at <= now:
        return _result_expired(job_id, expires_at=expires_at)

    media = media_service.get_media_by_path(job.result_file_path)
    if media is not None:
        location = media.public_url
    else:
        location = f"/media/{job.result_file_path}"

    response = RedirectResponse(
        url=location,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
    ttl_seconds = max(0, int((expires_at - now).total_seconds()))
    response.headers["Cache-Control"] = f"private, max-age={ttl_seconds}"
    response.headers["Expires"] = format_datetime(expires_at, usegmt=True)
    response.headers["PhotoChanger-Result-Expires-At"] = _serialize_datetime(
        expires_at
    )
    return response


__all__ = ["router", "get_public_media", "download_public_result"]
