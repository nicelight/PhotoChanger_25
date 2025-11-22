from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.app.db.db_models import Base, MediaObjectModel, SlotTemplateMediaModel
from src.app.ingest.ingest_errors import ProviderExecutionError
from src.app.ingest.ingest_models import JobContext, UploadValidationResult
from src.app.media.temp_media_store import TempMediaHandle
from src.app.providers.providers_turbotext import TurbotextDriver
from src.app.repositories.media_object_repository import MediaObjectRepository


class DummyHTTPResponse:
    def __init__(
        self,
        status_code: int,
        json_data: dict[str, Any] | None = None,
        text: str = "",
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.content = content or b""
        self.headers = headers or {}

    def json(self) -> dict[str, Any]:
        if self._json_data is None:
            raise ValueError("No JSON data")
        return self._json_data


class DummyAsyncClient:
    def __init__(
        self, post_queue: list[DummyHTTPResponse], get_queue: list[DummyHTTPResponse]
    ) -> None:
        self._post_queue = post_queue
        self._get_queue = get_queue

    async def __aenter__(self) -> "DummyAsyncClient":  # pragma: no cover - helper
        return self

    async def __aexit__(
        self, exc_type, exc_value, traceback
    ) -> None:  # pragma: no cover - helper
        return None

    async def post(
        self, url: str, headers: dict[str, str], data: dict[str, Any]
    ) -> DummyHTTPResponse:
        if not self._post_queue:
            raise RuntimeError("No post responses queued")
        return self._post_queue.pop(0)

    async def get(self, url: str, headers: dict[str, str]) -> DummyHTTPResponse:
        if not self._get_queue:
            raise RuntimeError("No get responses queued")
        return self._get_queue.pop(0)


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("PUBLIC_MEDIA_BASE_URL", "https://photochanger.local")
    monkeypatch.setenv("TURBOTEXT_API_KEY", "tt-key")


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
    path.write_bytes(b"template")
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
    payload = tmp_path / "ingest.jpg"
    payload.write_bytes(b"ingest-data")
    job = JobContext(slot_id="slot-555")
    job.job_id = "job-xyz"
    job.temp_payload_path = payload
    job.temp_media.append(TempMediaHandle(media_id="media-ingest", path=payload))
    job.upload = UploadValidationResult(
        content_type="image/jpeg",
        size_bytes=payload.stat().st_size,
        sha256="",
        filename="ingest.jpg",
    )
    job.slot_settings = {
        "prompt": "Improve lighting",
        "template_media": [
            {
                "role": "reference",
                "media_kind": "style",
                "form_field": "url_image_target",
            }
        ],
        "strength": 35,
    }
    job.slot_template_media = {"style": "media-style"}
    return job


def configure_httpx(
    monkeypatch,
    post_responses: list[DummyHTTPResponse],
    get_responses: list[DummyHTTPResponse],
):
    def factory(*args, **kwargs):
        return DummyAsyncClient(post_responses, get_responses)

    monkeypatch.setattr("httpx.AsyncClient", factory)


@pytest.mark.asyncio
async def test_turbotext_success(
    monkeypatch,
    job_context: JobContext,
    media_repo: MediaObjectRepository,
    tmp_path: Path,
):
    store_template_media(
        media_repo,
        slot_id=job_context.slot_id,
        media_id="media-style",
        media_kind="style",
        path=tmp_path / "templates" / "style.png",
    )

    post_responses = [
        DummyHTTPResponse(200, {"success": True, "queueid": "123"}),
        DummyHTTPResponse(
            200,
            {
                "success": True,
                "data": {"uploaded_image": "https://www.turbotext.ru/image/output.png"},
            },
        ),
    ]
    get_responses = [
        DummyHTTPResponse(
            200, content=b"result-bytes", headers={"Content-Type": "image/png"}
        )
    ]
    configure_httpx(monkeypatch, post_responses, get_responses)

    driver = TurbotextDriver(media_repo=media_repo)
    driver.poll_interval_seconds = 0
    result = await driver.process(job_context)

    assert result.payload == b"result-bytes"
    assert result.content_type == "image/png"


@pytest.mark.asyncio
async def test_turbotext_polling_reconnect(
    monkeypatch, job_context, media_repo, tmp_path
):
    store_template_media(
        media_repo,
        slot_id=job_context.slot_id,
        media_id="media-style",
        media_kind="style",
        path=tmp_path / "templates" / "style.png",
    )

    post_responses = [
        DummyHTTPResponse(200, {"success": True, "queueid": "123"}),
        DummyHTTPResponse(200, {"success": False, "action": "reconnect"}),
        DummyHTTPResponse(
            200,
            {
                "success": True,
                "data": {"uploaded_image": "https://www.turbotext.ru/image/output.png"},
            },
        ),
    ]
    get_responses = [
        DummyHTTPResponse(200, content=b"result", headers={"Content-Type": "image/png"})
    ]
    configure_httpx(monkeypatch, post_responses, get_responses)

    driver = TurbotextDriver(media_repo=media_repo)
    driver.poll_interval_seconds = 0
    result = await driver.process(job_context)
    assert result.payload == b"result"


@pytest.mark.asyncio
async def test_turbotext_timeout(monkeypatch, job_context, media_repo, tmp_path):
    store_template_media(
        media_repo,
        slot_id=job_context.slot_id,
        media_id="media-style",
        media_kind="style",
        path=tmp_path / "templates" / "style.png",
    )

    post_responses = [DummyHTTPResponse(200, {"success": True, "queueid": "123"})] + [
        DummyHTTPResponse(200, {"success": False, "action": "reconnect"})
        for _ in range(20)
    ]
    get_responses: list[DummyHTTPResponse] = []
    configure_httpx(monkeypatch, post_responses, get_responses)

    driver = TurbotextDriver(media_repo=media_repo)
    driver.poll_interval_seconds = 0
    with pytest.raises(ProviderExecutionError):
        await driver.process(job_context)


@pytest.mark.asyncio
async def test_turbotext_missing_base_url(monkeypatch, job_context, media_repo):
    monkeypatch.delenv("PUBLIC_MEDIA_BASE_URL", raising=False)
    driver = TurbotextDriver(media_repo=media_repo)
    driver.poll_interval_seconds = 0
    with pytest.raises(ProviderExecutionError):
        await driver.process(job_context)


@pytest.mark.asyncio
async def test_turbotext_create_queue_failure(
    monkeypatch, job_context, media_repo, tmp_path
):
    store_template_media(
        media_repo,
        slot_id=job_context.slot_id,
        media_id="media-style",
        media_kind="style",
        path=tmp_path / "templates" / "style.png",
    )

    post_responses = [DummyHTTPResponse(500)]
    get_responses: list[DummyHTTPResponse] = []
    configure_httpx(monkeypatch, post_responses, get_responses)

    driver = TurbotextDriver(media_repo=media_repo)
    driver.poll_interval_seconds = 0
    with pytest.raises(ProviderExecutionError):
        await driver.process(job_context)


@pytest.mark.asyncio
async def test_turbotext_missing_template(
    monkeypatch, job_context, media_repo, tmp_path
):
    # No template stored, and entry is required (no optional flag)
    post_responses = [DummyHTTPResponse(200, {"success": True, "queueid": "123"})]
    get_responses: list[DummyHTTPResponse] = []
    configure_httpx(monkeypatch, post_responses, get_responses)

    driver = TurbotextDriver(media_repo=media_repo)
    driver.poll_interval_seconds = 0
    with pytest.raises(ProviderExecutionError):
        await driver.process(job_context)
