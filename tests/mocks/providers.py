"""Deterministic provider mocks for contract and integration tests."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Mapping
from uuid import uuid4

from src.app.domain.models import Job, Slot
from src.app.providers.base import ProviderAdapter

CDN_BASE_URL = "https://cdn.photochanger.test"
TRANSPARENT_PNG_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/kwL7ZkAAAAASUVORK5CYII="
TRANSPARENT_PNG_BYTES = base64.b64decode(TRANSPARENT_PNG_BASE64)


class MockProviderScenario(str, Enum):
    """Available behaviours for provider mocks."""

    SUCCESS = "success"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass(slots=True)
class MockProviderState:
    """Internal state tracked for submitted jobs."""

    payload: Mapping[str, Any]
    polls: int = 0
    cancelled: bool = False
    completed: bool = False


@dataclass(slots=True)
class MockProviderConfig:
    """Common configuration shared by provider mocks."""

    scenario: MockProviderScenario = MockProviderScenario.SUCCESS
    timeout_polls: int = 3
    error_code: str = "PROVIDER_ERROR"
    error_message: str = "Simulated provider failure"

    def __post_init__(self) -> None:
        if not isinstance(
            self.scenario, MockProviderScenario
        ):  # pragma: no cover - runtime guard
            object.__setattr__(
                self, "scenario", MockProviderScenario(str(self.scenario))
            )
        if self.timeout_polls < 1:
            raise ValueError("timeout_polls must be at least 1")


def transparent_png_base64() -> str:
    """Return the deterministic 1×1 transparent PNG as base64."""

    return TRANSPARENT_PNG_BASE64


def make_cdn_url(reference: str) -> str:
    """Construct a deterministic CDN URL for the given reference."""

    safe_reference = reference.replace(" ", "-")
    return f"{CDN_BASE_URL}/{safe_reference}.png"


class MockGeminiProvider(ProviderAdapter):
    """Mock adapter emulating Gemini ``models.generateContent`` responses."""

    provider_id = "gemini"

    def __init__(self, config: MockProviderConfig | None = None) -> None:
        self.config = config or MockProviderConfig()
        self._state: Dict[str, MockProviderState] = {}
        self.events: list[str] = []

    def _record_event(self, event: str) -> None:
        self.events.append(event)

    def prepare_payload(
        self,
        *,
        job: Job,
        slot: Slot,
        settings: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        prompt = context.get("prompt") or f"Process job {job.id} for slot {slot.id}"
        payload = {
            "model": "gemini-2.5-flash-image",
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": transparent_png_base64(),
                            }
                        },
                    ],
                }
            ],
        }
        self._record_event(f"prepare:{job.id}")
        return payload

    async def submit_job(self, payload: Mapping[str, Any]) -> str:
        self._record_event("submit:attempt")
        if self.config.scenario == MockProviderScenario.ERROR:
            raise RuntimeError(
                f"Gemini error: code={self.config.error_code} message={self.config.error_message}"
            )
        reference = f"gemini-job-{uuid4()}"
        self._state[reference] = MockProviderState(payload=payload)
        self._record_event(f"submit:{reference}")
        return reference

    async def poll_status(self, reference: str) -> Mapping[str, Any]:
        if self.config.scenario == MockProviderScenario.ERROR:
            self._record_event(f"poll-error:{reference}")
            raise RuntimeError(
                f"Gemini error: code={self.config.error_code} message={self.config.error_message}"
            )
        state = self._state.get(reference)
        if state is None:
            raise KeyError(f"Unknown Gemini job reference: {reference}")
        state.polls += 1
        self._record_event(f"poll:{reference}:{state.polls}")
        if state.cancelled:
            raise RuntimeError("Gemini job cancelled")
        if self.config.scenario == MockProviderScenario.TIMEOUT:
            if state.polls <= self.config.timeout_polls:
                return {"status": "processing"}
            self._record_event(f"timeout:{reference}")
            raise TimeoutError("Gemini polling exceeded T_sync_response window")
        state.completed = True
        inline_data = {
            "mime_type": "image/png",
            "data": transparent_png_base64(),
        }
        candidate = {
            "finish_reason": "STOP",
            "content": {
                "role": "model",
                "parts": [
                    {"inline_data": inline_data},
                    {"text": f"mock-result:{reference}"},
                ],
            },
        }
        return {
            "status": "succeeded",
            "candidates": [candidate],
            "inline_data": inline_data,
        }

    async def cancel(self, reference: str) -> None:
        self._record_event(f"cancel:{reference}")
        state = self._state.get(reference)
        if state is None:
            return
        state.cancelled = True


class MockTurbotextProvider(ProviderAdapter):
    """Mock adapter emulating Turbotext queue and polling responses."""

    provider_id = "turbotext"

    def __init__(self, config: MockProviderConfig | None = None) -> None:
        self.config = config or MockProviderConfig()
        self._state: Dict[str, MockProviderState] = {}
        self.events: list[str] = []

    def _record_event(self, event: str) -> None:
        self.events.append(event)

    def prepare_payload(
        self,
        *,
        job: Job,
        slot: Slot,
        settings: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        prompt = context.get("prompt") or f"Render instructions for job {job.id}"
        source_url = context.get("source_image_url") or make_cdn_url(
            f"source-{job.id.hex}"
        )
        payload = {
            "do": "create_queue",
            "operation": slot.operation_id,
            "url": source_url,
            "content": prompt,
            "slot_id": slot.id,
        }
        self._record_event(f"prepare:{job.id}")
        return payload

    async def submit_job(self, payload: Mapping[str, Any]) -> str:
        self._record_event("submit:attempt")
        if self.config.scenario == MockProviderScenario.ERROR:
            raise RuntimeError(
                f"Turbotext error: code={self.config.error_code} message={self.config.error_message}"
            )
        reference = f"turbotext-queue-{uuid4()}"
        self._state[reference] = MockProviderState(payload=payload)
        self._record_event(f"submit:{reference}")
        return reference

    async def poll_status(self, reference: str) -> Mapping[str, Any]:
        if self.config.scenario == MockProviderScenario.ERROR:
            self._record_event(f"poll-error:{reference}")
            raise RuntimeError(
                f"Turbotext error: code={self.config.error_code} message={self.config.error_message}"
            )
        state = self._state.get(reference)
        if state is None:
            raise KeyError(f"Unknown Turbotext queue reference: {reference}")
        state.polls += 1
        self._record_event(f"poll:{reference}:{state.polls}")
        if state.cancelled:
            raise RuntimeError("Turbotext job cancelled")
        if self.config.scenario == MockProviderScenario.TIMEOUT:
            if state.polls <= self.config.timeout_polls:
                return {"action": "reconnect"}
            self._record_event(f"timeout:{reference}")
            raise TimeoutError("Turbotext polling exceeded T_sync_response window")
        state.completed = True
        payload = state.payload
        content = payload.get("content")
        uploaded_image = make_cdn_url(reference)
        data = {
            "queueid": reference,
            "uploaded_image": uploaded_image,
            "image": [f"image/{reference}.png"],
            "prompt": content,
        }
        return {"success": True, "data": data}

    async def cancel(self, reference: str) -> None:
        self._record_event(f"cancel:{reference}")
        state = self._state.get(reference)
        if state is None:
            return
        state.cancelled = True
