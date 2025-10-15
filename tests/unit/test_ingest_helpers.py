"""Unit tests for ingest helper utilities."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from uuid import UUID

import pytest

from src.app.api.routes.ingest import _decode_inline_result
from src.app.domain.models import Job, JobStatus


def _build_job() -> Job:
    now = datetime.now(timezone.utc)
    return Job(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        slot_id="slot-001",
        status=JobStatus.PENDING,
        is_finalized=True,
        failure_reason=None,
        expires_at=now,
        created_at=now,
        updated_at=now,
        payload_path=None,
    )


def test_decode_inline_result_success() -> None:
    job = _build_job()
    payload = b"binary-result"
    job.result_inline_base64 = base64.b64encode(payload).decode("ascii")
    job.result_mime_type = "image/jpeg"

    decoded, mime = _decode_inline_result(job)

    assert decoded == payload
    assert mime == "image/jpeg"


def test_decode_inline_result_without_mime() -> None:
    job = _build_job()
    job.result_inline_base64 = base64.b64encode(b"foo").decode("ascii")

    with pytest.raises(ValueError):
        _decode_inline_result(job)


def test_decode_inline_result_invalid_base64() -> None:
    job = _build_job()
    job.result_inline_base64 = "not-base64"
    job.result_mime_type = "image/png"

    with pytest.raises(ValueError):
        _decode_inline_result(job)
