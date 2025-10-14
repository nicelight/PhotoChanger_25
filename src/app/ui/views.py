"""FastAPI UI routes for the administrative scaffolding.

Templates mirror layouts from ``Docs/frontend-examples`` and consume mock
structures compatible with ``spec/contracts/schemas``.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.responses import TemplateResponse

from . import mock_data

TEMPLATES = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent / "templates")
)

router = APIRouter(prefix="/ui", tags=["ui"])


@router.get("/slots", name="ui:slots-index", response_class=HTMLResponse)
def slots_index(request: Request) -> TemplateResponse:
    """Render the overview with static slot cards."""

    slots = mock_data.generate_slot_overview(count=6)
    context = {"request": request, "slots": slots}
    return TEMPLATES.TemplateResponse("slots/index.html", context)


@router.get("/slots/{slot_id}", name="ui:slot-detail", response_class=HTMLResponse)
def slot_detail(slot_id: str, request: Request) -> TemplateResponse:
    """Show mock slot configuration and latest results."""

    slot = mock_data.generate_slot_detail(slot_id)
    context = {
        "request": request,
        "slot": slot,
        "recent_results": slot.recent_results,
    }
    return TEMPLATES.TemplateResponse("slots/detail.html", context)


@router.get("/stats", name="ui:stats-index", response_class=HTMLResponse)
def stats_index(request: Request) -> TemplateResponse:
    """Display aggregated statistics with placeholder values."""

    summary, metrics = mock_data.generate_global_stats()
    context = {"request": request, "summary": summary, "metrics": metrics}
    return TEMPLATES.TemplateResponse("stats/index.html", context)


@router.get(
    "/results/{slot_id}", name="ui:results-gallery", response_class=HTMLResponse
)
def results_gallery(slot_id: str, request: Request) -> TemplateResponse:
    """Render gallery view for a slot using mock results."""

    slot, results = mock_data.generate_gallery(slot_id)
    context = {"request": request, "slot": slot, "results": results}
    return TEMPLATES.TemplateResponse("results/gallery.html", context)


@router.get("/auth/login", name="ui:auth-login", response_class=HTMLResponse)
def login(request: Request) -> TemplateResponse:
    """Render login page stub without calling the Auth API."""

    context = {"request": request}
    return TEMPLATES.TemplateResponse("auth/login.html", context)


__all__ = ["router"]
