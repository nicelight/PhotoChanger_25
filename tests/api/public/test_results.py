from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest
from fastapi import status

from src.app.lifecycle import media_cleanup_once

from tests.helpers.public_results import isoformat_utc

if TYPE_CHECKING:
    from tests.conftest import PublicResultCase


@pytest.mark.integration
def test_download_public_result_redirects_before_ttl_expiry(
    contract_client,
    fresh_public_result: PublicResultCase,
):
    response = contract_client.get(
        f"/public/results/{fresh_public_result.job.id}",
        allow_redirects=False,
    )

    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert response.headers["location"] == fresh_public_result.public_url
    assert response.headers["photochanger-result-expires-at"] == isoformat_utc(
        fresh_public_result.expires_at
    )
    cache_control = response.headers["cache-control"]
    assert cache_control.startswith("private, max-age=")
    max_age = int(cache_control.split("=", 1)[1])
    assert max_age > 0


@pytest.mark.integration
def test_download_public_result_returns_410_after_ttl(
    contract_client,
    expired_public_result: PublicResultCase,
    validate_with_schema,
):
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


@pytest.mark.integration
def test_public_result_transitions_to_gone_and_cleanup_removes_media(
    contract_app,
    contract_client,
    fresh_public_result: PublicResultCase,
):
    response = contract_client.get(
        f"/public/results/{fresh_public_result.job.id}",
        allow_redirects=False,
    )

    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT

    expired_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    job = fresh_public_result.job
    job.result_expires_at = expired_at
    job.updated_at = expired_at
    registry = contract_app.state.service_registry
    job_service = registry.resolve_job_service()(config=contract_app.state.config)
    media_service = registry.resolve_media_service()(config=contract_app.state.config)
    assert job.result_file_path is not None
    media = media_service.get_media_by_path(job.result_file_path)
    assert media is not None
    media.expires_at = expired_at

    response = contract_client.get(
        f"/public/results/{job.id}", allow_redirects=False
    )
    assert response.status_code == status.HTTP_410_GONE

    media_cleanup_once(
        media_service=media_service,
        job_service=job_service,
        now=expired_at,
    )

    assert not fresh_public_result.media_path.exists()
    assert job.result_file_path is None

    response = contract_client.get(
        f"/public/results/{job.id}", allow_redirects=False
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
