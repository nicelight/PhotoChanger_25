"""Common dependencies for stubbed API routers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from fastapi import Request

from ...core.config import AppConfig
from ...security.jwt import decode_jwt
from ...security.service import AuthenticationService
from ..errors import forbidden_error, unauthorized_error


logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class AdminPrincipal:
    """Principal extracted from a verified bearer token."""

    username: str
    permissions: frozenset[str]


async def require_bearer_authentication(request: Request) -> AdminPrincipal:
    """Validate the ``Authorization`` header and return admin claims."""

    header = request.headers.get("Authorization")
    if not header:
        raise unauthorized_error("Bearer token is missing")

    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise unauthorized_error("Authorization header must use Bearer scheme")

    config = get_app_config(request)
    try:
        payload = decode_jwt(token.strip(), config.jwt_secret, algorithm="HS256")
    except ValueError:
        logger.warning("bearer token verification failed", extra={"reason": "invalid"})
        raise unauthorized_error("Bearer token is invalid") from None

    username = payload.get("sub")
    permissions_raw = payload.get("permissions")
    expires_at = payload.get("exp")
    if not isinstance(username, str) or not username:
        raise unauthorized_error("Bearer token is invalid")
    if not isinstance(permissions_raw, list) or not all(
        isinstance(permission, str) and permission
        for permission in permissions_raw
    ):
        raise unauthorized_error("Bearer token is invalid")
    try:
        expires_at_int = int(expires_at)
    except (TypeError, ValueError):
        raise unauthorized_error("Bearer token is invalid") from None

    now_ts = int(datetime.now(timezone.utc).timestamp())
    if expires_at_int <= now_ts:
        logger.info(
            "bearer token expired",
            extra={"username": username, "expires_at": expires_at_int},
        )
        raise unauthorized_error("Bearer token has expired")

    permissions = _expand_permissions(permissions_raw)
    principal = AdminPrincipal(username=username, permissions=permissions)
    request.state.admin_principal = principal
    return principal


def ensure_permissions(principal: AdminPrincipal, *required: str) -> None:
    """Ensure that ``principal`` has all requested permissions."""

    missing = [permission for permission in required if permission not in principal.permissions]
    if missing:
        logger.warning(
            "forbidden: missing permissions",
            extra={
                "username": principal.username,
                "missing_permissions": sorted(missing),
            },
        )
        raise forbidden_error(
            "Missing permissions: " + ", ".join(sorted(missing))
        )


def _expand_permissions(raw_permissions: Iterable[str]) -> frozenset[str]:
    """Return a normalised permissions set including implied scopes."""

    permissions = {permission for permission in raw_permissions}
    if "settings:write" in permissions:
        permissions.add("settings:read")
    return frozenset(permissions)


def get_app_config(request: Request) -> AppConfig:
    """Return the application configuration from FastAPI state."""

    config = getattr(request.app.state, "config", None)
    if not isinstance(config, AppConfig):  # pragma: no cover - defensive branch
        raise RuntimeError("application configuration is not initialised")
    return config


def get_authentication_service(request: Request) -> AuthenticationService:
    """Return the authentication service stored on the application state."""

    service = getattr(request.app.state, "auth_service", None)
    if not isinstance(service, AuthenticationService):
        raise RuntimeError("authentication service is not initialised")
    return service


__all__ = [
    "AdminPrincipal",
    "ensure_permissions",
    "get_app_config",
    "get_authentication_service",
    "require_bearer_authentication",
]
