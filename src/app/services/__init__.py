"""Доменные сервисы PhotoChanger. Реализация подключается через плагины.

Контракты сервисов определяются сценариями из ``spec/docs/blueprints`` и
OpenAPI (`spec/contracts/openapi.yaml`). Пока пакет остаётся пустым
шаблоном для будущих реализаций.
"""

from .registry import ServiceRegistry

__all__ = ["ServiceRegistry"]
