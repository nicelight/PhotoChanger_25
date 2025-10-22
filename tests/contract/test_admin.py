"""Contract coverage for administrative API endpoints.

Tests simulate authenticated requests to ``/api/slots``, ``/api/settings`` and
``/api/stats/*`` as described in ``spec/contracts/openapi.yaml``. Positive
scenarios validate JSON payloads against schemas, while negative ones ensure
error handling follows ``Error.json``.
"""

from __future__ import annotations

import pytest
from fastapi import status
from fastapi.responses import JSONResponse


ADMIN_MODULES = (
    "src.app.api.routes.slots",
    "src.app.api.routes.settings",
    "src.app.api.routes.stats",
)


@pytest.mark.contract
def test_login_success(
    contract_client,
    patch_endpoint_response,
    sample_auth_token,
    validate_with_schema,
):
    """``POST /api/login`` returns a signed JWT and TTL metadata."""

    def _response() -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_200_OK, content=sample_auth_token)

    patch_endpoint_response("src.app.api.routes.auth", "loginUser", _response)

    response = contract_client.post(
        "/api/login",
        json={"username": "serg", "password": "CorrectHorseBattery"},
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    validate_with_schema(payload, "AuthToken.json")
    assert payload["expires_in_sec"] == sample_auth_token["expires_in_sec"]


@pytest.mark.contract
def test_login_invalid_credentials(contract_client, patch_endpoint_response):
    """Invalid credentials trigger a 401 error with canonical payload."""

    def _response() -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": {
                    "code": "invalid_credentials",
                    "message": "Invalid username or password",
                }
            },
        )

    patch_endpoint_response("src.app.api.routes.auth", "loginUser", _response)

    response = contract_client.post(
        "/api/login", json={"username": "serg", "password": "wrong"}
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    payload = response.json()
    assert payload["error"]["code"] == "invalid_credentials"


@pytest.mark.contract
def test_login_throttled(contract_client, patch_endpoint_response):
    """Excessive login attempts result in a throttling error."""

    def _response() -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": {
                    "code": "login_throttled",
                    "message": "Too many login attempts. Try again later.",
                }
            },
        )

    patch_endpoint_response("src.app.api.routes.auth", "loginUser", _response)

    response = contract_client.post(
        "/api/login", json={"username": "serg", "password": "wrong"}
    )

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    payload = response.json()
    assert payload["error"]["code"] == "login_throttled"


@pytest.mark.contract
def test_list_slots_success(
    contract_client,
    allow_bearer_auth,
    patch_endpoint_response,
    sample_slot_list,
    validate_with_schema,
):
    """``GET /api/slots`` returns the slot catalog with recent results."""

    allow_bearer_auth(ADMIN_MODULES)

    def _response() -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_200_OK, content=sample_slot_list)

    patch_endpoint_response("src.app.api.routes.slots", "listSlots", _response)

    response = contract_client.get("/api/slots")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    validate_with_schema(payload, "SlotListResponse.json")
    assert payload["data"][0]["recent_results"][0]["result_expires_at"]


@pytest.mark.contract
def test_get_slot_success(
    contract_client,
    allow_bearer_auth,
    patch_endpoint_response,
    sample_slot,
    validate_with_schema,
):
    """``GET /api/slots/{slot_id}`` exposes slot metadata with deadlines."""

    allow_bearer_auth(ADMIN_MODULES)

    def _response() -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_200_OK, content=sample_slot)

    patch_endpoint_response("src.app.api.routes.slots", "getSlot", _response)

    response = contract_client.get("/api/slots/slot-001")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    validate_with_schema(payload, "Slot.json")
    assert (
        payload["recent_results"][0]["result_expires_at"]
        == sample_slot["recent_results"][0]["result_expires_at"]
    )


@pytest.mark.contract
def test_update_slot_success(
    contract_client,
    allow_bearer_auth,
    patch_endpoint_response,
    validate_with_schema,
):
    """``PUT /api/slots/{slot_id}`` acknowledges updates with ETag-friendly body."""

    allow_bearer_auth(ADMIN_MODULES)

    def _response() -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"id": "slot-001", "updated_at": "2025-10-18T10:01:00Z"},
        )

    patch_endpoint_response("src.app.api.routes.slots", "updateSlot", _response)

    response = contract_client.put(
        "/api/slots/slot-001",
        json={
            "name": "Portrait Enhancer",
            "provider_id": "gemini-pro",
            "operation_id": "portrait-v2",
            "settings_json": {"prompt": "v2"},
        },
        headers={"If-Match": "etag-slot-001"},
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    validate_with_schema(payload, "SlotUpdateResponse.json")


@pytest.mark.contract
def test_get_settings_success(
    contract_client,
    allow_bearer_auth,
    patch_endpoint_response,
    sample_settings,
    validate_with_schema,
):
    """``GET /api/settings`` returns TTL configuration and secret states."""

    allow_bearer_auth(ADMIN_MODULES)

    def _response() -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_200_OK, content=sample_settings)

    patch_endpoint_response(
        "src.app.api.routes.settings", "getPlatformSettings", _response
    )

    response = contract_client.get("/api/settings")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    validate_with_schema(payload, "Settings.json")
    assert (
        payload["media_cache"]["public_link_ttl_sec"]
        == payload["ingest"]["sync_response_timeout_sec"]
    )


@pytest.mark.contract
def test_get_slot_stats_success(
    contract_client,
    allow_bearer_auth,
    patch_endpoint_response,
    sample_slot_stats,
    validate_with_schema,
):
    """Slot stats endpoint returns histogram with last reset metadata."""

    allow_bearer_auth(ADMIN_MODULES)

    def _response() -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_200_OK, content=sample_slot_stats)

    patch_endpoint_response("src.app.api.routes.stats", "getSlotStats", _response)

    response = contract_client.get("/api/stats/slot-001?group_by=day")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    validate_with_schema(payload, "SlotStatsResponse.json")
    assert (
        payload["summary"]["last_reset_at"]
        == sample_slot_stats["summary"]["last_reset_at"]
    )


@pytest.mark.contract
def test_get_global_stats_success(
    contract_client,
    allow_bearer_auth,
    patch_endpoint_response,
    sample_global_stats,
    validate_with_schema,
):
    """Global stats endpoint returns paginated aggregates."""

    allow_bearer_auth(ADMIN_MODULES)

    def _response() -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_200_OK, content=sample_global_stats)

    patch_endpoint_response("src.app.api.routes.stats", "getGlobalStats", _response)

    response = contract_client.get(
        "/api/stats/global?page=1&page_size=10&group_by=week&sort_by=period_start&sort_order=desc"
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    validate_with_schema(payload, "GlobalStatsResponse.json")
    assert payload["meta"]["total"] == sample_global_stats["meta"]["total"]


# ---------------------------------------------------------------------------
# Negative scenarios
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_list_slots_requires_authentication(
    contract_client,
    patch_authentication_response,
    validate_with_schema,
):
    """Missing bearer token results in a ``401 Unauthorized`` contract error."""

    def _response() -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": {
                    "code": "unauthorized",
                    "message": "Bearer token is missing",
                }
            },
        )

    patch_authentication_response("src.app.api.routes.slots", _response)

    response = contract_client.get("/api/slots")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    payload = response.json()
    validate_with_schema(payload, "Error.json")


@pytest.mark.contract
def test_update_settings_forbidden(
    contract_client,
    allow_bearer_auth,
    patch_endpoint_response,
    validate_with_schema,
):
    """Admins without ``settings:write`` receive ``403 Forbidden`` responses."""

    allow_bearer_auth(ADMIN_MODULES)

    def _response() -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": {
                    "code": "forbidden",
                    "message": "settings:write scope required",
                }
            },
        )

    patch_endpoint_response(
        "src.app.api.routes.settings", "updatePlatformSettings", _response
    )

    response = contract_client.put(
        "/api/settings",
        json={
            "ingest": {"sync_response_timeout_sec": 50},
            "provider_keys": {},
        },
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    payload = response.json()
    validate_with_schema(payload, "Error.json")


@pytest.mark.contract
def test_global_stats_invalid_range(
    contract_client,
    allow_bearer_auth,
    patch_endpoint_response,
    validate_with_schema,
):
    """Invalid filters on stats endpoints must produce ``400`` errors."""

    allow_bearer_auth(ADMIN_MODULES)

    def _response() -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": "invalid_range",
                    "message": "`from` must be earlier than `to`",
                    "details": {"from": "2025-10-20", "to": "2025-10-10"},
                }
            },
        )

    patch_endpoint_response("src.app.api.routes.stats", "getGlobalStats", _response)

    response = contract_client.get(
        "/api/stats/global?from=2025-10-20T00:00:00Z&to=2025-10-10T00:00:00Z&group_by=week"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    payload = response.json()
    validate_with_schema(payload, "Error.json")
