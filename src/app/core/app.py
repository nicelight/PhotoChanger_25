"""FastAPI application factory adhering to PhotoChanger contracts.

The app exposes routers generated from ``spec/contracts/openapi.yaml`` and
stores the :class:`~src.app.services.registry.ServiceRegistry` on the
application state for dependency resolution. Real dependency wiring is deferred
to implementation phases as described in the blueprints.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from ..api import ApiFacade
from ..services.registry import ServiceRegistry


def _read_contract_version() -> str:
    """Return the OpenAPI version declared in ``spec/contracts``."""

    version_file = (
        Path(__file__).resolve().parents[2] / "spec" / "contracts" / "VERSION.json"
    )
    try:
        data = json.loads(version_file.read_text(encoding="utf-8"))
    except FileNotFoundError:  # pragma: no cover - optional contract sync
        return "0.0.0"
    except json.JSONDecodeError:  # pragma: no cover - corrupted contract version
        return "0.0.0"
    return str(data.get("version", "0.0.0"))


def _configure_dependencies(registry: ServiceRegistry) -> None:
    """Register infrastructure adapters and domain services.

    The actual wiring to repositories, queues and providers will be added in
    implementation phases.  Keeping the explicit ``NotImplementedError``
    highlights the pending work and protects accidental usage.
    """

    raise NotImplementedError("Dependency wiring is provided in implementation phases")


def create_app(extra_state: dict[str, Any] | None = None) -> FastAPI:
    """Initialise a FastAPI application with generated routers."""

    registry = ServiceRegistry()
    try:
        _configure_dependencies(registry)
    except NotImplementedError:
        # Scaffolding keeps the registry empty; store it for future wiring.
        pass

    facade = ApiFacade(registry=registry)
    app = FastAPI(title="PhotoChanger API", version=_read_contract_version())
    app.state.service_registry = registry
    if extra_state:
        for key, value in extra_state.items():
            setattr(app.state, key, value)
    facade.mount(app)
    return app


__all__ = ["create_app"]
