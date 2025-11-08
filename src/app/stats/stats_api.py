"""Routes for statistics exposure."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/overview")
async def stats_overview() -> dict[str, Any]:
    """Return placeholder statistics snapshot."""
    return {"window_minutes": 60, "system": {}, "slots": []}
