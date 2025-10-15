"""Deadline calculation helpers defined by the SDD blueprints.

The SDD (``spec/docs/blueprints/domain-model.md``) mandates shared helper
functions to derive queue deadlines and TTL-related metadata from
``T_sync_response`` and ``T_result_retention``. This module declares the
interfaces without implementing business logic in phase 2.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from .models import JobDeadline


def calculate_job_expires_at(
    created_at: datetime,
    *,
    sync_response_timeout_sec: int,
    public_link_ttl_sec: int,
) -> datetime:
    """Calculate ``job.expires_at`` according to the unified deadline formula.

    The blueprint states that ``T_public_link_ttl`` must match
    ``T_sync_response``; implementations should validate the relationship and
    then return ``created_at + T_sync_response``. Actual arithmetic is deferred
    to later phases.
    """

    if sync_response_timeout_sec <= 0:
        raise ValueError("sync_response_timeout_sec must be positive")
    if public_link_ttl_sec <= 0:
        raise ValueError("public_link_ttl_sec must be positive")
    if public_link_ttl_sec != sync_response_timeout_sec:
        raise ValueError(
            "public_link_ttl_sec must match sync_response_timeout_sec per SDD"
        )

    return created_at + timedelta(seconds=sync_response_timeout_sec)


def calculate_deadline_info(expires_at: datetime, *, now: datetime) -> JobDeadline:
    """Build a :class:`JobDeadline` snapshot for ingest/admin polling."""

    if expires_at.tzinfo is not None and now.tzinfo is None:
        now = now.replace(tzinfo=expires_at.tzinfo)
    elif expires_at.tzinfo is None and now.tzinfo is not None:
        expires_at = expires_at.replace(tzinfo=now.tzinfo)

    delta = expires_at - now
    remaining_ms = max(int(delta.total_seconds() * 1000), 0)
    is_expired = expires_at <= now
    return JobDeadline(
        expires_at=expires_at,
        remaining_ms=remaining_ms,
        is_expired=is_expired,
    )


def calculate_artifact_expiry(
    *,
    artifact_created_at: datetime,
    job_expires_at: datetime,
    ttl_seconds: int,
) -> datetime:
    """Return the TTL for temporary media respecting the job deadline."""

    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")

    artifact_deadline = artifact_created_at + timedelta(seconds=ttl_seconds)

    if artifact_deadline.tzinfo is not None and job_expires_at.tzinfo is None:
        job_expires_at = job_expires_at.replace(tzinfo=artifact_deadline.tzinfo)
    elif artifact_deadline.tzinfo is None and job_expires_at.tzinfo is not None:
        artifact_deadline = artifact_deadline.replace(tzinfo=job_expires_at.tzinfo)

    return min(artifact_deadline, job_expires_at)


def calculate_result_expires_at(
    finalized_at: datetime, *, result_retention_hours: int
) -> datetime:
    """Return ``result_expires_at`` for finalized jobs (72h retention)."""

    if result_retention_hours <= 0:
        raise ValueError("result_retention_hours must be positive")

    return finalized_at + timedelta(hours=result_retention_hours)


__all__ = [
    "calculate_job_expires_at",
    "calculate_deadline_info",
    "calculate_artifact_expiry",
    "calculate_result_expires_at",
]
