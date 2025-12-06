"""Public gallery endpoints (temporary share, static link)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse

from ..slots.slots_repository import SlotRepository
from ..repositories.job_history_repository import JobHistoryRepository, JobHistoryRecord
from ..settings.settings_service import SettingsService
from .public_gallery_service import GalleryCache, GalleryRateLimiter, GalleryShareState, utcnow


def build_public_gallery_router(
    *,
    share_state: GalleryShareState,
    rate_limiter: GalleryRateLimiter,
    cache: GalleryCache,
    slot_repo: SlotRepository,
    job_repo: JobHistoryRepository,
    settings_service: SettingsService,
    gallery_page_path: str,
) -> APIRouter:
    router = APIRouter(tags=["public-gallery"])

    @router.get("/pubgallery", include_in_schema=False)
    def serve_gallery_page() -> FileResponse:
        return FileResponse(gallery_page_path)

    @router.get("/pub/gallery")
    def fetch_public_gallery(request: Request) -> dict[str, Any]:
        if not share_state.is_enabled():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"status": "forbidden", "reason": "gallery_not_shared"},
            )
        client_ip = (request.client.host if request.client else "unknown") or "unknown"
        rate_limiter.check(client_ip)
        cached = cache.get()
        if cached is not None:
            return cached
        payload = _build_gallery_payload(slot_repo, job_repo, settings_service)
        cache.set(payload)
        return payload

    return router


def _build_gallery_payload(
    slot_repo: SlotRepository,
    job_repo: JobHistoryRepository,
    settings_service: SettingsService,
) -> dict[str, Any]:
    slots = slot_repo.list_slots()
    runtime = settings_service.snapshot()
    items: list[dict[str, Any]] = []
    for slot in slots:
        items.append(
            {
                "slot_id": slot.id,
                "display_name": slot.display_name,
                "provider": slot.provider,
                "operation": slot.operation,
                "is_active": slot.is_active,
                "latest_result": _build_latest(job_repo, slot.id),
                "recent_results": _build_recent(job_repo, slot.id),
            }
        )
    return {
        "status": "ok",
        "generated_at": utcnow().isoformat(),
        "slots": items,
        "sync_response_seconds": runtime["sync_response_seconds"],
        "result_ttl_hours": runtime["result_ttl_hours"],
    }


def _build_recent(job_repo: JobHistoryRepository, slot_id: str, limit: int = 10) -> list[dict[str, Any]]:
    records = job_repo.list_recent_by_slot(slot_id, limit=limit)
    return [_record_to_result(rec) for rec in records if rec.completed_at or rec.started_at]


def _build_latest(job_repo: JobHistoryRepository, slot_id: str) -> dict[str, Any] | None:
    records = job_repo.list_recent_by_slot(slot_id, limit=1)
    if not records:
        return None
    rec = records[0]
    if not (rec.completed_at or rec.started_at):
        return None
    return _record_to_result(rec)


def _record_to_result(record: JobHistoryRecord) -> dict[str, Any]:
    finished_at: datetime | None = record.completed_at or record.started_at
    public_url = f"/public/results/{record.job_id}"
    mime = None
    if record.result_path:
        path = record.result_path.lower()
        if path.endswith(".png"):
            mime = "image/png"
        elif path.endswith(".jpg") or path.endswith(".jpeg"):
            mime = "image/jpeg"
        elif path.endswith(".webp"):
            mime = "image/webp"
    return {
        "job_id": record.job_id,
        "status": record.status,
        "finished_at": finished_at,
        "public_url": public_url,
        "download_url": public_url,
        "thumbnail_url": public_url,
        "result_expires_at": record.result_expires_at,
        "expires_at": record.result_expires_at,
        "mime": mime,
    }
