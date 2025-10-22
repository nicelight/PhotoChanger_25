from __future__ import annotations

from http import HTTPStatus

import pytest

from src.app.security.jwt import decode_jwt

@pytest.mark.integration
def test_login_success_returns_jwt(
    contract_app,
    contract_client,
    validate_with_schema,
):
    response = contract_client.post(
        "/api/login",
        json={"username": "serg", "password": "serg-test-pass"},
    )

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    validate_with_schema(payload, "AuthToken.json")
    assert payload["token_type"] == "bearer"
    assert payload["expires_in_sec"] == contract_app.state.config.jwt_access_ttl_seconds
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"

    decoded = decode_jwt(
        payload["access_token"],
        contract_app.state.config.jwt_secret,
        algorithm="HS256",
    )
    assert decoded["sub"] == "serg"
    assert decoded["permissions"] == [
        "settings:write",
        "slots:write",
        "stats:read",
    ]
    assert decoded["exp"] - decoded["iat"] == payload["expires_in_sec"]


@pytest.mark.integration
def test_login_invalid_credentials(contract_client):
    response = contract_client.post(
        "/api/login",
        json={"username": "serg", "password": "wrong-password"},
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    payload = response.json()
    assert payload["error"]["code"] == "invalid_credentials"


@pytest.mark.integration
def test_login_throttled_after_repeated_failures(contract_client):
    for attempt in range(4):
        response = contract_client.post(
            "/api/login",
            json={"username": "serg", "password": f"wrong-{attempt}"},
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED

    throttled = contract_client.post(
        "/api/login",
        json={"username": "serg", "password": "still-wrong"},
    )

    assert throttled.status_code == HTTPStatus.TOO_MANY_REQUESTS
    payload = throttled.json()
    assert payload["error"]["code"] == "login_throttled"
