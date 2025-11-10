from datetime import timedelta, timezone, datetime

import jwt
import pytest

from src.app.auth.auth_service import (
    AdminCredential,
    AuthService,
    InvalidCredentialsError,
    LoginThrottledError,
    hash_password,
)


def build_service() -> AuthService:
    credential = AdminCredential(username="serg", password_hash=hash_password("secret"))
    return AuthService(
        credentials={"serg": credential},
        signing_key="test-key",
        token_ttl=timedelta(hours=1),
    )


def test_authenticate_returns_token_for_valid_credentials() -> None:
    service = build_service()

    token, expires_in = service.authenticate("serg", "secret")

    assert expires_in == 3600
    payload = jwt.decode(token, "test-key", algorithms=["HS256"])
    assert payload["sub"] == "serg"
    assert payload["scope"] == "admin"


def test_authenticate_raises_for_invalid_password() -> None:
    service = build_service()

    with pytest.raises(InvalidCredentialsError):
        service.authenticate("serg", "wrong")


def test_authenticate_blocks_after_too_many_failures() -> None:
    service = build_service()

    for _ in range(service.max_failures):
        with pytest.raises(InvalidCredentialsError):
            service.authenticate("serg", "wrong")

    with pytest.raises(LoginThrottledError):
        service.authenticate("serg", "wrong")

    # simulate block expiry
    state = service._failed_logins["serg"]  # type: ignore[attr-defined]
    state.blocked_until = datetime.now(timezone.utc) - timedelta(seconds=1)

    token, _ = service.authenticate("serg", "secret")
    assert token
