"""Базовая инфраструктура приложения (конфиги, логирование, DI).

Содержимое модуля должно соотноситься с ограничениями из
``spec/docs/blueprints/context.md`` и нефункциональными требованиями из
``spec/docs/blueprints/nfr.md``. Файл остаётся шаблоном до появления
конкретной реализации.
"""

try:
    from .config import AppConfig
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
    if exc.name != "pydantic":
        raise
    AppConfig = None  # type: ignore[assignment]
from .ui_config import (
    ProviderConfigEntry,
    ProviderOperationConfig,
    load_provider_catalog,
)

__all__ = [
    "AppConfig",
    "ProviderConfigEntry",
    "ProviderOperationConfig",
    "load_provider_catalog",
]
