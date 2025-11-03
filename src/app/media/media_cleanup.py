"""Helpers for result cleanup."""

from __future__ import annotations

import logging
from datetime import datetime

from ..repositories.media_object_repository import MediaObjectRepository
from .media_service import ResultStore

logger = logging.getLogger(__name__)


def cleanup_expired_results(
    media_repo: MediaObjectRepository,
    result_store: ResultStore,
    reference_time: datetime | None = None,
) -> int:
    """Remove expired media results and mark records cleaned."""
    now = reference_time or datetime.utcnow()
    expired = media_repo.list_expired_results(now)
    removed = 0
    for media in expired:
        result_store.remove_result_dir(media.slot_id, media.job_id)
        media_repo.mark_cleaned(media.id, now)
        removed += 1
        logger.info(
            "media.cleanup.removed",
            extra={"media_id": media.id, "slot_id": media.slot_id, "job_id": media.job_id},
        )
    return removed
