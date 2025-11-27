"""Admin API for uploading template media files."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)

from ..auth.auth_dependencies import require_admin_user
from ..config import AppConfig
from ..repositories.job_history_repository import JobHistoryRepository
from ..repositories.media_object_repository import MediaObjectRepository
from ..slots.slots_repository import SlotRepository

router = APIRouter(
    prefix="/api/template-media",
    tags=["template-media"],
    dependencies=[Depends(require_admin_user)],
)


def _get_slot_repo(request: Request) -> SlotRepository:
    try:
        return request.app.state.slot_repo  # type: ignore[attr-defined]
    except AttributeError as exc:  # pragma: no cover - defensive
        raise RuntimeError("SlotRepository is not configured") from exc


def _get_media_repo(request: Request) -> MediaObjectRepository:
    try:
        return request.app.state.media_repo  # type: ignore[attr-defined]
    except AttributeError as exc:  # pragma: no cover - defensive
        raise RuntimeError("MediaObjectRepository is not configured") from exc


def _get_job_repo(request: Request) -> JobHistoryRepository:
    try:
        return request.app.state.job_repo  # type: ignore[attr-defined]
    except AttributeError as exc:  # pragma: no cover - defensive
        raise RuntimeError("JobHistoryRepository is not configured") from exc


def _get_config(request: Request) -> AppConfig:
    try:
        return request.app.state.config  # type: ignore[attr-defined]
    except AttributeError as exc:  # pragma: no cover - defensive
        raise RuntimeError("AppConfig is not configured") from exc


@router.post("/register")
async def register_template_media(
    slot_id: str = Form(...),
    media_kind: str = Form(...),
    file: UploadFile = File(...),
    slot_repo: SlotRepository = Depends(_get_slot_repo),
    media_repo: MediaObjectRepository = Depends(_get_media_repo),
    job_repo: JobHistoryRepository = Depends(_get_job_repo),
    config: AppConfig = Depends(_get_config),
) -> dict[str, str]:
    """Upload a template media file and return its media_object_id."""
    # validate slot exists
    try:
        slot_repo.get_slot(slot_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "failure_reason": "slot_not_found"},
        ) from None

    content_type = file.content_type or ""
    if content_type not in config.ingest_limits.allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={"status": "error", "failure_reason": "unsupported_media_type"},
        )

    # persist file to templates folder
    slot_dir = config.media_paths.templates / slot_id
    slot_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "template").suffix or ".bin"
    media_filename = f"{uuid.uuid4().hex}{suffix}"
    media_path = slot_dir / media_filename
    with media_path.open("wb") as output:
        output.write(await file.read())

    now = datetime.utcnow()
    # record a pseudo job to satisfy media_object FK
    job_id = f"template-{uuid.uuid4().hex}"
    job_repo.create_template_upload(
        job_id=job_id,
        slot_id=slot_id,
        path=str(media_path),
        completed_at=now,
    )
    expires_at = now + timedelta(days=3650)
    media_object_id = media_repo.register_template(
        job_id=job_id,
        slot_id=slot_id,
        path=media_path,
        expires_at=expires_at,
    )

    return {"media_object_id": media_object_id, "media_kind": media_kind}
