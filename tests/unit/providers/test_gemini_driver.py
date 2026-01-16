from __future__ import annotations

import base64
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.app.db.db_models import Base, MediaObjectModel, SlotTemplateMediaModel
from src.app.ingest.ingest_errors import ProviderExecutionError, ProviderTimeoutError
from src.app.ingest.ingest_models import JobContext, UploadValidationResult
from src.app.providers.providers_gemini import GeminiDriver
from src.app.repositories.media_object_repository import MediaObjectRepository


class DummyResponse:
    def __init__(
        self, status_code: int, json_data: dict[str, Any] | None = None, text: str = ""
    ) -> None:
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self) -> dict[str, Any]:
        return self._json_data


class DummyAsyncClient:
    def __init__(self, responses: list[DummyResponse]) -> None:
        self._responses = responses
        self.requests: list[dict[str, Any]] = []

    async def __aenter__(self) -> "DummyAsyncClient":  # pragma: no cover - helper
        return self

    async def __aexit__(
        self, exc_type, exc_value, traceback
    ) -> None:  # pragma: no cover - helper
        return None

    async def post(
        self, url: str, headers: dict[str, str], json: dict[str, Any]
    ) -> DummyResponse:
        self.requests.append({"url": url, "headers": headers, "json": json})
        if not self._responses:
            raise RuntimeError("No more responses queued")
        return self._responses.pop(0)


@pytest.fixture(autouse=True)
def gemini_api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:", future=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    return Session


@pytest.fixture
def media_repo(session_factory) -> MediaObjectRepository:
    return MediaObjectRepository(session_factory)


def store_template_media(
    repo: MediaObjectRepository,
    *,
    slot_id: str,
    media_id: str,
    media_kind: str,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"template-bytes")
    with repo._session_factory() as session:  # type: ignore[attr-defined]
        session.add(
            MediaObjectModel(
                id=media_id,
                job_id="job",
                slot_id=slot_id,
                scope="template",
                path=str(path),
                preview_path=None,
                expires_at=datetime.utcnow() + timedelta(hours=1),
                cleaned_at=None,
            )
        )
        session.add(
            SlotTemplateMediaModel(
                slot_id=slot_id,
                media_kind=media_kind,
                media_object_id=media_id,
            )
        )
        session.commit()


@pytest.fixture
def job_context(tmp_path: Path) -> JobContext:
    payload = tmp_path / "ingest.png"
    payload.write_bytes(b"ingest-bytes")

    job = JobContext(slot_id="slot-001")
    job.job_id = "job-123"
    job.temp_payload_path = payload
    job.upload = UploadValidationResult(
        content_type="image/png",
        size_bytes=len(b"ingest-bytes"),
        sha256="",
        filename="ingest.png",
    )
    job.slot_settings = {
        "model": "gemini-2.5-flash-image",
        "prompt": "Keep faces, replace background",
        "output": {"mime_type": "image/png"},
        "image_config": {"aspect_ratio": "3:2"},
        "template_media": [{"role": "style", "media_kind": "style"}],
        "retry_policy": {"max_attempts": 2, "backoff_seconds": 0},
    }
    job.slot_template_media = {"style": "mo-style"}
    return job


@pytest.mark.asyncio
async def test_process_success(
    monkeypatch,
    job_context: JobContext,
    media_repo: MediaObjectRepository,
    tmp_path: Path,
) -> None:
    store_template_media(
        media_repo,
        slot_id=job_context.slot_id,
        media_id="mo-style",
        media_kind="style",
        path=tmp_path / "templates" / "style.png",
    )

    response_data = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": base64.b64encode(b"result-bytes").decode(
                                    "ascii"
                                ),
                            }
                        }
                    ]
                }
            }
        ]
    }
    client = DummyAsyncClient([DummyResponse(200, response_data)])
    monkeypatch.setattr("httpx.AsyncClient", lambda timeout: client)

    driver = GeminiDriver(media_repo=media_repo)
    result = await driver.process(job_context)

    assert result.content_type == "image/png"
    assert result.payload == b"result-bytes"
    assert client.requests[0]["headers"]["x-goog-api-key"] == "test-key"
    assert (
        client.requests[0]["json"]["contents"][0]["parts"][0]["inline_data"][
            "mime_type"
        ]
        == "image/png"
    )
    assert client.requests[0]["json"]["generationConfig"]["responseModalities"] == [
        "IMAGE"
    ]
    assert client.requests[0]["json"]["generationConfig"]["imageConfig"] == {
        "aspectRatio": "3:2"
    }


@pytest.mark.asyncio
async def test_process_retry_and_fail(monkeypatch, job_context, media_repo, tmp_path):
    store_template_media(
        media_repo,
        slot_id=job_context.slot_id,
        media_id="mo-style",
        media_kind="style",
        path=tmp_path / "templates" / "style.png",
    )

    error_response = DummyResponse(
        500, {"error": {"status": "INTERNAL", "message": "boom"}}
    )
    client = DummyAsyncClient([error_response, error_response])
    monkeypatch.setattr("httpx.AsyncClient", lambda timeout: client)

    driver = GeminiDriver(media_repo=media_repo)
    with pytest.raises(ProviderExecutionError):
        await driver.process(job_context)


@pytest.mark.asyncio
async def test_missing_api_key(monkeypatch, job_context, media_repo, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    store_template_media(
        media_repo,
        slot_id=job_context.slot_id,
        media_id="mo-style",
        media_kind="style",
        path=tmp_path / "templates" / "style.png",
    )

    driver = GeminiDriver(media_repo=media_repo)
    with pytest.raises(ProviderExecutionError):
        await driver.process(job_context)


@pytest.mark.asyncio
async def test_missing_prompt(job_context, media_repo):
    job_context.slot_settings["prompt"] = ""
    driver = GeminiDriver(media_repo=media_repo)
    with pytest.raises(ProviderExecutionError):
        await driver.process(job_context)


@pytest.mark.asyncio
async def test_response_without_inline(monkeypatch, job_context, media_repo, tmp_path):
    store_template_media(
        media_repo,
        slot_id=job_context.slot_id,
        media_id="mo-style",
        media_kind="style",
        path=tmp_path / "templates" / "style.png",
    )

    client = DummyAsyncClient([DummyResponse(200, {"candidates": []})])
    monkeypatch.setattr("httpx.AsyncClient", lambda timeout: client)

    driver = GeminiDriver(media_repo=media_repo)
    with pytest.raises(ProviderExecutionError):
        await driver.process(job_context)


@pytest.mark.asyncio
async def test_no_image_retries_until_success(
    monkeypatch, job_context, media_repo, tmp_path
):
    store_template_media(
        media_repo,
        slot_id=job_context.slot_id,
        media_id="mo-style",
        media_kind="style",
        path=tmp_path / "templates" / "style.png",
    )

    response_no_image = DummyResponse(
        200, {"candidates": [{"finish_reason": "NO_IMAGE"}]}
    )
    response_data = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": base64.b64encode(b"result-bytes").decode(
                                    "ascii"
                                ),
                            }
                        }
                    ]
                }
            }
        ]
    }
    client = DummyAsyncClient([response_no_image, DummyResponse(200, response_data)])
    monkeypatch.setattr("httpx.AsyncClient", lambda timeout: client)

    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr("src.app.providers.providers_gemini.asyncio.sleep", fake_sleep)

    driver = GeminiDriver(media_repo=media_repo)
    result = await driver.process(job_context)

    assert result.payload == b"result-bytes"
    assert client.requests
    assert sleep_calls == [3.0]


@pytest.mark.asyncio
async def test_no_image_exhausts_attempts(
    monkeypatch, job_context, media_repo, tmp_path
):
    store_template_media(
        media_repo,
        slot_id=job_context.slot_id,
        media_id="mo-style",
        media_kind="style",
        path=tmp_path / "templates" / "style.png",
    )

    response_no_image = DummyResponse(
        200, {"candidates": [{"finishReason": "NO_IMAGE"}]}
    )
    client = DummyAsyncClient([response_no_image] * 5)
    monkeypatch.setattr("httpx.AsyncClient", lambda timeout: client)

    async def fake_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr("src.app.providers.providers_gemini.asyncio.sleep", fake_sleep)

    driver = GeminiDriver(media_repo=media_repo)
    with pytest.raises(ProviderTimeoutError):
        await driver.process(job_context)
    assert len(client.requests) == 5


@pytest.mark.asyncio
async def test_duplicate_template_media(monkeypatch, job_context, media_repo, tmp_path):
    store_template_media(
        media_repo,
        slot_id=job_context.slot_id,
        media_id="mo-style-1",
        media_kind="style",
        path=tmp_path / "templates" / "style1.png",
    )
    store_template_media(
        media_repo,
        slot_id=job_context.slot_id,
        media_id="mo-style-2",
        media_kind="style",
        path=tmp_path / "templates" / "style2.png",
    )

    driver = GeminiDriver(media_repo=media_repo)
    with pytest.raises(ProviderExecutionError):
        await driver.process(job_context)
