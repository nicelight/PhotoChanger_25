"""Facade for mounting UI routes onto FastAPI or custom binders.

The scaffolding shares the :class:`~src.app.services.registry.ServiceRegistry`
with the API layer to keep dependency injection consistent across routers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from fastapi import APIRouter, FastAPI

from ..services.registry import ServiceRegistry


class RouterBinder(Protocol):
    """Protocol describing minimal router registration behaviour."""

    def include_router(self, router: APIRouter) -> None:
        """Register an ``APIRouter`` instance in a host application."""


@dataclass(slots=True)
class UiFacade:
    """Wires UI routers to FastAPI or an abstract binder."""

    registry: ServiceRegistry

    def mount(self, app: FastAPI) -> None:
        """Attach routers directly to a FastAPI application."""

        for router in self._iter_routers():
            app.include_router(router)

    def include_routers(self, binder: RouterBinder) -> None:
        """Register routers using an abstract binder."""

        for router in self._iter_routers():
            binder.include_router(router)

    @staticmethod
    def _iter_routers() -> Iterable[APIRouter]:
        """Yield UI routers available in this package."""

        from . import views

        return (views.router,)


__all__ = ["UiFacade", "RouterBinder"]
