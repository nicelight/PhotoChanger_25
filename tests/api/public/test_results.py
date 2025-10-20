from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import status

from tests.helpers.public_results import isoformat_utc, register_finalized_job


@pytest.mark.integration
def test_download_public_result_redirects_before_ttl_expiry(
    contract_app,
    contract_client,
):
    finalized_at = datetime.now(timezone.utc)
    job, public_url, expires_at = register_finalized_job(
        contract_app, finalized_at=finalized_at
    )

    response = contract_client.get(
        f"/public/results/{job.id}", allow_redirects=False
    )

    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert response.headers["location"] == public_url
    assert response.headers["photochanger-result-expires-at"] == isoformat_utc(
        expires_at
    )
    cache_control = response.headers["cache-control"]
    assert cache_control.startswith("private, max-age=")
    max_age = int(cache_control.split("=", 1)[1])
    assert max_age > 0


@pytest.mark.integration
def test_download_public_result_returns_410_after_ttl(
    contract_app,
    contract_client,
    validate_with_schema,
):
    registry = contract_app.state.service_registry
    job_service = registry.resolve_job_service()(config=contract_app.state.config)
    retention_hours = job_service.result_retention_hours
    finalized_at = datetime.now(timezone.utc) - timedelta(
        hours=retention_hours + 1
    )
    job, _, expires_at = register_finalized_job(
        contract_app, finalized_at=finalized_at
    )

    response = contract_client.get(
        f"/public/results/{job.id}", allow_redirects=False
    )

    assert response.status_code == status.HTTP_410_GONE
    payload = response.json()
    validate_with_schema(payload, "Error.json")
    assert payload["error"]["code"] == "result_expired"
    assert payload["error"]["details"]["job_id"] == str(job.id)
    assert payload["error"]["details"]["result_expires_at"] == isoformat_utc(
        expires_at
    )
