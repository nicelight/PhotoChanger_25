"""HTTP-фасад, который должен соответствовать контракту из ``spec/contracts/openapi.yaml``.

Фасад объединяет сгенерированные стаб-роутеры и предоставляет удобные методы
подключения к FastAPI-приложению либо внешнему биндеру. В фазе scaffolding
обработчики отсутствуют — см. ``src/app/api/routes``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from fastapi import APIRouter, FastAPI

from ..services.registry import ServiceRegistry


class RouterBinder(Protocol):
    """Интерфейс адаптера веб-фреймворка для регистрации маршрутизаторов."""

    def include_router(self, router: APIRouter) -> None:
        """Регистрирует ``APIRouter`` в стороннем приложении."""


@dataclass(slots=True)
class ApiFacade:
    """Тонкий слой между HTTP-стеком и доменными сервисами."""

    registry: ServiceRegistry

    def mount(self, app: FastAPI) -> None:
        """Подключает все маршрутизаторы к экземпляру FastAPI."""

        if getattr(app.state, "service_registry", None) is None:
            app.state.service_registry = self.registry
        for router in self._iter_routers():
            app.include_router(router)

    def include_routers(self, binder: RouterBinder) -> None:
        """Регистрирует маршрутизаторы через абстрактный биндер."""

        for router in self._iter_routers():
            binder.include_router(router)

    @staticmethod
    def _iter_routers() -> Iterable[APIRouter]:
        """Возвращает стаб-роутеры, сгруппированные по разделам OpenAPI."""

        from .routes import (
            auth,
            ingest,
            jobs,
            media,
            providers,
            public,
            settings,
            slots,
            stats,
        )

        return (
            auth.router,
            providers.router,
            slots.router,
            settings.router,
            media.router,
            jobs.router,
            stats.router,
            ingest.router,
            public.router,
        )
