"""HTTP routes for ingest operations."""

from __future__ import annotations

import logging
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
from fastapi.responses import Response

from .ingest_errors import (
    ChecksumMismatchError,
    PayloadTooLargeError,
    ProviderExecutionError,
    ProviderTimeoutError,
    SlotDisabledError,
    UnsupportedMediaError,
    UploadReadError,
)
from .ingest_models import FailureReason
from .ingest_service import IngestService

router = APIRouter(prefix="/api/ingest", tags=["ingest"])
logger = logging.getLogger(__name__)


def get_ingest_service(request: Request) -> IngestService:
    """Fetch ingest service from application state."""
    try:
        return request.app.state.ingest_service  # type: ignore[attr-defined]
    except AttributeError as exc:  # pragma: no cover - defensive path
        raise RuntimeError("IngestService is not configured") from exc


@router.post("/{slot_id}")
async def submit_ingest(
    slot_id: str,
    request: Request,
    password: str = Form(...),
    hash_hex: str | None = Form(None),
    hash_legacy: str | None = Form(None, alias="hash"),
    file: UploadFile | None = File(None),
    file_legacy: UploadFile | None = File(None, alias="fileToUpload"),
    service: IngestService = Depends(get_ingest_service),
) -> Response:
    """Validate ingest payload, run provider and return binary result."""
    hash_value = hash_hex or hash_legacy
    upload = file or file_legacy
    slot_lock = service.slot_lock(slot_id)

    if slot_lock.locked():
        logger.warning(
            "ingest.rate_limited",
            extra={"slot_id": slot_id, "reason": "slot_busy"},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "status": "error",
                "failure_reason": FailureReason.RATE_LIMITED.value,
                "retry_after": service.sync_response_seconds,
            },
        )

    # Логируем все поля формы (без содержимого файла) для отладки DSLR
    raw_form = await request.form()
    form_dump: dict[str, object] = {}
    for key, value in raw_form.multi_items():
        if isinstance(value, UploadFile):
            form_dump[key] = {
                "filename": value.filename,
                "content_type": value.content_type,
            }
        else:
            form_dump[key] = value

    logger.info(
        "ingest.request.debug slot=%s headers=%s form=%s",
        slot_id,
        dict(request.headers),
        form_dump,
    )
    if not password or not upload or not hash_value:
        logger.warning(
            "ingest.invalid_request_missing_fields",
            extra={"slot_id": slot_id, "has_password": bool(password), "has_file": bool(upload), "has_hash": bool(hash_value)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "failure_reason": FailureReason.INVALID_REQUEST.value,
                "details": "password, hash (hash_hex) and file are required",
            },
        )

    if not service.verify_ingest_password(password):
        logger.warning(
            "ingest.invalid_password", extra={"slot_id": slot_id, "hash_present": bool(hash_hex)}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "failure_reason": FailureReason.INVALID_PASSWORD.value,
            },
        )
    async with slot_lock:
        try:
            job = service.prepare_job(slot_id)
        except SlotDisabledError as exc:
            logger.warning("ingest.slot_disabled", extra={"slot_id": slot_id})
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "failure_reason": FailureReason.SLOT_DISABLED.value,
                },
            ) from exc
        except KeyError:
            logger.warning("ingest.slot_not_found", extra={"slot_id": slot_id})
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "failure_reason": FailureReason.SLOT_NOT_FOUND.value,
                },
            ) from None

        job.metadata["ingest_password"] = password

        try:
            await service.validate_upload(job, upload, hash_value)
        except UnsupportedMediaError as exc:
            service.record_failure(job, failure_reason=FailureReason.UNSUPPORTED_MEDIA_TYPE)
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail={
                    "status": "error",
                    "failure_reason": FailureReason.UNSUPPORTED_MEDIA_TYPE.value,
                },
            ) from exc
        except PayloadTooLargeError as exc:
            service.record_failure(job, failure_reason=FailureReason.PAYLOAD_TOO_LARGE)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={
                    "status": "error",
                    "failure_reason": FailureReason.PAYLOAD_TOO_LARGE.value,
                },
            ) from exc
        except ChecksumMismatchError as exc:
            service.record_failure(job, failure_reason=FailureReason.INVALID_REQUEST)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "failure_reason": FailureReason.INVALID_REQUEST.value,
                },
            ) from exc
        except UploadReadError as exc:
            service.record_failure(job, failure_reason=FailureReason.INVALID_REQUEST)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "failure_reason": FailureReason.INVALID_REQUEST.value,
                },
            ) from exc

        try:
            payload = await service.process(job)
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
                    "message": str(exc),
                },
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("ingest.unexpected_error", extra={"slot_id": slot_id})
            service.record_failure(job, failure_reason=FailureReason.INTERNAL_ERROR)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "status": "error",
                    "failure_reason": FailureReason.INTERNAL_ERROR.value,
                },
            ) from exc

        content_type = (
            job.metadata.get("result_content_type")
            or (job.upload.content_type if job.upload else None)
            or "image/png"
        )
        return Response(
            content=payload,
            media_type=content_type,
            headers={"Content-Disposition": 'attachment; filename="result.png"'},
        )
