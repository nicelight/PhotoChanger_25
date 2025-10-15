"""Smoke tests ensuring scaffolding wiring matches the contracts.

Validates that ``create_app`` registers the routers enumerated in
``spec/contracts/openapi.yaml`` even when dependencies are not wired yet.
"""

from __future__ import annotations

from typing import Iterable, Tuple

import pytest

pytestmark = pytest.mark.unit

try:  # pragma: no cover - optional dependency for scaffolding tests
    from fastapi import FastAPI
except ModuleNotFoundError:  # pragma: no cover - guard for environments without FastAPI
    pytest.skip(
        "FastAPI is not installed for scaffolding tests", allow_module_level=True
    )

from src.app.core.app import create_app  # noqa: E402
from src.app.services.registry import ServiceRegistry  # noqa: E402


def _collect_route_signatures(app: FastAPI) -> set[Tuple[str, str]]:
    """Return a set of (path, method) tuples for registered routes."""

    signatures: set[Tuple[str, str]] = set()
    for route in app.routes:
        methods: Iterable[str] = getattr(route, "methods", []) or []
        for method in methods:
            signatures.add((route.path, method.upper()))
    return signatures


def test_create_app_exposes_expected_routes() -> None:
    """The FastAPI factory should register scaffolding routers without deps."""

    app = create_app()
    assert isinstance(app, FastAPI)
    assert isinstance(app.state.service_registry, ServiceRegistry)

    signatures = _collect_route_signatures(app)

    expected = {
        ("/api/providers", "GET"),
        ("/api/slots", "GET"),
        ("/api/settings", "GET"),
        ("/ingest/{slotId}", "POST"),
        ("/public/results/{job_id}", "GET"),
    }
    for signature in expected:
        assert signature in signatures
