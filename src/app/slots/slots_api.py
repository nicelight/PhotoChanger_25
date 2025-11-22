"""Admin slot routes (test-run, CRUD)."""

from __future__ import annotations

import json
from typing import Any

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
from ..ingest.ingest_errors import (
    PayloadTooLargeError,
    ProviderExecutionError,
    ProviderTimeoutError,
    UnsupportedMediaError,
    UploadReadError,
)
from ..ingest.ingest_models import FailureReason
from ..ingest.ingest_service import IngestService
from ..repositories.job_history_repository import JobHistoryRepository
from ..repositories.media_object_repository import MediaObjectRepository
from ..settings.settings_service import SettingsService
from .slots_models import Slot
from .slots_repository import SlotRepository
from .slots_schemas import (
    SlotDetailsResponse,
    SlotRecentResultPayload,
    SlotSummaryResponse,
    SlotTemplateMediaPayload,
    SlotUpdateRequest,
)

router = APIRouter(
    prefix="/api/slots",
    tags=["slots"],
    dependencies=[Depends(require_admin_user)],
)


def get_ingest_service(request: Request) -> IngestService:
    """Fetch ingest service from application state."""
    try:
        return request.app.state.ingest_service  # type: ignore[attr-defined]
    except AttributeError as exc:  # pragma: no cover - defensive path
        raise RuntimeError("IngestService is not configured") from exc


def get_slot_repo(request: Request) -> SlotRepository:
    try:
        return request.app.state.slot_repo  # type: ignore[attr-defined]
    except AttributeError as exc:  # pragma: no cover - defensive path
        raise RuntimeError("SlotRepository is not configured") from exc


def get_job_repo(request: Request) -> JobHistoryRepository:
    try:
        return request.app.state.job_repo  # type: ignore[attr-defined]
    except AttributeError as exc:  # pragma: no cover - defensive path
        raise RuntimeError("JobHistoryRepository is not configured") from exc


def get_media_repo(request: Request) -> MediaObjectRepository:
    try:
        return request.app.state.media_repo  # type: ignore[attr-defined]
    except AttributeError as exc:  # pragma: no cover - defensive path
        raise RuntimeError("MediaObjectRepository is not configured") from exc


def get_settings_service(request: Request) -> SettingsService:
    try:
        return request.app.state.settings_service  # type: ignore[attr-defined]
    except AttributeError as exc:  # pragma: no cover - defensive path
        raise RuntimeError("SettingsService is not configured") from exc


@router.get("/")
def list_slots(
    slot_repo: SlotRepository = Depends(get_slot_repo),
) -> list[SlotSummaryResponse]:
    slots = slot_repo.list_slots()
    return [_slot_summary(slot) for slot in slots]


@router.get("/{slot_id}")
def fetch_slot(
    slot_id: str,
    slot_repo: SlotRepository = Depends(get_slot_repo),
    job_repo: JobHistoryRepository = Depends(get_job_repo),
    settings_service: SettingsService = Depends(get_settings_service),
) -> SlotDetailsResponse:
    try:
        slot = slot_repo.get_slot(slot_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "failure_reason": FailureReason.SLOT_NOT_FOUND.value,
            },
        ) from None
    return _slot_details(slot, job_repo, settings_service)


@router.put("/{slot_id}")
def update_slot(
    slot_id: str,
    payload: SlotUpdateRequest,
    slot_repo: SlotRepository = Depends(get_slot_repo),
    job_repo: JobHistoryRepository = Depends(get_job_repo),
    settings_service: SettingsService = Depends(get_settings_service),
) -> SlotDetailsResponse:
    try:
        updated = slot_repo.update_slot(
            slot_id,
            display_name=payload.display_name,
            provider=payload.provider,
            operation=payload.operation,
            is_active=payload.is_active,
            size_limit_mb=payload.size_limit_mb,
            settings=payload.settings,
            template_media=[
                {
                    "media_kind": binding.media_kind,
                    "media_object_id": binding.media_object_id,
                }
                for binding in payload.template_media
            ],
            updated_by="admin-ui",
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "failure_reason": FailureReason.SLOT_NOT_FOUND.value,
            },
        ) from None
    return _slot_details(updated, job_repo, settings_service)


def _apply_overrides(
    base_settings: dict[str, Any], overrides: dict[str, Any]
) -> dict[str, Any]:
    """Apply override values to base settings and return merged result."""
    merged = dict(base_settings)

    if "settings" in overrides and isinstance(overrides["settings"], dict):
        merged.update(overrides["settings"])

    # Apply top-level overrides (provider, operation, template_media)
    for key in ["provider", "operation", "template_media"]:
        if key in overrides:
            merged[key] = overrides[key]

    return merged


def _bad_request(details: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "status": "error",
            "failure_reason": FailureReason.INVALID_REQUEST.value,
            "details": details,
        },
    )


def _sanitize_template_media(value: Any) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise _bad_request("template_media must be an array of objects")

    prepared: list[dict[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise _bad_request(f"template_media[{index}] must be an object")
        media_kind = item.get("media_kind")
        media_object_id = item.get("media_object_id")
        if not media_kind or not media_object_id:
            raise _bad_request(
                "media_kind and media_object_id are required for template_media items"
            )
        prepared.append(
            {"media_kind": str(media_kind), "media_object_id": str(media_object_id)}
        )
    return prepared


def _parse_slot_payload(raw_value: str | None) -> dict[str, Any]:
    if raw_value is None or raw_value == "":
        return {}
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise _bad_request("slot_payload must be a JSON object") from exc

    if not isinstance(payload, dict):
        raise _bad_request("slot_payload must be a JSON object")

    overrides: dict[str, Any] = {}
    provider = payload.get("provider")
    if provider is not None:
        if not isinstance(provider, str) or not provider:
            raise _bad_request("provider override must be a non-empty string")
        overrides["provider"] = provider

    operation = payload.get("operation")
    if operation is not None:
        if not isinstance(operation, str) or not operation:
            raise _bad_request("operation override must be a non-empty string")
        overrides["operation"] = operation

    settings = payload.get("settings")
    if settings is not None:
        if not isinstance(settings, dict):
            raise _bad_request("settings override must be an object")
        overrides["settings"] = settings

    template_media = payload.get("template_media")
    if template_media is not None:
        overrides["template_media"] = _sanitize_template_media(template_media)

    # Back-compat: allow top-level prompt override
    prompt = payload.get("prompt")
    if prompt is not None:
        if not isinstance(prompt, str):
            raise _bad_request("prompt override must be a string")
        settings_override = overrides.setdefault("settings", {})
        settings_override["prompt"] = prompt

    return overrides


@router.post("/{slot_id}/test-run")
async def run_test_slot(
    slot_id: str,
    test_image: UploadFile = File(...),
    slot_payload: str | None = Form(None),
    service: IngestService = Depends(get_ingest_service),
) -> dict[str, Any]:
    """Trigger synchronous processing for admin UI test button."""
    overrides = _parse_slot_payload(slot_payload)

    try:
        job, duration = await service.run_test_job(
            slot_id=slot_id,
            upload=test_image,
            overrides=overrides or None,
            expected_hash=None,
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "failure_reason": FailureReason.SLOT_NOT_FOUND.value,
            },
        ) from None
    except UnsupportedMediaError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "status": "error",
                "failure_reason": FailureReason.UNSUPPORTED_MEDIA_TYPE.value,
            },
        ) from exc
    except PayloadTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "status": "error",
                "failure_reason": FailureReason.PAYLOAD_TOO_LARGE.value,
            },
        ) from exc
    except UploadReadError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "failure_reason": FailureReason.INVALID_REQUEST.value,
            },
        ) from exc

    if overrides:
        job.slot_settings = _apply_overrides(job.slot_settings, overrides)

    try:
        await service.process(job)
    except ProviderTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "status": "timeout",
                "failure_reason": FailureReason.PROVIDER_TIMEOUT.value,
            },
        ) from exc
    except ProviderExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "status": "error",
                "failure_reason": FailureReason.PROVIDER_ERROR.value,
            },
        ) from exc

    if not job.job_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "failure_reason": FailureReason.INTERNAL_ERROR.value,
            },
        )

    return {
        "status": "done",
        "job_id": job.job_id,
        "public_result_url": f"/public/results/{job.job_id}",
        "completed_in_seconds": duration,
    }


def _slot_summary(slot: Slot) -> SlotSummaryResponse:
    return SlotSummaryResponse(
        slot_id=slot.id,
        display_name=slot.display_name,
        provider=slot.provider,
        operation=slot.operation,
        is_active=slot.is_active,
        version=slot.version,
        updated_at=slot.updated_at,
    )


def _slot_details(
    slot: Slot, job_repo: JobHistoryRepository, settings_service: SettingsService
) -> SlotDetailsResponse:
    template_media = [
        SlotTemplateMediaPayload(
            media_kind=binding.media_kind,
            media_object_id=binding.media_object_id,
            preview_url=f"/public/provider-media/{binding.media_object_id}",
        )
        for binding in slot.template_media
    ]
    recent_records = job_repo.list_recent_by_slot(slot.id, limit=10)
    recent_results: list[SlotRecentResultPayload] = []
    for record in recent_records:
        if record.status not in {"done", "failed", "timeout"}:
            continue
        finished_at = record.completed_at or record.started_at
        if finished_at is None:
            continue
        recent_results.append(
            SlotRecentResultPayload(
                job_id=record.job_id,
                status=record.status,
                finished_at=finished_at,
                public_url=f"/public/results/{record.job_id}",
                expires_at=record.result_expires_at,
            )
        )
    runtime = settings_service.snapshot()

    return SlotDetailsResponse(
        **_slot_summary(slot).model_dump(),
        size_limit_mb=slot.size_limit_mb,
        sync_response_seconds=runtime["sync_response_seconds"],
        settings=slot.settings or {},
        template_media=template_media,
        recent_results=recent_results,
    )
