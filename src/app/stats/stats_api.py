"""Routes for statistics exposure."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/slots")
async def slot_stats() -> list[dict[str, str]]:
    """Return placeholder slot statistics."""
    return []
