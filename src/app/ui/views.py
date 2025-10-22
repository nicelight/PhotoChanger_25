"""FastAPI UI routes for the administrative scaffolding.

Templates mirror layouts from ``spec/docs/frontend-examples`` and consume mock
structures compatible with ``spec/contracts/schemas``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from starlette.responses import Response

from . import mock_data

try:
    from fastapi.templating import Jinja2Templates
except ModuleNotFoundError:  # pragma: no cover - optional dependency guard
    Jinja2Templates = None  # type: ignore[assignment]
    _TEMPLATES = None
    _TEMPLATES_ERROR = (
        "fastapi.templating.Jinja2Templates is unavailable; install FastAPI with Jinja2"
    )
else:
    try:
        _TEMPLATES = Jinja2Templates(
            directory=str(Path(__file__).resolve().parent / "templates")
        )
    except AssertionError as exc:  # pragma: no cover - optional dependency guard
        _TEMPLATES = None
        _TEMPLATES_ERROR = str(exc)
    else:
        _TEMPLATES_ERROR = ""

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from fastapi.templating import Jinja2Templates as _TemplatesType
else:  # pragma: no cover - runtime fallback when typing is not evaluated
    _TemplatesType = Any  # type: ignore[misc,assignment]


def _get_templates() -> "_TemplatesType":
    if Jinja2Templates is None or _TEMPLATES is None:
        message = _TEMPLATES_ERROR or "Jinja2 templates backend is unavailable"
        raise RuntimeError(message)
    return _TEMPLATES


TEMPLATES = _TEMPLATES

router = APIRouter(prefix="/ui", tags=["ui"])


@router.get("/slots", name="ui:slots-index", response_class=HTMLResponse)
def slots_index(request: Request) -> Response:
    """Render the overview with static slot cards."""

    slots = mock_data.generate_slot_overview(count=6)
    context = {"request": request, "slots": slots}
    return _get_templates().TemplateResponse("slots/index.html", context)


@router.get("/slots/{slot_id}", name="ui:slot-detail", response_class=HTMLResponse)
def slot_detail(slot_id: str, request: Request) -> Response:
    """Show mock slot configuration and latest results."""

    slot = mock_data.generate_slot_detail(slot_id)
    context = {
        "request": request,
        "slot": slot,
        "recent_results": slot.recent_results,
    }
    return _get_templates().TemplateResponse("slots/detail.html", context)


@router.get("/stats", name="ui:stats-index", response_class=HTMLResponse)
def stats_index(request: Request) -> Response:
    """Display aggregated statistics with placeholder values."""

    summary, metrics = mock_data.generate_global_stats()
    context = {"request": request, "summary": summary, "metrics": metrics}
    return _get_templates().TemplateResponse("stats/index.html", context)


@router.get(
    "/results/{slot_id}", name="ui:results-gallery", response_class=HTMLResponse
)
def results_gallery(slot_id: str, request: Request) -> Response:
    """Render gallery view for a slot using mock results."""

    slot, results = mock_data.generate_gallery(slot_id)
    context = {"request": request, "slot": slot, "results": results}
    return _get_templates().TemplateResponse("results/gallery.html", context)


@router.get("/auth/login", name="ui:auth-login", response_class=HTMLResponse)
def login(request: Request) -> Response:
    """Render login page stub without calling the Auth API."""

    context = {"request": request}
    return _get_templates().TemplateResponse("auth/login.html", context)


__all__ = ["router"]
