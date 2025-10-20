"""Contract tests for public download links exposed under ``/public``."""

from __future__ import annotations

import pytest
from fastapi import status
from fastapi.responses import JSONResponse, Response


@pytest.mark.contract
def test_public_result_success(
    contract_client,
    patch_endpoint_response,
    sample_result,
):
    """``GET /public/results/{job_id}`` streams binary content with headers."""

    def _response() -> Response:
        return Response(
            content=b"fake-public-result",
            media_type="image/png",
            headers={
                "Content-Disposition": f"attachment; filename={sample_result['job_id']}.png"
            },
        )

    patch_endpoint_response(
        "src.app.api.routes.public", "downloadPublicResult", _response
    )

    response = contract_client.get(f"/public/results/{sample_result['job_id']}")

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "image/png"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.content == b"fake-public-result"


@pytest.mark.contract
def test_public_result_gone(
    contract_client,
    expired_result,
    patch_endpoint_response,
    validate_with_schema,
):
    """Expired public links respond with ``410 Gone`` following ADR-0002."""

    def _response() -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_410_GONE,
            content={
                "error": {
                    "code": "result_expired",
                    "message": "Result link TTL elapsed",
                    "details": {
                        "job_id": expired_result["job_id"],
                        "result_expires_at": expired_result["result_expires_at"],
                    },
                }
            },
        )

    patch_endpoint_response(
        "src.app.api.routes.public", "downloadPublicResult", _response
    )

    response = contract_client.get(f"/public/results/{expired_result['job_id']}")

    assert response.status_code == status.HTTP_410_GONE
    payload = response.json()
    validate_with_schema(payload, "Error.json")
    assert (
        payload["error"]["details"]["result_expires_at"]
        == expired_result["result_expires_at"]
    )
