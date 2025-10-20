from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from src.app.domain.models import Job, JobStatus


def isoformat_utc(dt: datetime) -> str:
    return (
        dt.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def register_finalized_job(
    app,
    *,
    finalized_at: datetime,
    job_id: UUID | None = None,
    mime: str = "image/png",
) -> tuple[Job, str, datetime]:
    registry = app.state.service_registry
    job_service = registry.resolve_job_service()(config=app.state.config)
    media_service = registry.resolve_media_service()(config=app.state.config)

    now = datetime.now(timezone.utc)
    job_identifier = job_id or uuid4()
    retention_hours = job_service.result_retention_hours
    media, checksum = media_service.save_result_media(
        job_id=job_identifier,
        data=b"test-result-payload",
        mime=mime,
        finalized_at=finalized_at,
        retention_hours=retention_hours,
    )

    job = Job(
        id=job_identifier,
        slot_id="slot-001",
        status=JobStatus.PROCESSING,
        is_finalized=True,
        failure_reason=None,
        expires_at=now + timedelta(minutes=15),
        created_at=now - timedelta(minutes=5),
        updated_at=now,
        finalized_at=finalized_at,
        payload_path=None,
        provider_job_reference=None,
        result_file_path=media.path,
        result_inline_base64=None,
        result_mime_type=media.mime,
        result_size_bytes=media.size_bytes,
        result_checksum=checksum,
        result_expires_at=media.expires_at,
    )
    job_service.jobs[job.id] = job
    return job, media.public_url, media.expires_at
