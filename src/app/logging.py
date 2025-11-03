"""Logging configuration for PhotoChanger."""

from __future__ import annotations

import logging

try:
    import structlog
except ModuleNotFoundError:  # pragma: no cover - fallback only triggered when structlog absent
    structlog = None  # type: ignore[assignment]


def configure_logging() -> None:
    """Configure logging (prefers structlog, falls back to stdlib)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if structlog is None:
        return

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
