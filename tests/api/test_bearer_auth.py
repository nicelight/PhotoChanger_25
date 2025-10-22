from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("fastapi")

from fastapi import status

from src.app.security.jwt import encode_jwt


def _build_token(secret: str, permissions: list[str], *, expires_in: int = 3600) -> str:
    issued_at = datetime.now(timezone.utc)
    claims = {
        "sub": "serg",
        "permissions": permissions,
        "iat": int(issued_at.timestamp()),
        "exp": int((issued_at + timedelta(seconds=expires_in)).timestamp()),
    }
    return encode_jwt(claims, secret, algorithm="HS256")


@pytest.mark.integration
def test_missing_bearer_token_returns_unauthorized(contract_client):
    response = contract_client.get("/api/slots")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    payload = response.json()
    assert payload == {
        "error": {
            "code": "unauthorized",
            "message": "Bearer token is missing",
        }
    }


@pytest.mark.integration
def test_invalid_scheme_returns_unauthorized(contract_client):
    response = contract_client.get(
        "/api/slots", headers={"Authorization": "Basic Zm9v"}
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    payload = response.json()
    assert payload == {
        "error": {
            "code": "unauthorized",
            "message": "Authorization header must use Bearer scheme",
        }
    }


@pytest.mark.integration
def test_expired_token_returns_unauthorized(contract_client):
    secret = contract_client.app.state.config.jwt_secret  # type: ignore[attr-defined]
    token = _build_token(secret, ["slots:write"], expires_in=-60)

    response = contract_client.get(
        "/api/slots", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    payload = response.json()
    assert payload == {
        "error": {
            "code": "unauthorized",
            "message": "Bearer token has expired",
        }
    }


@pytest.mark.integration
def test_missing_permission_returns_forbidden(contract_client):
    secret = contract_client.app.state.config.jwt_secret  # type: ignore[attr-defined]
    token = _build_token(secret, ["settings:write"])

    response = contract_client.get(
        "/api/slots", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    payload = response.json()
    assert payload == {
        "error": {
            "code": "forbidden",
            "message": "Missing permissions: slots:write",
        }
    }
