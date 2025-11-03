"""Admin API routes for global settings."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/")
async def read_settings() -> dict[str, str]:
    """Return placeholder settings."""
    return {}
