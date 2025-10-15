"""Unit coverage for deadline and TTL helpers defined in phase 2 scaffolding."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.app.domain import deadlines

pytestmark = pytest.mark.unit


def test_calculate_job_expires_at_respects_sync_timeout() -> None:
    """`expires_at` should equal `created_at + T_sync_response`."""

    created_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    expires_at = deadlines.calculate_job_expires_at(
        created_at,
        sync_response_timeout_sec=48,
        public_link_ttl_sec=48,
    )

    assert expires_at == created_at + timedelta(seconds=48)


def test_calculate_job_expires_at_validates_ttl_alignment() -> None:
    """`T_public_link_ttl` must mirror `T_sync_response` per SDD."""

    created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="must match sync_response_timeout_sec"):
        deadlines.calculate_job_expires_at(
            created_at,
            sync_response_timeout_sec=45,
            public_link_ttl_sec=60,
        )


def test_calculate_job_expires_at_rejects_non_positive_timeout() -> None:
    """Timeout inputs have to be positive integers."""

    created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="must be positive"):
        deadlines.calculate_job_expires_at(
            created_at,
            sync_response_timeout_sec=0,
            public_link_ttl_sec=0,
        )


def test_calculate_deadline_info_reports_remaining_time() -> None:
    """The helper returns remaining milliseconds and expiry flag."""

    now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    expires_at = now + timedelta(seconds=15)

    info = deadlines.calculate_deadline_info(expires_at, now=now)

    assert info.expires_at == expires_at
    assert info.remaining_ms == 15_000
    assert info.is_expired is False


def test_calculate_deadline_info_clamps_negative_remaining_time() -> None:
    """Expired deadlines should report zero remaining milliseconds."""

    now = datetime(2025, 1, 1, 12, 0, 30, tzinfo=timezone.utc)
    expires_at = now - timedelta(seconds=5)

    info = deadlines.calculate_deadline_info(expires_at, now=now)

    assert info.remaining_ms == 0
    assert info.is_expired is True


def test_calculate_artifact_expiry_never_exceeds_job_deadline() -> None:
    """Artifact expiry is the minimum of job deadline and TTL window."""

    created_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    job_expires_at = created_at + timedelta(seconds=40)

    expires_at = deadlines.calculate_artifact_expiry(
        artifact_created_at=created_at,
        job_expires_at=job_expires_at,
        ttl_seconds=60,
    )

    assert expires_at == job_expires_at

    longer_job_deadline = created_at + timedelta(seconds=120)
    ttl_limited = deadlines.calculate_artifact_expiry(
        artifact_created_at=created_at,
        job_expires_at=longer_job_deadline,
        ttl_seconds=30,
    )

    assert ttl_limited == created_at + timedelta(seconds=30)


def test_calculate_artifact_expiry_requires_positive_ttl() -> None:
    """TTL inputs must be positive to avoid silent overflow."""

    created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    job_expires_at = created_at + timedelta(seconds=45)

    with pytest.raises(ValueError, match="ttl_seconds must be positive"):
        deadlines.calculate_artifact_expiry(
            artifact_created_at=created_at,
            job_expires_at=job_expires_at,
            ttl_seconds=0,
        )


def test_calculate_result_expires_at_respects_retention_window() -> None:
    """Result retention extends finalized timestamp by configured hours."""

    finalized_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    expires_at = deadlines.calculate_result_expires_at(
        finalized_at,
        result_retention_hours=72,
    )

    assert expires_at == finalized_at + timedelta(hours=72)


def test_calculate_result_expires_at_requires_positive_retention() -> None:
    """Retention hours cannot be zero or negative."""

    finalized_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="result_retention_hours must be positive"):
        deadlines.calculate_result_expires_at(
            finalized_at,
            result_retention_hours=0,
        )

