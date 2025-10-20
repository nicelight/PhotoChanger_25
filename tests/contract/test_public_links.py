"""Contract tests for public download links exposed under ``/public``."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi import status

from tests.helpers.public_results import isoformat_utc

if TYPE_CHECKING:
    from tests.conftest import PublicResultCase


@pytest.mark.contract
def test_public_result_success(
    contract_client,
    fresh_public_result: PublicResultCase,
):
    """``GET /public/results/{job_id}`` issues a temporary redirect before TTL."""

    response = contract_client.get(
        f"/public/results/{fresh_public_result.job.id}",
        allow_redirects=False,
    )

    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert response.headers["location"] == fresh_public_result.public_url
    assert response.headers["photochanger-result-expires-at"] == isoformat_utc(
        fresh_public_result.expires_at
    )


@pytest.mark.contract
def test_public_result_gone(
    contract_client,
    expired_public_result: PublicResultCase,
    validate_with_schema,
):
    """Expired public links respond with ``410 Gone`` following ADR-0002."""

    response = contract_client.get(
        f"/public/results/{expired_public_result.job.id}",
        allow_redirects=False,
    )

    assert response.status_code == status.HTTP_410_GONE
    payload = response.json()
    validate_with_schema(payload, "Error.json")
    assert payload["error"]["code"] == "result_expired"
    assert payload["error"]["details"]["job_id"] == str(
        expired_public_result.job.id
    )
    assert payload["error"]["details"]["result_expires_at"] == isoformat_utc(
        expired_public_result.expires_at
    )
