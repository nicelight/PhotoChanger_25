"""Common dependencies for stubbed API routers."""

from __future__ import annotations


async def require_bearer_authentication() -> bool:
    """Placeholder dependency for JWT validation."""

    return False
