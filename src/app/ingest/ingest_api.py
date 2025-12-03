"""HTTP routes for ingest operations."""

from __future__ import annotations

import logging
import hashlib
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

from .ingest_errors import (
    ChecksumMismatchError,
    PayloadTooLargeError,
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
) -> dict[str, str]:
    """Validate ingest payload; provider processing будет добавлено позже."""
    hash_value = hash_hex or hash_legacy
    upload = file or file_legacy

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
    try:
        job = service.prepare_job(slot_id)
    except KeyError:
        logger.warning("ingest.slot_not_found", extra={"slot_id": slot_id})
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "failure_reason": "slot_not_found"},
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

    return {"status": "validated", "slot_id": job.slot_id}
