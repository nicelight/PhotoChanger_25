"""Common dependencies for stubbed API routers."""

from __future__ import annotations

from fastapi import Request

from ...core.config import AppConfig
from ...security.service import AuthenticationService


async def require_bearer_authentication() -> bool:
    """Placeholder dependency for JWT validation."""

    return False


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
