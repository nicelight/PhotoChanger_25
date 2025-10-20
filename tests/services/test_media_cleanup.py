import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from src.app.domain.models import Job, JobStatus, MediaObject
from src.app.lifecycle import media_cleanup_once, run_periodic_media_cleanup


class _StubMediaService:
    def __init__(self, media: list[MediaObject]):
        self._media = list(media)
        self.calls: list[datetime] = []

    def purge_expired_media(self, *, now: datetime) -> list[MediaObject]:
        self.calls.append(now)
        expired: list[MediaObject] = []
        remaining: list[MediaObject] = []
        for obj in self._media:
            if obj.expires_at <= now:
                expired.append(obj)
            else:
                remaining.append(obj)
        self._media = remaining
        return expired


class _StubJobService:
    def __init__(self, jobs: list[Job]):
        self._jobs = list(jobs)
        self.calls: list[datetime] = []

    def purge_expired_results(self, *, now: datetime) -> list[Job]:
        self.calls.append(now)
        expired: list[Job] = []
        for job in self._jobs:
            if job.result_expires_at and job.result_expires_at <= now:
                job.result_file_path = None
                job.result_expires_at = None
                expired.append(job)
        return expired


def _media_object(*, expires_at: datetime) -> MediaObject:
    return MediaObject(
        id=uuid4(),
        path="results/sample.bin",
        public_url="/media/results/sample.bin",
        expires_at=expires_at,
        created_at=expires_at - timedelta(hours=1),
        job_id=uuid4(),
        mime="image/png",
        size_bytes=1024,
    )


def _job(*, expires_at: datetime | None) -> Job:
    now = datetime.now(timezone.utc)
    return Job(
        id=UUID("00000000-0000-0000-0000-0000000000aa"),
        slot_id="slot-001",
        status=JobStatus.PROCESSING,
        is_finalized=True,
        failure_reason=None,
        expires_at=now,
        created_at=now,
        updated_at=now,
        finalized_at=now,
        payload_path=None,
        provider_job_reference=None,
        result_file_path="results/sample.bin" if expires_at else None,
        result_inline_base64=None,
        result_mime_type="image/png" if expires_at else None,
        result_size_bytes=512 if expires_at else None,
        result_checksum="sha256:deadbeef" if expires_at else None,
        result_expires_at=expires_at,
    )


@pytest.mark.unit
def test_media_cleanup_once_collects_expired_entities() -> None:
    now = datetime.now(timezone.utc)
    media = [
        _media_object(expires_at=now - timedelta(minutes=5)),
        _media_object(expires_at=now + timedelta(minutes=5)),
    ]
    jobs = [
        _job(expires_at=now - timedelta(minutes=1)),
        _job(expires_at=now + timedelta(minutes=10)),
    ]
    media_service = _StubMediaService(media)
    job_service = _StubJobService(jobs)

    expired_media, expired_jobs = media_cleanup_once(
        media_service=media_service,
        job_service=job_service,
        now=now,
    )

    assert [obj.expires_at for obj in expired_media] == [media[0].expires_at]
    assert expired_jobs == [jobs[0]]
    assert job_service.calls == [now]
    assert media_service.calls == [now]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_periodic_media_cleanup_stops_on_shutdown() -> None:
    now = datetime.now(timezone.utc)
    media_service = _StubMediaService([])
    job_service = _StubJobService([])
    shutdown = asyncio.Event()

    def _clock() -> datetime:
        nonlocal now
        current = now
        now = now + timedelta(seconds=1)
        return current

    task = asyncio.create_task(
        run_periodic_media_cleanup(
            media_service=media_service,
            job_service=job_service,
            shutdown_event=shutdown,
            interval_seconds=0.05,
            clock=_clock,
        )
    )

    await asyncio.sleep(0.12)
    shutdown.set()
    await asyncio.wait_for(task, timeout=1)

    assert len(media_service.calls) >= 1
    assert len(job_service.calls) >= 1
