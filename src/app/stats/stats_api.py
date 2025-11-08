"""Routes for statistics exposure."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from .stats_service import StatsService

router = APIRouter(prefix="/api/stats", tags=["stats"])


def get_stats_service(request: Request) -> StatsService:
    try:
        return request.app.state.stats_service  # type: ignore[attr-defined]
    except AttributeError as exc:  # pragma: no cover - defensive path
        raise RuntimeError("StatsService is not configured") from exc


@router.get("/overview")
def stats_overview(
    window_minutes: int = 60,
    service: StatsService = Depends(get_stats_service),
) -> dict[str, Any]:
    """Return statistics snapshot for admin UI."""
    return service.overview(window_minutes=window_minutes)
