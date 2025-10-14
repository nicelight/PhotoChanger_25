"""Mock generators for UI scaffolding aligned with contracts."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Iterable, Sequence
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SlotViewModel(BaseModel):
    """Presentation-friendly slot mirroring :schema:`Slot` fields."""

    id: str = Field(..., description="Идентификатор статического ingest-слота")
    name: str = Field(..., description="Отображаемое имя слота")
    provider_id: str = Field(..., description="Идентификатор провайдера")
    provider_label: str = Field(..., description="Человекочитаемое имя провайдера")
    operation_id: str = Field(..., description="Идентификатор операции провайдера")
    operation_label: str = Field(..., description="Человекочитаемое имя операции")
    ingest_url: str = Field(
        ..., description="Публичная ingest-ссылка, которую UI строит по шаблону"
    )
    settings_json: dict[str, Any] = Field(
        default_factory=dict,
        description="Сериализованные настройки, возвращаемые Admin API",
    )
    created_at: datetime = Field(..., description="Момент создания слота")
    updated_at: datetime = Field(..., description="Момент последнего обновления")
    last_reset_at: datetime | None = Field(
        None, description="Метка последнего сброса статистики"
    )
    recent_results: list["ResultCard"] = Field(
        default_factory=list,
        description="Последние успешные результаты слота",
    )


class ResultCard(BaseModel):
    """Result representation matching :schema:`Result` with UI helpers."""

    job_id: UUID = Field(
        ..., description="Идентификатор Job, по которому получен результат"
    )
    thumbnail_url: str = Field(..., description="URL превью изображения")
    download_url: str = Field(..., description="Публичная ссылка на итоговый файл")
    completed_at: datetime | None = Field(None, description="Момент финализации задачи")
    result_expires_at: datetime | None = Field(
        None, description="Момент истечения TTL итогового файла"
    )
    mime: str = Field(..., description="MIME-тип итогового изображения")
    size_bytes: int | None = Field(
        None, ge=0, description="Размер итогового файла в байтах"
    )

    @property
    def is_expired(self) -> bool:
        """Return ``True`` if the download link is no longer valid."""

        if self.result_expires_at is None:
            return False
        return self.result_expires_at <= datetime.utcnow()


class GlobalStatsSummary(BaseModel):
    """Aggregated counters from :schema:`GlobalStatsResponse.summary`."""

    total_runs: int = Field(..., ge=0)
    timeouts: int = Field(..., ge=0)
    provider_errors: int = Field(..., ge=0)
    cancelled: int = Field(..., ge=0)
    errors: int = Field(..., ge=0)
    ingest_count: int = Field(..., ge=0)

    @property
    def successful_runs(self) -> int:
        """Return synthetic counter of successful jobs for the UI."""

        failures = self.timeouts + self.provider_errors + self.cancelled + self.errors
        return max(self.total_runs - failures, 0)


try:  # Pydantic v2
    SlotViewModel.model_rebuild()
except AttributeError:  # pragma: no cover - fallback for Pydantic v1
    SlotViewModel.update_forward_refs(ResultCard=ResultCard)  # type: ignore[attr-defined]


class DailyStatsMetric(BaseModel):
    """Time-series point compatible with :schema:`GlobalStatsMetric`."""

    period_start: date = Field(..., description="Дата начала периода агрегирования")
    period_end: date = Field(..., description="Дата окончания периода агрегирования")
    success: int = Field(..., ge=0)
    timeouts: int = Field(..., ge=0)
    provider_errors: int = Field(..., ge=0)
    cancelled: int = Field(..., ge=0)
    errors: int = Field(..., ge=0)
    ingest_count: int = Field(..., ge=0)


_PLACEHOLDER_THUMBNAILS: Sequence[str] = (
    "https://placehold.co/320x240/png",
    "https://placehold.co/320x240/jpg",
    "https://placehold.co/320x240/webp",
)


def generate_slot_overview(count: int = 3) -> list[SlotViewModel]:
    """Create a list of fake slots for the index page."""

    now = datetime.utcnow()
    slots: list[SlotViewModel] = []
    for index in range(1, count + 1):
        slot_id = f"slot-{index:03d}"
        slots.append(
            SlotViewModel(
                id=slot_id,
                name=f"Demo слот {index:02d}",
                provider_id="gemini" if index % 2 else "turbotext",
                provider_label="Gemini" if index % 2 else "Turbotext",
                operation_id="style_transfer" if index % 2 else "identity_transfer",
                operation_label="Style transfer" if index % 2 else "Identity transfer",
                ingest_url=f"https://ui.example.test/ingest/{slot_id}",
                settings_json={"prompt": "Demo prompt", "style": "studio"},
                created_at=now - timedelta(days=14 + index),
                updated_at=now - timedelta(hours=index * 4),
                last_reset_at=now - timedelta(days=7),
            )
        )
    return slots


def generate_slot_detail(slot_id: str) -> SlotViewModel:
    """Return mock slot metadata together with last processed results."""

    now = datetime.utcnow()
    slot = SlotViewModel(
        id=slot_id,
        name=f"Demo слот {slot_id.split('-')[-1]}",
        provider_id="gemini",
        provider_label="Gemini Advanced",
        operation_id="style_transfer",
        operation_label="Portrait stylization",
        ingest_url=f"https://ui.example.test/ingest/{slot_id}",
        settings_json={
            "prompt": "Сделать профессиональный портрет в корпоративном стиле",
            "template_media": [
                {
                    "id": "template-portrait",
                    "mime": "image/png",
                }
            ],
            "scheduler": {
                "deadline_seconds": 45,
            },
        },
        created_at=now - timedelta(days=21),
        updated_at=now - timedelta(hours=6),
        last_reset_at=now - timedelta(days=3),
        recent_results=list(_generate_results(limit=6)),
    )
    return slot


def generate_gallery(slot_id: str) -> tuple[SlotViewModel, list[ResultCard]]:
    """Prepare gallery context for a given slot id."""

    slot = generate_slot_detail(slot_id)
    return slot, slot.recent_results


def generate_global_stats() -> tuple[GlobalStatsSummary, list[DailyStatsMetric]]:
    """Produce aggregate statistics and daily points for the dashboard."""

    summary = GlobalStatsSummary(
        total_runs=240,
        timeouts=12,
        provider_errors=9,
        cancelled=6,
        errors=3,
        ingest_count=240,
    )
    today = date.today()
    metrics = [
        DailyStatsMetric(
            period_start=today - timedelta(days=offset + 1),
            period_end=today - timedelta(days=offset),
            success=max(0, 32 - offset * 2),
            timeouts=offset % 3,
            provider_errors=offset % 2,
            cancelled=1 if offset % 4 == 0 else 0,
            errors=1 if offset % 5 == 0 else 0,
            ingest_count=32,
        )
        for offset in range(0, 7)
    ]
    metrics.reverse()
    return summary, metrics


def _generate_results(limit: int) -> Iterable[ResultCard]:
    """Internal helper producing deterministic result cards."""

    base_time = datetime.utcnow()
    for index in range(limit):
        completed = base_time - timedelta(hours=index * 3)
        expires = completed + timedelta(hours=72)
        yield ResultCard(
            job_id=uuid4(),
            thumbnail_url=_PLACEHOLDER_THUMBNAILS[index % len(_PLACEHOLDER_THUMBNAILS)],
            download_url="https://public.example.test/results/demo",
            completed_at=completed,
            result_expires_at=expires,
            mime="image/png",
            size_bytes=1_024_000,
        )
