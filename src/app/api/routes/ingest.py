"""External ingest router for DSLR Remote Pro payloads."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Callable, TypeVar, cast
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Path as PathParam,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse, Response

try:  # pragma: no cover - stdlib guard for optional environments
    import binascii
except ModuleNotFoundError:  # pragma: no cover - fallback for restricted envs
    binascii = None  # type: ignore[assignment]

from ...domain import calculate_artifact_expiry, calculate_job_expires_at
from ...domain.models import Job, JobFailureReason, MediaObject
from ...services import (
    JobService,
    MediaService,
    ServiceRegistry,
    SettingsService,
    SlotService,
)
from ...services.job_service import QueueBusyError, QueueUnavailableError
from ..schemas import SlotIdentifier

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Ingest"])

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024
DEFAULT_FILENAME = "upload.bin"
POLL_INTERVAL_SECONDS = 1.0

TService = TypeVar("TService")


class PayloadTooLargeError(Exception):
    """Raised when the payload exceeds the configured size limit."""


class InvalidPayloadError(Exception):
    """Raised when the payload does not satisfy structural requirements."""


@dataclass(slots=True)
class StoredPayload:
    """Metadata about a payload written to MEDIA_ROOT."""

    absolute_path: Path
    relative_path: str
    size_bytes: int
    checksum: str


def _log_attempt(
    *,
    request: Request,
    slot_id: str,
    status_code: int,
    message: str,
    level: int = logging.INFO,
    extra: dict[str, Any] | None = None,
) -> None:
    client_ip = request.client.host if request.client else None
    payload = {"slot_id": slot_id, "status_code": status_code, "client_ip": client_ip}
    if extra:
        payload.update(extra)
    logger.log(level, message, extra={"ingest": payload})


def _get_registry(request: Request) -> ServiceRegistry:
    registry = getattr(request.app.state, "service_registry", None)
    if registry is None:  # pragma: no cover - defensive guard
        raise RuntimeError("service registry is not configured")
    return cast(ServiceRegistry, registry)


def _get_app_config(request: Request) -> Any | None:
    return getattr(request.app.state, "config", None)


def _instantiate_service(
    factory: Callable[..., object], expected: type[TService], *, app_config: Any | None
) -> TService:
    instance = factory(config=app_config)
    if not isinstance(instance, expected):  # pragma: no cover - misconfiguration guard
        raise RuntimeError(f"resolved service is not of type {expected!r}")
    return cast(TService, instance)


def get_settings_service(
    request: Request,
) -> SettingsService:
    registry = _get_registry(request)
    factory = registry.resolve_settings_service()
    return _instantiate_service(
        factory,
        SettingsService,
        app_config=_get_app_config(request),
    )


def get_slot_service(request: Request) -> SlotService:
    registry = _get_registry(request)
    factory = registry.resolve_slot_service()
    return _instantiate_service(
        factory,
        SlotService,
        app_config=_get_app_config(request),
    )


def get_media_service(request: Request) -> MediaService:
    registry = _get_registry(request)
    factory = registry.resolve_media_service()
    return _instantiate_service(
        factory,
        MediaService,
        app_config=_get_app_config(request),
    )


def get_job_service(request: Request) -> JobService:
    registry = _get_registry(request)
    factory = registry.resolve_job_service()
    return _instantiate_service(
        factory,
        JobService,
        app_config=_get_app_config(request),
    )


def _sanitize_filename(filename: str | None) -> str:
    candidate = Path(filename or "").name
    sanitized = re.sub(r"[^A-Za-z0-9_.-]", "_", candidate)
    return sanitized or DEFAULT_FILENAME


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        payload["details"] = details
    return JSONResponse(status_code=status_code, content={"error": payload})


if binascii is not None:  # pragma: no branch - evaluated once
    _BASE64_EXCEPTIONS: tuple[type[Exception], ...] = (ValueError, binascii.Error)
else:  # pragma: no cover - fallback branch
    _BASE64_EXCEPTIONS = (ValueError,)


def _decode_inline_result(job: Job) -> tuple[bytes, str]:
    """Decode ``job.result_inline_base64`` into bytes and return with MIME type."""

    if not job.result_inline_base64:
        raise ValueError("inline result is missing")
    try:
        payload = base64.b64decode(job.result_inline_base64, validate=True)
    except _BASE64_EXCEPTIONS as exc:  # type: ignore[misc]
        raise ValueError("invalid base64 inline result") from exc
    if not job.result_mime_type:
        raise ValueError("inline result MIME type is missing")
    return payload, job.result_mime_type


async def _store_payload(
    upload: UploadFile,
    *,
    media_root: Path,
    job_id: UUID,
    filename: str,
) -> StoredPayload:
    target_dir = media_root / "payloads" / str(job_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    size = 0
    checksum = hashlib.sha256()
    try:
        with target_path.open("wb") as destination:
            while True:
                chunk = await upload.read(CHUNK_SIZE)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_PAYLOAD_BYTES:
                    raise PayloadTooLargeError
                destination.write(chunk)
                checksum.update(chunk)
    except Exception:
        target_path.unlink(missing_ok=True)
        raise

    if size == 0:
        target_path.unlink(missing_ok=True)
        raise InvalidPayloadError("uploaded file is empty")

    relative_path = target_path.relative_to(media_root)
    return StoredPayload(
        absolute_path=target_path,
        relative_path=str(relative_path).replace("\\", "/"),
        size_bytes=size,
        checksum=checksum.hexdigest(),
    )


@router.post(
    "/ingest/{slotId}",
    status_code=status.HTTP_200_OK,
)
async def ingest_slot(
    request: Request,
    slot_id: Annotated[
        SlotIdentifier,
        PathParam(alias="slotId", description="Статический идентификатор ingest-слота"),
    ],
    password: Annotated[str, Form(alias="password", min_length=1)],
    file_to_upload: Annotated[UploadFile, File(alias="fileToUpload")],
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
    slot_service: Annotated[SlotService, Depends(get_slot_service)],
    media_service: Annotated[MediaService, Depends(get_media_service)],
    job_service: Annotated[JobService, Depends(get_job_service)],
) -> Response:
    """Принять ingest-запрос от DSLR Remote Pro."""

    settings = settings_service.read_settings()
    if not settings.dslr_password.is_set or not settings_service.verify_ingest_password(
        password
    ):
        _log_attempt(
            request=request,
            slot_id=slot_id,
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="ingest password rejected",
            level=logging.WARNING,
        )
        await file_to_upload.close()
        return _error_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_credentials",
            message="Invalid ingest credentials",
            details={"field": "password"},
        )

    try:
        slot = await slot_service.get_slot(slot_id)
    except KeyError:
        _log_attempt(
            request=request,
            slot_id=slot_id,
            status_code=status.HTTP_404_NOT_FOUND,
            message="ingest slot not found",
            level=logging.WARNING,
            extra={"reason": "missing_slot"},
        )
        await file_to_upload.close()
        return _error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="slot_not_found",
            message="Ingest slot is not available",
            details={"slot_id": slot_id},
        )

    mime = (file_to_upload.content_type or "").lower()
    if mime not in ALLOWED_MIME_TYPES:
        _log_attempt(
            request=request,
            slot_id=slot_id,
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            message="unsupported ingest mime type",
            level=logging.WARNING,
            extra={"mime": mime},
        )
        await file_to_upload.close()
        return _error_response(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            code="unsupported_media_type",
            message="Unsupported media type",
            details={"mime": mime or "unknown"},
        )

    app_config = _get_app_config(request)
    if app_config is None:  # pragma: no cover - defensive guard
        raise RuntimeError("application configuration is not available")
    media_root = Path(getattr(app_config, "media_root"))
    job_id = uuid4()
    created_at = datetime.now(timezone.utc)
    filename = _sanitize_filename(file_to_upload.filename)

    stored_payload: StoredPayload | None = None
    media_object: MediaObject | None = None
    job: Job | None = None
    job_state: Job | None = None
    response: Response | JSONResponse | None = None
    correlation_id: str | None = None

    try:
        stored_payload = await _store_payload(
            file_to_upload,
            media_root=media_root,
            job_id=job_id,
            filename=filename,
        )
        job_expires_at = calculate_job_expires_at(
            created_at,
            sync_response_timeout_sec=settings.ingest.sync_response_timeout_sec,
            public_link_ttl_sec=settings.media_cache.public_link_ttl_sec,
        )
        payload_expires_at = calculate_artifact_expiry(
            artifact_created_at=created_at,
            job_expires_at=job_expires_at,
            ttl_seconds=settings.ingest.ingest_ttl_sec,
        )
        media_object = media_service.register_media(
            path=stored_payload.relative_path,
            mime=mime,
            size_bytes=stored_payload.size_bytes,
            expires_at=payload_expires_at,
            job_id=job_id,
        )
        job = job_service.create_job(
            slot,
            payload=media_object,
            settings=settings,
            job_id=job_id,
            created_at=created_at,
        )

        poll_deadline = time.monotonic() + settings.ingest.sync_response_timeout_sec
        poll_interval = min(
            POLL_INTERVAL_SECONDS, settings.ingest.sync_response_timeout_sec
        )
        job_state = job
        while True:
            current = job_service.get_job(job.id)
            if current is not None:
                job_state = current
            if job_state is not None and job_state.is_finalized:
                break
            remaining = poll_deadline - time.monotonic()
            if remaining <= 0:
                break
            await asyncio.sleep(min(poll_interval, remaining))

        if job_state is None:
            correlation_id = str(uuid4())
            logger.error(
                "job disappeared during ingest polling",
                extra={
                    "slot_id": slot_id,
                    "job_id": str(job.id),
                    "correlation_id": correlation_id,
                },
            )
            response = _error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="job_not_found",
                message="Ingest job could not be located",
                details={"correlation_id": correlation_id},
            )
        elif not job_state.is_finalized:
            now_dt = datetime.now(timezone.utc)
            job_state = job_service.fail_job(
                job_state,
                failure_reason=JobFailureReason.TIMEOUT,
                occurred_at=now_dt,
            )
            response = _error_response(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                code="sync_timeout",
                message="Ingest processing exceeded the synchronous response window",
                details={
                    "job_id": str(job_state.id),
                    "expires_at": job_state.expires_at.isoformat(),
                },
            )
            _log_attempt(
                request=request,
                slot_id=slot_id,
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                message="ingest job timed out before finalization",
                level=logging.WARNING,
                extra={"job_id": str(job_state.id)},
            )
        elif job_state.failure_reason is not None:
            failure = job_state.failure_reason
            if failure is JobFailureReason.PROVIDER_ERROR:
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
                code = "provider_error"
                message_text = "Provider failed to process ingest request"
            elif failure is JobFailureReason.CANCELLED:
                status_code = status.HTTP_503_SERVICE_UNAVAILABLE
                code = "job_cancelled"
                message_text = "Ingest job was cancelled before completion"
            else:
                status_code = status.HTTP_504_GATEWAY_TIMEOUT
                code = "sync_timeout"
                message_text = (
                    "Ingest processing exceeded the synchronous response window"
                )
            response = _error_response(
                status_code=status_code,
                code=code,
                message=message_text,
                details={"job_id": str(job_state.id)},
            )
            _log_attempt(
                request=request,
                slot_id=slot_id,
                status_code=status_code,
                message="ingest job finalized with failure",
                level=logging.WARNING,
                extra={"job_id": str(job_state.id), "failure_reason": failure.value},
            )
        else:
            try:
                payload_bytes, mime_type = _decode_inline_result(job_state)
            except ValueError as exc:
                correlation_id = str(uuid4())
                logger.error(
                    "failed to decode inline result",
                    extra={
                        "slot_id": slot_id,
                        "job_id": str(job_state.id),
                        "correlation_id": correlation_id,
                        "reason": str(exc),
                    },
                )
                response = _error_response(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    code="invalid_inline_result",
                    message="Inline result payload is corrupted",
                    details={"correlation_id": correlation_id},
                )
            else:
                success = Response(content=payload_bytes, media_type=mime_type)
                success.status_code = status.HTTP_200_OK
                success.headers["X-Job-Id"] = str(job_state.id)
                success.headers["Cache-Control"] = "no-store"
                success.headers["Content-Length"] = str(len(payload_bytes))
                response = success
                _log_attempt(
                    request=request,
                    slot_id=slot_id,
                    status_code=status.HTTP_200_OK,
                    message="ingest job finalized successfully",
                    extra={
                        "job_id": str(job_state.id),
                        "mime": mime_type,
                        "size_bytes": len(payload_bytes),
                    },
                )

    except PayloadTooLargeError:
        if stored_payload is not None:
            stored_payload.absolute_path.unlink(missing_ok=True)
        _log_attempt(
            request=request,
            slot_id=slot_id,
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            message="ingest payload exceeds limit",
            level=logging.WARNING,
            extra={"max_bytes": MAX_PAYLOAD_BYTES},
        )
        await file_to_upload.close()
        return _error_response(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            code="payload_too_large",
            message="Payload exceeds the 2GB ingest limit",
            details={"max_bytes": MAX_PAYLOAD_BYTES},
        )
    except InvalidPayloadError:
        if stored_payload is not None:
            stored_payload.absolute_path.unlink(missing_ok=True)
        _log_attempt(
            request=request,
            slot_id=slot_id,
            status_code=status.HTTP_400_BAD_REQUEST,
            message="ingest payload missing content",
            level=logging.WARNING,
        )
        await file_to_upload.close()
        return _error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_payload",
            message="Uploaded file is empty",
            details={"field": "fileToUpload"},
        )
    except QueueBusyError:
        if stored_payload is not None:
            stored_payload.absolute_path.unlink(missing_ok=True)
        if media_object is not None:
            try:
                media_service.revoke_media(media_object)
            except Exception:  # pragma: no cover - best effort cleanup
                logger.exception("failed to revoke media after queue busy")
        _log_attempt(
            request=request,
            slot_id=slot_id,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            message="ingest queue reported saturation",
            level=logging.WARNING,
        )
        response = _error_response(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="queue_busy",
            message="Ingest queue is busy, retry later",
        )
    except QueueUnavailableError:
        if stored_payload is not None:
            stored_payload.absolute_path.unlink(missing_ok=True)
        if media_object is not None:
            try:
                media_service.revoke_media(media_object)
            except Exception:  # pragma: no cover - best effort cleanup
                logger.exception("failed to revoke media after queue outage")
        _log_attempt(
            request=request,
            slot_id=slot_id,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            message="ingest queue unavailable",
            level=logging.ERROR,
        )
        response = _error_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="queue_unavailable",
            message="Ingest service is temporarily unavailable",
        )
    except Exception:
        if stored_payload is not None:
            stored_payload.absolute_path.unlink(missing_ok=True)
        if media_object is not None:
            try:
                media_service.revoke_media(media_object)
            except Exception:  # pragma: no cover - best effort cleanup
                logger.exception("failed to revoke media after ingest error")
        correlation_id = str(uuid4())
        logger.exception(
            "unexpected ingest failure",
            extra={"slot_id": slot_id, "correlation_id": correlation_id},
        )
        response = _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            message="Unexpected ingest failure",
            details={"correlation_id": correlation_id},
        )
    finally:
        await file_to_upload.close()
        if media_object is not None:
            try:
                media_service.revoke_media(media_object)
            except Exception:  # pragma: no cover - best effort cleanup
                logger.exception(
                    "failed to revoke media after ingest completion",
                    extra={
                        "job_id": str(media_object.job_id)
                        if media_object.job_id
                        else None
                    },
                )
        elif stored_payload is not None:
            stored_payload.absolute_path.unlink(missing_ok=True)
        if job_state is not None:
            try:
                job_service.clear_inline_preview(job_state)
            except Exception:  # pragma: no cover - best effort cleanup
                logger.exception(
                    "failed to clear inline preview",
                    extra={"job_id": str(job_state.id)},
                )

    if response is None:
        response = _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            message="Unexpected ingest failure",
            details={"correlation_id": correlation_id},
        )
    if isinstance(response, Response):
        if "X-Job-Id" not in response.headers and job is not None:
            response.headers["X-Job-Id"] = str(job.id)
        if "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
    return response


__all__ = ["router", "ingest_slot"]
