from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterator

import pytest

pytest.importorskip("fastapi")
from fastapi import status

jwt = pytest.importorskip("jwt")

from src.app.security.service import AuthenticationService

_ADMIN_PERMISSIONS = ["settings:write", "slots:write", "stats:read"]
_SERG_HASH = (
    "pbkdf2_sha256$390000$5468b98e343193bd674fdcc63e24c74f$"
    "b78b20878e016f947147690703fe28bd63b7f6ed1f218a30580dc888f4f6a8cd"
)


@pytest.fixture
def admin_credentials_factory(tmp_path: Path) -> Callable[..., Path]:
    """Return a helper that writes runtime credentials with custom throttling."""

    def _factory(
        *,
        max_attempts: int = 5,
        window_seconds: int = 60,
        lockout_seconds: int = 300,
    ) -> Path:
        payload = {
            "admins": [
                {
                    "username": "serg",
                    "password_hash": _SERG_HASH,
                    "permissions": _ADMIN_PERMISSIONS,
                }
            ],
            "throttling": {
                "max_attempts": max_attempts,
                "window_seconds": window_seconds,
                "lockout_seconds": lockout_seconds,
            },
        }
        path = tmp_path / "runtime_credentials.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    return _factory


@pytest.mark.integration
def test_login_success_returns_signed_jwt(
    contract_app,
    contract_client,
    admin_credentials_factory: Callable[..., Path],
) -> None:
    """Successful login issues a signed JWT with expected claims and TTL."""

    credentials_path = admin_credentials_factory()
    auth_service = AuthenticationService.load_from_file(credentials_path)
    contract_app.state.auth_service = auth_service
    config = contract_app.state.config

    response = contract_client.post(
        "/api/login",
        json={"username": "serg", "password": "serg-test-pass"},
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["expires_in_sec"] == config.jwt_access_ttl_seconds

    decoded = jwt.decode(
        payload["access_token"],
        config.jwt_secret,
        algorithms=["HS256"],
    )
    assert decoded["sub"] == "serg"
    assert decoded["permissions"] == _ADMIN_PERMISSIONS
    assert decoded["exp"] - decoded["iat"] == config.jwt_access_ttl_seconds


@pytest.mark.integration
@pytest.mark.parametrize(
    "username,password",
    [
        ("unknown", "serg-test-pass"),
        ("serg", "totally-wrong"),
    ],
    ids=["unknown_user", "invalid_password"],
)
def test_login_invalid_credentials_return_unauthorized(
    contract_app,
    contract_client,
    admin_credentials_factory: Callable[..., Path],
    username: str,
    password: str,
) -> None:
    """Unknown users and invalid passwords return uniform 401 responses."""

    credentials_path = admin_credentials_factory()
    contract_app.state.auth_service = AuthenticationService.load_from_file(
        credentials_path
    )

    response = contract_client.post(
        "/api/login",
        json={"username": username, "password": password},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    payload = response.json()
    assert payload["error"]["code"] == "invalid_credentials"
    assert payload["error"]["message"] == "Invalid username or password"


@pytest.mark.integration
def test_login_throttling_blocks_and_unlocks_after_lockout(
    contract_app,
    contract_client,
    admin_credentials_factory: Callable[..., Path],
) -> None:
    """Repeated failures trigger throttling and unlock after the lockout window."""

    credentials_path = admin_credentials_factory(
        max_attempts=2, window_seconds=60, lockout_seconds=10
    )
    auth_service = AuthenticationService.load_from_file(credentials_path)
    contract_app.state.auth_service = auth_service

    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    timestamps: Iterator[datetime] = iter(
        [
            base_time,
            base_time + timedelta(seconds=1),
            base_time + timedelta(seconds=2),
            base_time + timedelta(seconds=12),
            base_time + timedelta(seconds=13),
        ]
    )
    auth_service._now = lambda: next(timestamps)

    def _login(password: str):
        return contract_client.post(
            "/api/login", json={"username": "serg", "password": password}
        )

    first = _login("wrong-pass")
    assert first.status_code == status.HTTP_401_UNAUTHORIZED
    assert first.json()["error"]["code"] == "invalid_credentials"

    second = _login("wrong-pass")
    assert second.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert second.json()["error"]["code"] == "login_throttled"

    third = _login("serg-test-pass")
    assert third.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert third.json()["error"]["code"] == "login_throttled"

    fourth = _login("serg-test-pass")
    assert fourth.status_code == status.HTTP_200_OK

    fifth = _login("wrong-pass")
    assert fifth.status_code == status.HTTP_401_UNAUTHORIZED
    assert fifth.json()["error"]["code"] == "invalid_credentials"
