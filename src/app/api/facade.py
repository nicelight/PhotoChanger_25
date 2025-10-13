"""HTTP-фасад, который должен соответствовать контракту из ``spec/contracts/openapi.yaml``.

Шаблон фиксирует структуру точек расширения для будущей реализации. Реальные
обработчики обязаны учитывать доменную семантику, описанную в
``spec/docs/blueprints`` (слоты, шаблонные медиа, ingest). Фасад остаётся
тонким: он делегирует работу в доменные сервисы, которые извлекаются из
``ServiceRegistry``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from ..services.registry import ServiceRegistry


class RouteBinder(Protocol):
    """Интерфейс адаптера веб-фреймворка для регистрации маршрутов."""

    def add_route(self, path: str, method: str, handler: Callable[..., object]) -> None:
        """Регистрирует обработчик HTTP-метода для пути."""


@dataclass(slots=True)
class ApiFacade:
    """Тонкий слой между HTTP-стеком и доменными сервисами."""

    registry: ServiceRegistry

    def bind(self, binder: RouteBinder) -> None:
        """Привязывает обработчики API к веб-фреймворку.

        Каждый вспомогательный метод отвечает за отдельный раздел OpenAPI:

        * ``_bind_slot_routes`` — CRUD слотов и ingest (`#/paths/~1api~1slots`).
        * ``_bind_template_media_routes`` — операции над шаблонными медиа
          (`#/paths/~1api~1template-media`).
        * ``_bind_public_routes`` — публичные загрузки и статические ресурсы
          (`#/paths/~1public`).

        Шаблонные методы ниже намеренно выбрасывают ``NotImplementedError``.
        Это сигнал интеграторам, что необходимо сгенерировать реальные
        обработчики по спецификациям.
        """

        self._bind_slot_routes(binder)
        self._bind_template_media_routes(binder)
        self._bind_public_routes(binder)

    def _bind_slot_routes(self, binder: RouteBinder) -> None:  # noqa: D401
        """Настроить маршруты управления слотами согласно OpenAPI."""

        _ = binder  # placeholder to silence linters
        raise NotImplementedError(
            "Сгенерируйте обработчики слотов из spec/contracts/openapi.yaml"
        )

    def _bind_template_media_routes(self, binder: RouteBinder) -> None:  # noqa: D401
        """Настроить маршруты управления шаблонными медиа."""

        _ = binder
        raise NotImplementedError(
            "Сгенерируйте обработчики шаблонов из spec/contracts/openapi.yaml"
        )

    def _bind_public_routes(self, binder: RouteBinder) -> None:  # noqa: D401
        """Настроить публичные маршруты скачивания медиа."""

        _ = binder
        raise NotImplementedError(
            "Сгенерируйте публичные обработчики из spec/contracts/openapi.yaml"
        )
