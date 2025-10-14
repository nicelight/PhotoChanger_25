"""Deadline calculation helpers defined by the SDD blueprints.

The SDD (``spec/docs/blueprints/domain-model.md``) mandates shared helper
functions to derive queue deadlines and TTL-related metadata from
``T_sync_response`` and ``T_result_retention``. This module declares the
interfaces without implementing business logic in phase 2.
"""

from __future__ import annotations

from datetime import datetime

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

    raise NotImplementedError


def calculate_deadline_info(expires_at: datetime, *, now: datetime) -> JobDeadline:
    """Build a :class:`JobDeadline` snapshot for ingest/admin polling."""

    raise NotImplementedError


def calculate_artifact_expiry(
    *,
    artifact_created_at: datetime,
    job_expires_at: datetime,
    ttl_seconds: int,
) -> datetime:
    """Return the TTL for temporary media respecting the job deadline."""

    raise NotImplementedError


def calculate_result_expires_at(
    finalized_at: datetime, *, result_retention_hours: int
) -> datetime:
    """Return ``result_expires_at`` for finalized jobs (72h retention)."""

    raise NotImplementedError


__all__ = [
    "calculate_job_expires_at",
    "calculate_deadline_info",
    "calculate_artifact_expiry",
    "calculate_result_expires_at",
]
