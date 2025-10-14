"""Infrastructure adapters and repository contracts for PhotoChanger."""

from __future__ import annotations

from .job_repository import JobRepository
from .media_storage import MediaStorage
from .settings_repository import SettingsRepository
from .slot_repository import SlotRepository
from .stats_repository import StatsRepository
from .template_storage import TemplateStorage
from .unit_of_work import UnitOfWork

__all__ = [
    "JobRepository",
    "MediaStorage",
    "SettingsRepository",
    "SlotRepository",
    "StatsRepository",
    "TemplateStorage",
    "UnitOfWork",
]
