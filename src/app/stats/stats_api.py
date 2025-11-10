"""Routes for statistics exposure."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from ..auth.auth_dependencies import require_admin_user

from .stats_service import StatsService

router = APIRouter(
    prefix="/api/stats",
    tags=["stats"],
    dependencies=[Depends(require_admin_user)],
)


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


@router.get("/slots")
def stats_slots(
    window_minutes: int = 60,
    service: StatsService = Depends(get_stats_service),
) -> dict[str, Any]:
    """Return per-slot metrics tailored for graphs."""
    return service.slot_stats(window_minutes=window_minutes)
