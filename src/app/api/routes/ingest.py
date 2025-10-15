"""External ingest router for DSLR Remote Pro payloads."""

from __future__ import annotations

import hashlib
import logging
import re
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

from ...domain import calculate_artifact_expiry, calculate_job_expires_at
from ...domain.models import MediaObject
from ...services import (
    JobService,
    MediaService,
    ServiceRegistry,
    SettingsService,
    SlotService,
)
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
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details}},
    )


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
    status_code=status.HTTP_202_ACCEPTED,
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
        slot = slot_service.get_slot(slot_id)
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
            ttl_seconds=settings.media_cache.public_link_ttl_sec,
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
    except Exception:
        if stored_payload is not None:
            stored_payload.absolute_path.unlink(missing_ok=True)
        if media_object is not None:
            try:
                media_service.revoke_media(media_object)
            except Exception:  # pragma: no cover - best effort cleanup
                logger.exception("failed to revoke media after ingest error")
        logger.exception("failed to enqueue ingest job", extra={"slot_id": slot_id})
        await file_to_upload.close()
        return _error_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="ingest_unavailable",
            message="Ingest service is temporarily unavailable",
        )
    finally:
        await file_to_upload.close()

    _log_attempt(
        request=request,
        slot_id=slot_id,
        status_code=status.HTTP_202_ACCEPTED,
        message="ingest job accepted",
        extra={
            "job_id": str(job.id),
            "mime": mime,
            "size_bytes": stored_payload.size_bytes if stored_payload else None,
        },
    )

    response = Response(status_code=status.HTTP_202_ACCEPTED)
    response.headers["X-Job-Id"] = str(job.id)
    response.headers["Cache-Control"] = "no-store"
    return response


__all__ = ["router", "ingest_slot"]
