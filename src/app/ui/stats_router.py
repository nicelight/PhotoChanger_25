"""Serve static statistics dashboard."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse


router = APIRouter(tags=["ui"], include_in_schema=False)

FRONTEND_ROOT = Path(__file__).resolve().parents[3] / "frontend"
STATS_DIR = FRONTEND_ROOT / "stats"
STATS_HTML = STATS_DIR / "index.html"


@router.get("/ui/stats", response_class=HTMLResponse, include_in_schema=False)
def render_stats_page() -> HTMLResponse:
    """Return pre-built stats dashboard."""
    if not STATS_HTML.exists():
        raise HTTPException(status_code=404, detail="Stats UI is not available")
    return HTMLResponse(STATS_HTML.read_text(encoding="utf-8"))
