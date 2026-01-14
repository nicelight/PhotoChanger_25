"""FastAPI application entry point."""

import logging

from fastapi import FastAPI

from .config import AppConfig, load_config
from .dependencies import include_routers
from .logging import configure_logging


def create_app(config: AppConfig | None = None) -> FastAPI:
    """Build FastAPI instance with configured dependencies."""
    configure_logging()
    cfg = config or load_config()
    app = FastAPI(title="PhotoChanger")
    include_routers(app, cfg)
    logger = logging.getLogger(__name__)
    dashboard_url = "http://127.0.0.1:8000/ui/static/admin/dashboard.html"
    logger.info("admin.dashboard_url=%s", dashboard_url)
    return app


app = create_app()
