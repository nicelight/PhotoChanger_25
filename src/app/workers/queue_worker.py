"""Queue worker coordinating provider dispatch and result persistence."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from ..domain import deadlines
from ..domain.models import (
    Job,
    JobFailureReason,
    MediaObject,
    ProcessingLog,
    ProcessingStatus,
    Settings,
    Slot,
)
from ..plugins.base import PluginFactory
from ..providers.base import ProviderAdapter
from ..services import (
    JobService,
    MediaService,
    SettingsService,
    SlotService,
    StatsService,
)


class ProviderDispatchOutcome(str, Enum):
    """High-level result of dispatching a job to a provider."""

    SUCCESS = "success"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass(slots=True)
class ProviderDispatchResult:
    """Container returned by :meth:`QueueWorker.dispatch_to_provider`."""

    outcome: ProviderDispatchOutcome
    provider_reference: str | None
    response: Mapping[str, Any] | None
    finished_at: datetime | None
    error: Exception | None = None


class QueueWorker:
    """Coordinates picking jobs, dispatching to providers and persisting results."""

    def __init__(
        self,
        *,
        job_service: JobService,
        slot_service: SlotService,
        media_service: MediaService,
        settings_service: SettingsService,
        stats_service: StatsService,
        provider_factories: Mapping[str, PluginFactory],
        provider_configs: Mapping[str, Mapping[str, Any]] | None = None,
        clock: Callable[[], datetime] | None = None,
        sleep: Callable[[float], None] | None = None,
        poll_interval: float = 1.0,
        max_poll_attempts: int = 10,
    ) -> None:
        self.job_service = job_service
        self.slot_service = slot_service
        self.media_service = media_service
        self.settings_service = settings_service
        self.stats_service = stats_service
        self._provider_factories = dict(provider_factories)
        self._provider_configs = dict(provider_configs or {})
        self._providers: dict[str, ProviderAdapter] = {}
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._sleep = sleep or time.sleep
        self._poll_interval = poll_interval
        self._max_poll_attempts = max_poll_attempts
        self._logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # High-level control flow
    # ------------------------------------------------------------------
    def run_once(self, *, now: datetime) -> None:
        """Pick and process at most one job within the ``T_sync_response`` window."""

        job = self.job_service.acquire_next_job(now=now)
        if job is None:
            return
        if now >= job.expires_at:
            self.handle_timeout(job, now=now)
            return
        self.process_job(job, now=now)

    def process_job(self, job: Job, *, now: datetime) -> None:
        """Execute provider-specific logic while respecting queue deadlines."""

        slot = self.slot_service.get_slot(job.slot_id)
        settings = self.settings_service.read_settings()
        context = self._load_job_context(job)
        dispatch_result = self.dispatch_to_provider(
            job,
            slot=slot,
            settings=settings,
            context=context,
            started_at=now,
        )

        if dispatch_result.outcome is ProviderDispatchOutcome.SUCCESS:
            finalized_at = dispatch_result.finished_at or self._clock()
            inline_preview, result_media = self._materialize_provider_result(
                job=job,
                slot=slot,
                provider_id=slot.provider_id,
                response=dispatch_result.response or {},
                finalized_at=finalized_at,
                settings=settings,
            )
            self.job_service.finalize_job(
                job,
                finalized_at=finalized_at,
                result_media=result_media,
                inline_preview=inline_preview,
            )
            return

        occurred_at = dispatch_result.finished_at or self._clock()
        failure_reason = (
            JobFailureReason.TIMEOUT
            if dispatch_result.outcome is ProviderDispatchOutcome.TIMEOUT
            else JobFailureReason.PROVIDER_ERROR
        )
        self.job_service.fail_job(
            job,
            failure_reason=failure_reason,
            occurred_at=occurred_at,
        )

    def handle_timeout(self, job: Job, *, now: datetime) -> None:
        """Mark the job as timed out when ``now`` exceeds ``job.expires_at``."""

        slot = self.slot_service.get_slot(job.slot_id)
        self.job_service.fail_job(
            job,
            failure_reason=JobFailureReason.TIMEOUT,
            occurred_at=now,
        )
        log_entry = self._build_processing_log(
            job,
            slot,
            status=ProcessingStatus.TIMEOUT,
            occurred_at=now,
            started_at=now,
            message="Job expired before dispatch",
        )
        self.job_service.append_processing_logs(job, [log_entry])
        self._record_processing_logs([log_entry])

    # ------------------------------------------------------------------
    # Provider dispatch lifecycle
    # ------------------------------------------------------------------
    def dispatch_to_provider(
        self,
        job: Job,
        *,
        slot: Slot,
        settings: Settings,
        context: Mapping[str, Any],
        started_at: datetime,
    ) -> ProviderDispatchResult:
        """Delegate processing to the configured provider adapter."""

        provider = self._get_or_create_provider(slot.provider_id)
        provider_settings = self._provider_settings_for(slot.provider_id, settings)
        logs: list[ProcessingLog] = [
            self._build_processing_log(
                job,
                slot,
                status=ProcessingStatus.RECEIVED,
                occurred_at=started_at,
                started_at=started_at,
                message="Job received for processing",
                details={"provider_id": slot.provider_id},
            )
        ]

        try:
            payload = provider.prepare_payload(
                job=job,
                slot=slot,
                settings=provider_settings,
                context=context,
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            error_time = self._clock()
            self._logger.exception("Provider payload preparation failed", exc_info=exc)
            logs.append(
                self._build_processing_log(
                    job,
                    slot,
                    status=ProcessingStatus.FAILED,
                    occurred_at=error_time,
                    started_at=started_at,
                    message=str(exc),
                    details={"error": repr(exc)},
                )
            )
            self.job_service.append_processing_logs(job, logs)
            self._record_processing_logs(logs)
            return ProviderDispatchResult(
                outcome=ProviderDispatchOutcome.ERROR,
                provider_reference=None,
                response=None,
                finished_at=error_time,
                error=exc,
            )

        dispatched_at = self._clock()
        logs.append(
            self._build_processing_log(
                job,
                slot,
                status=ProcessingStatus.DISPATCHED,
                occurred_at=dispatched_at,
                started_at=started_at,
                message="Submitted payload to provider",
                details={"provider_id": slot.provider_id},
            )
        )

        try:
            reference = asyncio.run(provider.submit_job(payload))
        except Exception as exc:
            failure_time = self._clock()
            self._logger.exception("Provider submission failed", exc_info=exc)
            logs.append(
                self._build_processing_log(
                    job,
                    slot,
                    status=ProcessingStatus.FAILED,
                    occurred_at=failure_time,
                    started_at=started_at,
                    message=str(exc),
                    details={"error": repr(exc)},
                )
            )
            self.job_service.append_processing_logs(job, logs)
            self._record_processing_logs(logs)
            return ProviderDispatchResult(
                outcome=ProviderDispatchOutcome.ERROR,
                provider_reference=None,
                response=None,
                finished_at=failure_time,
                error=exc,
            )

        job.provider_job_reference = reference
        response: Mapping[str, Any] | None = None
        error: Exception | None = None
        outcome = ProviderDispatchOutcome.ERROR
        finished_at: datetime | None = None

        for attempt in range(1, self._max_poll_attempts + 1):
            now = self._clock()
            if now >= job.expires_at:
                error = TimeoutError("Job deadline reached before provider completion")
                outcome = ProviderDispatchOutcome.TIMEOUT
                finished_at = now
                break
            try:
                response = asyncio.run(provider.poll_status(reference))
            except TimeoutError as exc:
                error = exc
                outcome = ProviderDispatchOutcome.TIMEOUT
                finished_at = now
                break
            except Exception as exc:  # pragma: no cover - defensive guard
                error = exc
                outcome = ProviderDispatchOutcome.ERROR
                finished_at = now
                break

            status = self._classify_provider_response(slot.provider_id, response)
            if status == "success":
                finished_at = now
                logs.append(
                    self._build_processing_log(
                        job,
                        slot,
                        status=ProcessingStatus.PROVIDER_RESPONDED,
                        occurred_at=now,
                        started_at=started_at,
                        details={"attempt": attempt},
                    )
                )
                outcome = ProviderDispatchOutcome.SUCCESS
                break
            if status == "pending":
                self._sleep(self._poll_interval)
                continue

            error = RuntimeError(
                f"Provider {slot.provider_id} returned unsuccessful status"
            )
            outcome = ProviderDispatchOutcome.ERROR
            finished_at = now
            break
        else:
            error = TimeoutError("Provider polling exceeded allowed attempts")
            outcome = ProviderDispatchOutcome.TIMEOUT
            finished_at = self._clock()

        if outcome is ProviderDispatchOutcome.TIMEOUT:
            try:
                asyncio.run(provider.cancel(reference))
            except Exception as cancel_error:  # pragma: no cover - best effort logging
                self._logger.warning(
                    "Provider cancellation raised an exception", exc_info=cancel_error
                )
            logs.append(
                self._build_processing_log(
                    job,
                    slot,
                    status=ProcessingStatus.TIMEOUT,
                    occurred_at=finished_at,
                    started_at=started_at,
                    message=(str(error) if error else None),
                    details={"provider_id": slot.provider_id},
                )
            )
        elif outcome is ProviderDispatchOutcome.SUCCESS:
            logs.append(
                self._build_processing_log(
                    job,
                    slot,
                    status=ProcessingStatus.SUCCEEDED,
                    occurred_at=finished_at,
                    started_at=started_at,
                    details={"provider_id": slot.provider_id},
                )
            )
        else:
            logs.append(
                self._build_processing_log(
                    job,
                    slot,
                    status=ProcessingStatus.FAILED,
                    occurred_at=finished_at,
                    started_at=started_at,
                    message=(str(error) if error else None),
                    details={
                        "provider_id": slot.provider_id,
                        "error": repr(error) if error else None,
                    },
                )
            )

        self.job_service.append_processing_logs(job, logs)
        self._record_processing_logs(logs)

        return ProviderDispatchResult(
            outcome=outcome,
            provider_reference=reference,
            response=response,
            finished_at=finished_at,
            error=error,
        )

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
    def _get_or_create_provider(self, provider_id: str) -> ProviderAdapter:
        try:
            return self._providers[provider_id]
        except KeyError:
            factory = self._provider_factories.get(provider_id)
            if factory is None:
                raise LookupError(f"Provider {provider_id!r} is not registered")
            config = self._provider_configs.get(provider_id)
            instance = factory(config=config)  # type: ignore[arg-type]
            if not isinstance(instance, ProviderAdapter):
                raise TypeError(
                    f"Factory for provider {provider_id!r} returned unexpected type"
                )
            self._providers[provider_id] = instance
            return instance

    def _provider_settings_for(
        self, provider_id: str, settings: Settings
    ) -> Mapping[str, Any]:
        status = settings.provider_keys.get(provider_id)
        if status is None:
            return {}
        provider_settings: dict[str, Any] = {
            "is_configured": status.is_configured,
        }
        provider_settings.update(dict(status.extra))
        if status.updated_at is not None:
            provider_settings["updated_at"] = status.updated_at.isoformat()
        if status.updated_by is not None:
            provider_settings["updated_by"] = status.updated_by
        return provider_settings

    def _build_processing_log(
        self,
        job: Job,
        slot: Slot,
        *,
        status: ProcessingStatus,
        occurred_at: datetime | None,
        started_at: datetime,
        message: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> ProcessingLog:
        occurred_at = occurred_at or self._clock()
        latency_ms = max(
            int((occurred_at - started_at).total_seconds() * 1000),
            0,
        )
        details_mutable = dict(details) if details is not None else None
        return ProcessingLog(
            id=uuid4(),
            job_id=job.id,
            slot_id=slot.id,
            status=status,
            occurred_at=occurred_at,
            message=message,
            details=details_mutable,
            provider_latency_ms=latency_ms,
        )

    def _record_processing_logs(self, logs: list[ProcessingLog]) -> None:
        for log in logs:
            try:
                self.stats_service.record_processing_event(log)
            except NotImplementedError:  # pragma: no cover - optional override
                continue

    def _load_job_context(self, job: Job) -> Mapping[str, Any]:
        if job.payload_path is None:
            return {}
        try:
            with open(job.payload_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            self._logger.warning(
                "Failed to decode payload JSON for job %s: %s", job.id, exc
            )
            return {}
        if not isinstance(data, Mapping):
            return {}
        context = data.get("provider_context") or data.get("context") or {}
        if isinstance(context, Mapping):
            return dict(context)
        return {}

    def _materialize_provider_result(
        self,
        *,
        job: Job,
        slot: Slot,
        provider_id: str,
        response: Mapping[str, Any],
        finalized_at: datetime,
        settings: Settings,
    ) -> tuple[str | None, MediaObject | None]:
        inline_preview: str | None = None
        media_object: MediaObject | None = None

        inline_data = response.get("inline_data")
        if isinstance(inline_data, Mapping):
            inline_preview = inline_data.get("data")  # type: ignore[assignment]
            mime = inline_data.get("mime_type")
            if mime is not None:
                job.result_mime_type = str(mime)

        if inline_preview is None:
            candidate = response.get("candidates")
            if isinstance(candidate, list) and candidate:
                first = candidate[0]
                if isinstance(first, Mapping):
                    content = first.get("content")
                    if isinstance(content, Mapping):
                        parts = content.get("parts")
                        if isinstance(parts, list) and parts:
                            part = parts[0]
                            if isinstance(part, Mapping) and "data" in part:
                                inline_preview = part.get("data")  # type: ignore[assignment]
                                mime = part.get("mime_type")
                                if mime is not None:
                                    job.result_mime_type = str(mime)

        if provider_id == "turbotext":
            data = response.get("data")
            if isinstance(data, Mapping):
                uploaded_image = data.get("uploaded_image")
                if uploaded_image:
                    expires_at = deadlines.calculate_artifact_expiry(
                        artifact_created_at=finalized_at,
                        job_expires_at=job.expires_at,
                        ttl_seconds=settings.media_cache.public_link_ttl_sec,
                    )
                    media_object = self.media_service.register_media(
                        path=str(uploaded_image),
                        mime=str(data.get("mime", job.result_mime_type or "image/png")),
                        size_bytes=int(data.get("size_bytes", 0)),
                        expires_at=expires_at,
                        job_id=job.id,
                    )

        return inline_preview, media_object

    def _classify_provider_response(
        self, provider_id: str, response: Mapping[str, Any]
    ) -> str:
        if provider_id == "gemini":
            status = response.get("status")
            if status == "succeeded":
                return "success"
            if status in {"processing", "running"}:
                return "pending"
            return "failure"
        if provider_id == "turbotext":
            if response.get("success") is True:
                return "success"
            action = response.get("action")
            if action == "reconnect":
                return "pending"
            return "failure"

        status = response.get("status")
        if status in {"success", "succeeded"}:
            return "success"
        if status in {"processing", "pending", "running"}:
            return "pending"
        return "failure"
