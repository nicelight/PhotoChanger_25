"""Contract tests for the ingest endpoint (``POST /ingest/{slotId}``).

The module focuses on validating happy-path binary responses along with
timeout/error branches defined in ``spec/contracts/openapi.yaml``. Tests rely on
helpers from ``tests.conftest`` to reuse JSON Schemas and to override scaffolded
routers without modifying production code.
"""

from __future__ import annotations

import pytest
from fastapi import status
from fastapi.responses import JSONResponse, Response


@pytest.mark.contract
def test_ingest_returns_processed_image(
    contract_client,
    ingest_payload,
    patch_endpoint_response,
    sample_job,
):
    """Ingest returns an inline image when processing finishes synchronously."""

    def _response() -> Response:
        return Response(
            content=ingest_payload["image_bytes"],
            media_type="image/jpeg",
            headers={"X-Job-Id": sample_job["id"]},
        )

    patch_endpoint_response(
        "src.app.api.routes.ingest", "ingestSlot", _response
    )

    response = contract_client.post(
        "/ingest/slot-001",
        json=ingest_payload["form"],
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["x-job-id"] == sample_job["id"]
    assert response.content == ingest_payload["image_bytes"]


@pytest.mark.contract
def test_ingest_rejects_invalid_payload(
    contract_client,
    ingest_payload,
    patch_endpoint_response,
    validate_with_schema,
):
    """Invalid ingest payloads must return a structured ``400`` error."""

    def _response() -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": "invalid_payload",
                    "message": "image field is missing",
                    "details": {"field": "fileToUpload"},
                }
            },
        )

    patch_endpoint_response(
        "src.app.api.routes.ingest", "ingestSlot", _response
    )

    response = contract_client.post(
        "/ingest/slot-001",
        json=ingest_payload["form"],
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    payload = response.json()
    validate_with_schema(payload, "Error.json")
    assert payload["error"]["details"]["field"] == "fileToUpload"


@pytest.mark.contract
def test_ingest_timeout_returns_gateway_timeout(
    contract_client,
    ingest_payload,
    expired_job,
    patch_endpoint_response,
    validate_with_schema,
):
    """Expired jobs must trigger ``504 Gateway Timeout`` with deadline details."""

    def _response() -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={
                "error": {
                    "code": "sync_timeout",
                    "message": "Job timed out before completion",
                    "details": {
                        "job_id": expired_job["id"],
                        "expires_at": expired_job["expires_at"],
                    },
                }
            },
        )

    patch_endpoint_response(
        "src.app.api.routes.ingest", "ingestSlot", _response
    )

    response = contract_client.post(
        "/ingest/slot-001",
        json=ingest_payload["form"],
    )

    assert response.status_code == status.HTTP_504_GATEWAY_TIMEOUT
    payload = response.json()
    validate_with_schema(payload, "Error.json")
    assert payload["error"]["details"]["expires_at"] == expired_job["expires_at"]
