"""Тонкий HTTP-фасад, соответствующий спецификации ``spec/contracts/openapi.yaml``.

Фасад регистрирует маршруты поверх конкретного веб-фреймворка и делегирует
реализацию доменным сервисам через ``ServiceRegistry``.
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
        """Привязывает обработчики из доменных сервисов к веб-фреймворку.

        Конкретные обработчики должны соответствовать контрактам из
        ``spec/contracts/openapi.yaml`` и использовать сериализацию,
        описанную в схемах ``spec/contracts/schemas``.
        """

        del binder  # пока нет реализации
        # TODO: Реализовать после генерации стаба контроллеров.
