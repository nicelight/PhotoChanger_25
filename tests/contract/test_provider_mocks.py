"""Contract tests that validate deterministic behaviours of provider mocks."""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Mapping
from uuid import uuid4

import pytest

from src.app.domain.models import Job, JobStatus, Slot

from tests.mocks.providers import (
    MockGeminiProvider,
    MockProviderConfig,
    MockProviderScenario,
    MockTurbotextProvider,
    TRANSPARENT_PNG_BASE64,
    TRANSPARENT_PNG_BYTES,
    make_cdn_url,
)

BASE_TIME = datetime(2025, 10, 18, 12, 0, tzinfo=timezone.utc)


def _build_job(*, slot_id: str) -> Job:
    return Job(
        id=uuid4(),
        slot_id=slot_id,
        status=JobStatus.PENDING,
        is_finalized=False,
        failure_reason=None,
        expires_at=BASE_TIME + timedelta(seconds=90),
        created_at=BASE_TIME,
        updated_at=BASE_TIME,
        finalized_at=None,
    )


def _build_slot(*, provider_id: str, operation_id: str) -> Slot:
    return Slot(
        id="slot-001",
        name=f"{provider_id}-slot",
        provider_id=provider_id,
        operation_id=operation_id,
        settings_json={},
        created_at=BASE_TIME,
        updated_at=BASE_TIME,
    )


def _build_context(provider_id: str) -> Mapping[str, Any]:
    if provider_id == "turbotext":
        return {
            "prompt": "Enhance the portrait",
            "source_image_url": make_cdn_url("source-portrait"),
        }
    return {"prompt": "Compose a studio portrait"}


def _submit(
    provider: MockGeminiProvider | MockTurbotextProvider,
    payload: Mapping[str, Any],
) -> str:
    return asyncio.run(provider.submit_job(payload))


def _poll(
    provider: MockGeminiProvider | MockTurbotextProvider,
    reference: str,
) -> Mapping[str, Any]:
    return asyncio.run(provider.poll_status(reference))


def _cancel(
    provider: MockGeminiProvider | MockTurbotextProvider, reference: str
) -> None:
    asyncio.run(provider.cancel(reference))


@pytest.mark.contract
def test_gemini_success_returns_png() -> None:
    provider = MockGeminiProvider(
        MockProviderConfig(
            scenario=MockProviderScenario.SUCCESS,
            timeout_polls=2,
            error_code="RESOURCE_EXHAUSTED",
            error_message="Quota exceeded for mock Gemini project",
        )
    )
    slot = _build_slot(provider_id="gemini", operation_id="models.generateContent")
    job = _build_job(slot_id=slot.id)
    payload = provider.prepare_payload(
        job=job, slot=slot, settings={}, context=_build_context("gemini")
    )

    reference = _submit(provider, payload)
    response = _poll(provider, reference)

    assert response["status"] == "succeeded"
    inline_data_top = response["inline_data"]
    assert inline_data_top["mime_type"] == "image/png"
    assert inline_data_top["data"] == TRANSPARENT_PNG_BASE64
    candidate = response["candidates"][0]
    inline_data = candidate["content"]["parts"][0]
    assert inline_data["mime_type"] == "image/png"
    assert inline_data["data"] == TRANSPARENT_PNG_BASE64
    png_bytes = base64.b64decode(inline_data["data"])
    assert png_bytes == TRANSPARENT_PNG_BYTES
    assert provider.events[:4] == [
        f"prepare:{job.id}",
        "submit:attempt",
        f"submit:{reference}",
        f"poll:{reference}:1",
    ]


@pytest.mark.contract
def test_gemini_timeout_transitions_to_timeout_error() -> None:
    provider = MockGeminiProvider(
        MockProviderConfig(
            scenario=MockProviderScenario.TIMEOUT,
            timeout_polls=2,
            error_code="RESOURCE_EXHAUSTED",
            error_message="Quota exceeded for mock Gemini project",
        )
    )
    slot = _build_slot(provider_id="gemini", operation_id="models.generateContent")
    job = _build_job(slot_id=slot.id)
    payload = provider.prepare_payload(
        job=job, slot=slot, settings={}, context=_build_context("gemini")
    )

    reference = _submit(provider, payload)
    assert _poll(provider, reference) == {"status": "processing"}
    assert _poll(provider, reference) == {"status": "processing"}
    with pytest.raises(TimeoutError, match="T_sync_response"):
        _poll(provider, reference)
    assert any(event.startswith("timeout:") for event in provider.events)


@pytest.mark.contract
def test_gemini_error_surfaces_runtime_error() -> None:
    provider = MockGeminiProvider(
        MockProviderConfig(
            scenario=MockProviderScenario.ERROR,
            error_code="RESOURCE_EXHAUSTED",
            error_message="Quota exceeded for mock Gemini project",
        )
    )
    with pytest.raises(RuntimeError, match="code=RESOURCE_EXHAUSTED"):
        _submit(provider, {})
    with pytest.raises(RuntimeError, match="code=RESOURCE_EXHAUSTED"):
        _poll(provider, "gemini-job-deadbeef")


@pytest.mark.contract
def test_turbotext_success_returns_uploaded_image(
    validate_with_schema: Callable[[Dict[str, Any], str], None],
) -> None:
    provider = MockTurbotextProvider(
        MockProviderConfig(
            scenario=MockProviderScenario.SUCCESS,
            timeout_polls=2,
            error_code="INVALID_IMAGE_FORMAT",
            error_message="Unsupported image format supplied to mock Turbotext",
        )
    )
    slot = _build_slot(provider_id="turbotext", operation_id="generate_image2image")
    job = _build_job(slot_id=slot.id)
    context = _build_context("turbotext")
    payload = provider.prepare_payload(job=job, slot=slot, settings={}, context=context)

    assert payload["do"] == "create_queue"
    assert payload["url"] == context["source_image_url"]

    reference = _submit(provider, payload)
    response = _poll(provider, reference)

    assert response["success"] is True
    uploaded = response["data"]["uploaded_image"]
    assert uploaded == make_cdn_url(reference)

    media_payload = {
        "id": str(uuid4()),
        "public_url": uploaded,
        "expires_at": BASE_TIME.isoformat().replace("+00:00", "Z"),
        "mime": "image/png",
        "size_bytes": 512,
        "job_id": str(job.id),
    }
    validate_with_schema(media_payload, "MediaObject.json")


@pytest.mark.contract
def test_turbotext_timeout_raises_after_reconnects() -> None:
    provider = MockTurbotextProvider(
        MockProviderConfig(
            scenario=MockProviderScenario.TIMEOUT,
            timeout_polls=2,
            error_code="INVALID_IMAGE_FORMAT",
            error_message="Unsupported image format supplied to mock Turbotext",
        )
    )
    slot = _build_slot(provider_id="turbotext", operation_id="generate_image2image")
    job = _build_job(slot_id=slot.id)
    payload = provider.prepare_payload(
        job=job, slot=slot, settings={}, context=_build_context("turbotext")
    )

    reference = _submit(provider, payload)
    assert _poll(provider, reference) == {"action": "reconnect"}
    assert _poll(provider, reference) == {"action": "reconnect"}
    with pytest.raises(TimeoutError, match="T_sync_response"):
        _poll(provider, reference)
    assert any(event.startswith("timeout:") for event in provider.events)


@pytest.mark.contract
def test_turbotext_error_surfaces_runtime_error() -> None:
    provider = MockTurbotextProvider(
        MockProviderConfig(
            scenario=MockProviderScenario.ERROR,
            error_code="INVALID_IMAGE_FORMAT",
            error_message="Unsupported image format supplied to mock Turbotext",
        )
    )
    with pytest.raises(RuntimeError, match="code=INVALID_IMAGE_FORMAT"):
        _submit(provider, {})
    with pytest.raises(RuntimeError, match="code=INVALID_IMAGE_FORMAT"):
        _poll(provider, "turbotext-queue-deadbeef")


@pytest.mark.contract
@pytest.mark.parametrize("provider_key", ["gemini", "turbotext"])
def test_cancel_idempotent_and_logged(provider_key: str) -> None:
    if provider_key == "gemini":
        provider = MockGeminiProvider(
            MockProviderConfig(
                scenario=MockProviderScenario.TIMEOUT,
                timeout_polls=2,
                error_code="RESOURCE_EXHAUSTED",
                error_message="Quota exceeded for mock Gemini project",
            )
        )
        slot = _build_slot(provider_id="gemini", operation_id="models.generateContent")
    else:
        provider = MockTurbotextProvider(
            MockProviderConfig(
                scenario=MockProviderScenario.TIMEOUT,
                timeout_polls=2,
                error_code="INVALID_IMAGE_FORMAT",
                error_message="Unsupported image format supplied to mock Turbotext",
            )
        )
        slot = _build_slot(provider_id="turbotext", operation_id="generate_image2image")
    job = _build_job(slot_id=slot.id)
    payload = provider.prepare_payload(
        job=job, slot=slot, settings={}, context=_build_context(provider_key)
    )

    reference = _submit(provider, payload)
    _cancel(provider, reference)
    _cancel(provider, reference)

    cancel_events = [event for event in provider.events if event.startswith("cancel:")]
    assert cancel_events[-2:] == [f"cancel:{reference}", f"cancel:{reference}"]
    with pytest.raises(RuntimeError, match="job cancelled"):
        _poll(provider, reference)
