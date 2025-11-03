"""FastAPI application entry point."""

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
    return app


app = create_app()
