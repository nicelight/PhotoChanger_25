"""Helpers for serving public result files."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from fastapi import status
from fastapi.responses import FileResponse, JSONResponse

from ..repositories.job_history_repository import JobHistoryRepository


def _guess_mime(suffix: str) -> str:
    lowered = suffix.lower()
    if lowered in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if lowered == ".png":
        return "image/png"
    if lowered == ".webp":
        return "image/webp"
    return "application/octet-stream"


@dataclass(slots=True)
class PublicResultService:
    """Expose processed results for public download."""

    job_repo: JobHistoryRepository
    log: logging.Logger = field(default_factory=lambda: logging.getLogger(__name__))

    def open_result(self, job_id: str) -> FileResponse | JSONResponse:
        """Return the processed result file or error payload."""
        try:
            job = self.job_repo.get_job(job_id)
        except KeyError:
            self.log.debug("public.result.not_found", extra={"job_id": job_id})
            return self._error(status.HTTP_404_NOT_FOUND, "result_not_found")

        if job.status != "done" or not job.result_path:
            self.log.debug(
                "public.result.not_completed",
                extra={
                    "job_id": job.job_id,
                    "slot_id": job.slot_id,
                    "status": job.status,
                },
            )
            return self._error(status.HTTP_404_NOT_FOUND, "result_not_found")

        if job.result_expires_at and job.result_expires_at <= datetime.utcnow():
            self.log.info(
                "public.result.expired",
                extra={
                    "job_id": job.job_id,
                    "slot_id": job.slot_id,
                    "result_expires_at": job.result_expires_at.isoformat(),
                },
            )
            return self._error(status.HTTP_410_GONE, "result_expired")

        result_path = Path(job.result_path)
        if not result_path.exists():
            # файл отсутствует (вероятно, cron уже очистил) — считаем ссылку истёкшей
            self.log.warning(
                "public.result.missing_file",
                extra={
                    "job_id": job.job_id,
                    "slot_id": job.slot_id,
                    "path": job.result_path,
                },
            )
            return self._error(status.HTTP_410_GONE, "result_expired")

        return FileResponse(
            path=result_path,
            media_type=_guess_mime(result_path.suffix),
            filename=result_path.name,
            headers={"Content-Disposition": f'inline; filename="{result_path.name}"'},
        )

    @staticmethod
    def _error(status_code: int, failure_reason: str) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "error",
                "failure_reason": failure_reason,
            },
        )
