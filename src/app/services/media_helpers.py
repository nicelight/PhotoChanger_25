"""Helpers for persisting provider results under ``MEDIA_ROOT/results``."""

from __future__ import annotations

import base64
import binascii
from datetime import datetime
from uuid import UUID

from .media_service import MediaService
from ..domain.models import MediaObject


def persist_base64_result(
    media_service: MediaService,
    *,
    job_id: UUID,
    base64_data: str,
    finalized_at: datetime,
    retention_hours: int,
    mime: str,
    suggested_name: str | None = None,
) -> tuple[MediaObject, str]:
    """Decode ``base64_data`` and persist it via :class:`MediaService`.

    The helper implements the requirement from SDD section 4.4.9: inline
    provider payloads must be materialised under ``MEDIA_ROOT/results`` using
    ``MediaService.save_result_media`` so that public download links share the
    same retention logic as file-based responses.

    Args:
        media_service: Service responsible for storing media artefacts.
        job_id: Identifier of the job owning the result.
        base64_data: Base64-encoded bytes returned by the provider.
        finalized_at: Timestamp when the provider finished processing.
        retention_hours: Retention window in hours (72h per ADR-0002).
        mime: Mime type associated with the artefact.
        suggested_name: Optional filename hint supplied by the provider.

    Returns:
        Tuple of the registered :class:`MediaObject` and its SHA-256 checksum.

    Raises:
        binascii.Error: If ``base64_data`` is not valid base64.
        ValueError: If ``base64_data`` contains invalid padding.
    """

    decoded = base64.b64decode(base64_data, validate=True)
    media, checksum = media_service.save_result_media(
        job_id=job_id,
        data=decoded,
        mime=mime,
        finalized_at=finalized_at,
        retention_hours=retention_hours,
        suggested_name=suggested_name,
    )
    return media, checksum


__all__ = ["persist_base64_result"]

