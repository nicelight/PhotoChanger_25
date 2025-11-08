"""Admin slot routes (test-run, CRUD stubs)."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from ..ingest.ingest_errors import (
    PayloadTooLargeError,
    ProviderExecutionError,
    ProviderTimeoutError,
    UnsupportedMediaError,
    UploadReadError,
)
from ..ingest.ingest_models import FailureReason
from ..ingest.ingest_service import IngestService

router = APIRouter(prefix="/api/slots", tags=["slots"])


def get_ingest_service(request: Request) -> IngestService:
    """Fetch ingest service from application state."""
    try:
        return request.app.state.ingest_service  # type: ignore[attr-defined]
    except AttributeError as exc:  # pragma: no cover - defensive path
        raise RuntimeError("IngestService is not configured") from exc


def _parse_template_media(raw_value: str | None) -> list[dict[str, str]]:
    if not raw_value:
        return []
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "failure_reason": FailureReason.INVALID_REQUEST.value,
                "details": "template_media must be a JSON array of objects",
            },
        ) from exc

    if not isinstance(payload, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "failure_reason": FailureReason.INVALID_REQUEST.value,
                "details": "template_media must be a JSON array of objects",
            },
        )

    prepared: list[dict[str, str]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "failure_reason": FailureReason.INVALID_REQUEST.value,
                    "details": f"template_media[{index}] must be an object",
                },
            )
        media_kind = item.get("media_kind")
        media_object_id = item.get("media_object_id")
        if not media_kind or not media_object_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "failure_reason": FailureReason.INVALID_REQUEST.value,
                    "details": "media_kind and media_object_id are required for template_media items",
                },
            )
        prepared.append({"media_kind": str(media_kind), "media_object_id": str(media_object_id)})
    return prepared


def _apply_overrides(job_settings: dict[str, Any] | None, overrides: dict[str, Any]) -> dict[str, Any]:
    updated = dict(job_settings or {})
    for key, value in overrides.items():
        updated[key] = value
    return updated


@router.post("/{slot_id}/test-run")
async def run_test_slot(
    slot_id: str,
    test_image: UploadFile = File(...),
    prompt: str | None = Form(None),
    template_media: str | None = Form(None),
    service: IngestService = Depends(get_ingest_service),
) -> dict[str, str]:
    """Trigger synchronous processing for admin UI test button."""
    try:
        job = service.prepare_job(slot_id, source="ui_test")
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "failure_reason": FailureReason.SLOT_NOT_FOUND.value},
        ) from None

    overrides: dict[str, Any] = {}
    bindings = _parse_template_media(template_media)
    if bindings:
        overrides["template_media"] = bindings
    if prompt is not None:
        overrides["prompt"] = prompt
    if overrides:
        job.slot_settings = _apply_overrides(job.slot_settings, overrides)

    try:
        await service.validate_upload(job, test_image, expected_hash=None)
    except UnsupportedMediaError as exc:
        service.record_failure(job, failure_reason=FailureReason.UNSUPPORTED_MEDIA_TYPE)
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={"status": "error", "failure_reason": FailureReason.UNSUPPORTED_MEDIA_TYPE.value},
        ) from exc
    except PayloadTooLargeError as exc:
        service.record_failure(job, failure_reason=FailureReason.PAYLOAD_TOO_LARGE)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"status": "error", "failure_reason": FailureReason.PAYLOAD_TOO_LARGE.value},
        ) from exc
    except UploadReadError as exc:
        service.record_failure(job, failure_reason=FailureReason.INVALID_REQUEST)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "failure_reason": FailureReason.INVALID_REQUEST.value},
        ) from exc

    try:
        await service.process(job)
    except ProviderTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"status": "timeout", "failure_reason": FailureReason.PROVIDER_TIMEOUT.value},
        ) from exc
    except ProviderExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"status": "error", "failure_reason": FailureReason.PROVIDER_ERROR.value},
        ) from exc

    if not job.job_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "failure_reason": FailureReason.INTERNAL_ERROR.value},
        )

    return {
        "status": "done",
        "job_id": job.job_id,
        "public_result_url": f"/public/results/{job.job_id}",
    }
