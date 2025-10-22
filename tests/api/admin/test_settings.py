"""Integration tests for administrative settings endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Iterable

import pytest

pytest.importorskip("fastapi")

from src.app.security.jwt import encode_jwt

pytestmark = pytest.mark.integration


def _authorization_headers(
    contract_app,
    permissions: Iterable[str],
    *,
    username: str = "serg",
    expires_in: int = 3600,
) -> dict[str, str]:
    """Construct Authorization headers for a bearer token with given permissions."""

    now = datetime.now(timezone.utc)
    claims = {
        "sub": username,
        "permissions": list(permissions),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    secret = contract_app.state.config.jwt_secret  # type: ignore[attr-defined]
    token = encode_jwt(claims, secret, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _get_settings_service(contract_app):
    registry = contract_app.state.service_registry  # type: ignore[attr-defined]
    return registry.resolve_settings_service()(config=contract_app.state.config)


def test_get_settings_returns_snapshot(contract_app, contract_client):
    settings_service = _get_settings_service(contract_app)
    expected = settings_service.get_settings()

    response = contract_client.get(
        "/api/settings",
        headers=_authorization_headers(contract_app, ["settings:read"]),
    )

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["ingest"]["sync_response_timeout_sec"] == expected.ingest.sync_response_timeout_sec
    assert payload["ingest"]["ingest_ttl_sec"] == expected.ingest.ingest_ttl_sec
    assert payload["media_cache"]["public_link_ttl_sec"] == expected.media_cache.public_link_ttl_sec
    assert (
        payload["media_cache"]["processed_media_ttl_hours"]
        == expected.media_cache.processed_media_ttl_hours
    )
    assert payload["dslr_password"]["is_set"] == expected.dslr_password.is_set
    assert payload["dslr_password"]["updated_by"] == expected.dslr_password.updated_by


def test_get_settings_missing_permission_returns_forbidden(contract_app, contract_client):
    response = contract_client.get(
        "/api/settings",
        headers=_authorization_headers(contract_app, ["stats:read"]),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    payload = response.json()
    assert payload["error"]["code"] == "forbidden"
    assert payload["error"]["message"].startswith("Missing permissions: settings:read")


def test_update_settings_updates_ttl(contract_app, contract_client):
    settings_service = _get_settings_service(contract_app)
    headers = _authorization_headers(contract_app, ["settings:write"])

    response = contract_client.put(
        "/api/settings",
        json={"ingest": {"sync_response_timeout_sec": 55}},
        headers=headers,
    )

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["ingest"] == {
        "sync_response_timeout_sec": 55,
        "ingest_ttl_sec": 55,
    }
    assert payload["media_cache"]["public_link_ttl_sec"] == 55

    updated = settings_service.get_settings(force_refresh=True)
    assert updated.ingest.sync_response_timeout_sec == 55
    assert updated.ingest.ingest_ttl_sec == 55
    assert updated.media_cache.public_link_ttl_sec == 55


def test_update_settings_rejects_provider_keys(contract_app, contract_client):
    headers = _authorization_headers(contract_app, ["settings:write"])

    response = contract_client.put(
        "/api/settings",
        json={"provider_keys": {"gemini": {"api_key": "abc"}}},
        headers=headers,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    payload = response.json()
    assert payload["error"]["code"] == "provider_keys_not_supported"


def test_update_settings_validation_errors_bubble_up(contract_app, contract_client):
    headers = _authorization_headers(contract_app, ["settings:write"])

    response = contract_client.put(
        "/api/settings",
        json={"ingest": {"sync_response_timeout_sec": 30}},
        headers=headers,
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    payload = response.json()
    assert any(
        error.get("loc", ["unknown"])[-1] == "sync_response_timeout_sec"
        for error in payload.get("detail", [])
    )


def test_rotate_dslr_password_updates_state_and_logs(contract_app, contract_client):
    settings_service = _get_settings_service(contract_app)
    headers = _authorization_headers(contract_app, ["settings:write"])
    new_password = "new-dslr-secret"

    response = contract_client.put(
        "/api/settings",
        json={"dslr_password": {"value": new_password}},
        headers=headers,
    )

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["dslr_password"]["is_set"] is True
    assert payload["dslr_password"]["updated_by"] == "serg"

    assert settings_service.verify_ingest_password(new_password) is True
    refreshed = settings_service.get_settings(force_refresh=True)
    assert refreshed.dslr_password.updated_by == "serg"
    assert any(
        record.get("action") == "settings.rotate_ingest_password"
        for record in getattr(settings_service, "audit_records", [])
    )


def test_rotate_dslr_password_missing_permission(contract_app, contract_client):
    response = contract_client.put(
        "/api/settings",
        json={"dslr_password": {"value": "unauthorised"}},
        headers=_authorization_headers(contract_app, ["settings:read"]),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    payload = response.json()
    assert payload["error"]["code"] == "forbidden"
    assert "settings:write" in payload["error"]["message"]
