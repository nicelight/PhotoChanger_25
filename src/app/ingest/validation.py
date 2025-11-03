"""Upload validation utilities."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from hashlib import sha256

from fastapi import UploadFile

from ..config import IngestLimits
from .ingest_errors import PayloadTooLargeError, UnsupportedMediaError, UploadReadError
from .ingest_models import UploadValidationResult

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class UploadValidator:
    """Validate ingest payloads against configured limits."""

    limits: IngestLimits

    async def validate(
        self,
        slot_limit_mb: int,
        upload: UploadFile,
    ) -> UploadValidationResult:
        allowed = set(self.limits.allowed_content_types)
        if upload.content_type not in allowed:
            logger.warning(
                "ingest.upload.unsupported_media",
                extra={"content_type": upload.content_type},
            )
            raise UnsupportedMediaError(upload.content_type)

        cap = min(slot_limit_mb * 1024 * 1024, self.limits.absolute_cap_bytes)
        digest = sha256()
        size = 0

        try:
            while True:
                chunk = await upload.read(self.limits.chunk_size_bytes)
                if not chunk:
                    break
                size += len(chunk)
                if size > cap:
                    logger.warning(
                        "ingest.upload.payload_too_large",
                        extra={"size_bytes": size, "limit_bytes": cap},
                    )
                    raise PayloadTooLargeError(size)
                digest.update(chunk)
        except PayloadTooLargeError:
            raise
        except Exception as exc:  # pragma: no cover - defensive branch
            await upload.close()
            logger.error("ingest.upload.read_failed", exc_info=exc)
            raise UploadReadError(str(exc)) from exc
        finally:
            await upload.seek(0)

        result = UploadValidationResult(
            content_type=upload.content_type or "application/octet-stream",
            size_bytes=size,
            sha256=digest.hexdigest(),
            filename=upload.filename or "upload",
        )
        logger.info(
            "ingest.upload.validated",
            extra={
                "filename": result.filename,
                "size_bytes": result.size_bytes,
                "content_type": result.content_type,
            },
        )
        return result
