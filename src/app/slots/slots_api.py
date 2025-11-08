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
            raise _bad_request("media_kind and media_object_id are required for template_media items")
        prepared.append({"media_kind": str(media_kind), "media_object_id": str(media_object_id)})
    return prepared


def _parse_slot_payload(raw_value: str | None) -> dict[str, Any]:
    if raw_value in (None, ""):
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
            detail={"status": "error", "failure_reason": FailureReason.SLOT_NOT_FOUND.value},
        ) from None
    except UnsupportedMediaError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={"status": "error", "failure_reason": FailureReason.UNSUPPORTED_MEDIA_TYPE.value},
        ) from exc
    except PayloadTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"status": "error", "failure_reason": FailureReason.PAYLOAD_TOO_LARGE.value},
        ) from exc
    except UploadReadError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "failure_reason": FailureReason.INVALID_REQUEST.value},
        ) from exc
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
        "completed_in_seconds": duration,
    }
