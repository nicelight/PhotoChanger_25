from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.app.db.db_models import Base
from src.app.ingest.ingest_errors import ProviderExecutionError
from src.app.ingest.ingest_models import JobContext, UploadValidationResult
from src.app.providers.providers_gpt_image_1_5 import GptImage15Driver
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
        self,
        url: str,
        headers: dict[str, str],
        data: dict[str, Any],
        files: list[tuple[str, tuple[str, bytes, str]]],
    ) -> DummyResponse:
        self.requests.append({"url": url, "headers": headers, "data": data, "files": files})
        if not self._responses:
            raise RuntimeError("No more responses queued")
        return self._responses.pop(0)


@pytest.fixture(autouse=True)
def openai_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:", future=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    return Session


@pytest.fixture
def media_repo(session_factory) -> MediaObjectRepository:
    return MediaObjectRepository(session_factory)


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
        "model": "gpt-image-1.5-2025-12-16",
        "prompt": "Create a stylized portrait",
        "output": {"format": "png", "size": "1024x1024"},
    }
    return job


@pytest.mark.asyncio
async def test_process_success(monkeypatch, job_context, media_repo):
    response_data = {
        "data": [
            {"b64_json": base64.b64encode(b"result-bytes").decode("ascii")}
        ]
    }
    client = DummyAsyncClient([DummyResponse(200, response_data)])
    monkeypatch.setattr("httpx.AsyncClient", lambda timeout: client)

    driver = GptImage15Driver(media_repo=media_repo)
    result = await driver.process(job_context)

    assert result.content_type == "image/png"
    assert result.payload == b"result-bytes"
    assert client.requests[0]["headers"]["Authorization"] == "Bearer test-key"
    assert client.requests[0]["data"]["model"] == "gpt-image-1.5-2025-12-16"
    assert client.requests[0]["data"]["size"] == "1024x1024"
    assert client.requests[0]["files"][0][0] == "image[]"


@pytest.mark.asyncio
async def test_missing_api_key(monkeypatch, job_context, media_repo):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    driver = GptImage15Driver(media_repo=media_repo)
    with pytest.raises(ProviderExecutionError):
        await driver.process(job_context)


@pytest.mark.asyncio
async def test_missing_prompt(job_context, media_repo):
    job_context.slot_settings["prompt"] = ""
    driver = GptImage15Driver(media_repo=media_repo)
    with pytest.raises(ProviderExecutionError):
        await driver.process(job_context)


@pytest.mark.asyncio
async def test_error_response(monkeypatch, job_context, media_repo):
    error_response = DummyResponse(
        400, {"error": {"type": "invalid_request", "message": "bad input"}}
    )
    client = DummyAsyncClient([error_response])
    monkeypatch.setattr("httpx.AsyncClient", lambda timeout: client)

    driver = GptImage15Driver(media_repo=media_repo)
    with pytest.raises(ProviderExecutionError):
        await driver.process(job_context)
