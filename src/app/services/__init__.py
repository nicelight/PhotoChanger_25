"""Доменные сервисы PhotoChanger.

На этой фазе определяются только интерфейсы без бизнес-логики. Реализации
подключаются через плагины согласно ``spec/docs/blueprints`` и контрактам из
``spec/contracts``.
"""

from .job_service import JobService
from .media_service import MediaService
from .registry import ServiceRegistry
from .settings_service import SettingsService
from .slot_service import SlotService
from .slots import SlotManagementService, SlotValidationError
from .stats import CachedStatsService
from .stats_service import StatsService

__all__ = [
    "JobService",
    "MediaService",
    "ServiceRegistry",
    "SettingsService",
    "SlotService",
    "SlotManagementService",
    "SlotValidationError",
    "CachedStatsService",
    "StatsService",
]
