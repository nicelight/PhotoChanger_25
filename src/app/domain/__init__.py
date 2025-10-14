"""Доменные модели и правила платформы PhotoChanger.

Реализации должны отражать сущности и инварианты из
``spec/docs/blueprints/domain-model.md`` и удовлетворять критериям приёмки
из ``spec/docs/blueprints/acceptance-criteria.md``.
"""

from .deadlines import (
    calculate_artifact_expiry,
    calculate_deadline_info,
    calculate_job_expires_at,
    calculate_result_expires_at,
)
from .models import (
    Job,
    JobDeadline,
    JobFailureReason,
    JobMetrics,
    JobStatus,
    MediaCacheSettings,
    MediaObject,
    ProcessingLog,
    ProcessingStatus,
    Settings,
    SettingsDslrPasswordStatus,
    SettingsIngestConfig,
    SettingsProviderKeyStatus,
    Slot,
    SlotRecentResult,
    TemplateMedia,
)

__all__ = [
    "Job",
    "JobDeadline",
    "JobFailureReason",
    "JobMetrics",
    "JobStatus",
    "calculate_artifact_expiry",
    "calculate_deadline_info",
    "calculate_job_expires_at",
    "calculate_result_expires_at",
    "MediaCacheSettings",
    "MediaObject",
    "ProcessingLog",
    "ProcessingStatus",
    "Settings",
    "SettingsDslrPasswordStatus",
    "SettingsIngestConfig",
    "SettingsProviderKeyStatus",
    "Slot",
    "SlotRecentResult",
    "TemplateMedia",
]
