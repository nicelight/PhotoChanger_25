"""Lifecycle helpers wiring background tasks for FastAPI startup."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable

from .domain.models import Job, MediaObject
from .services import JobService, MediaService


logger = logging.getLogger(__name__)


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def media_cleanup_once(
    *,
    media_service: MediaService,
    job_service: JobService,
    now: datetime | None = None,
) -> tuple[list[MediaObject], list[Job]]:
    """Run a single media cleanup iteration and return affected objects."""

    current = now or _default_clock()
    expired_media = media_service.purge_expired_media(now=current)
    try:
        expired_jobs = job_service.purge_expired_results(now=current)
    except NotImplementedError:
        logger.debug("Job service does not support purge_expired_results; skipping")
        expired_jobs = []
    return expired_media, expired_jobs


async def run_periodic_media_cleanup(
    *,
    media_service: MediaService,
    job_service: JobService,
    shutdown_event: asyncio.Event,
    interval_seconds: float = 900.0,
    clock: Callable[[], datetime] | None = None,
) -> None:
    """Execute media cleanup until ``shutdown_event`` is signalled."""

    interval = max(1.0, float(interval_seconds))
    tick = clock or _default_clock
    try:
        while not shutdown_event.is_set():
            now = tick()
            try:
                expired_media, expired_jobs = media_cleanup_once(
                    media_service=media_service,
                    job_service=job_service,
                    now=now,
                )
            except Exception:  # pragma: no cover - defensive logging
                logger.exception("Media cleanup iteration failed")
            else:
                if expired_media or expired_jobs:
                    logger.info(
                        "Purged %s media objects and %s jobs during cleanup",
                        len(expired_media),
                        len(expired_jobs),
                    )
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue
    except asyncio.CancelledError:  # pragma: no cover - shutdown path
        raise


__all__ = [
    "media_cleanup_once",
    "run_periodic_media_cleanup",
]
