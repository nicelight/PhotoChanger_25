import asyncio
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.app.config import IngestLimits, MediaPaths
from src.app.db.db_init import init_db
from src.app.db.db_models import JobHistoryModel
from src.app.ingest.ingest_errors import ChecksumMismatchError, ProviderTimeoutError
from src.app.ingest.ingest_service import IngestService
from src.app.ingest.ingest_models import FailureReason, JobContext, JobStatus
from src.app.ingest.validation import UploadValidator
from src.app.media.media_service import ResultStore
from src.app.media.temp_media_store import TempMediaStore
from src.app.repositories.job_history_repository import JobHistoryRepository
from src.app.repositories.media_object_repository import MediaObjectRepository
from src.app.slots.slots_repository import SlotRepository
from starlette.datastructures import Headers  # добавь рядом с UploadFile

ASSETS = Path(__file__).resolve().parents[2] / "assets"


def load_asset(name: str) -> bytes:
    return (ASSETS / name).read_bytes()


# для реальных не моковых данных. 
# def make_upload(data: bytes, *, content_type: str = "image/png", filename: str = "file.png") -> UploadFile:
#     return UploadFile(filename=filename, file=BytesIO(data), content_type=content_type)

def make_upload(
    data: bytes,
    *,
    content_type: str = "image/png",
    filename: str = "file.png",
) -> UploadFile:
    headers = Headers({"content-type": content_type})
    return UploadFile(filename=filename, file=BytesIO(data), headers=headers)


def build_service(
    tmp_path: Path,
    *,
    sync_response_seconds: int = 48,
    service_cls: type[IngestService] = IngestService,
    **service_kwargs,
) -> IngestService:
    engine = create_engine("sqlite:///:memory:", future=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    init_db(engine, session_factory)

    limits = IngestLimits(
        allowed_content_types=("image/jpeg", "image/png", "image/webp"),
        slot_default_limit_mb=15,
        absolute_cap_bytes=20 * 1024 * 1024,
        chunk_size_bytes=1024,
    )
    validator = UploadValidator(limits)
    slot_repo = SlotRepository(session_factory)
    job_repo = JobHistoryRepository(session_factory)
    media_repo = MediaObjectRepository(session_factory)
    media_paths = MediaPaths(
        root=tmp_path,
        results=tmp_path / "results",
        templates=tmp_path / "templates",
        temp=tmp_path / "temp",
    )
    result_store = ResultStore(media_paths)
    temp_store = TempMediaStore(
        paths=media_paths,
        media_repo=media_repo,
        temp_ttl_seconds=sync_response_seconds,
    )
    return service_cls(
        slot_repo=slot_repo,
        validator=validator,
        job_repo=job_repo,
        media_repo=media_repo,
        result_store=result_store,
        temp_store=temp_store,
        result_ttl_hours=72,
        sync_response_seconds=sync_response_seconds,
        **service_kwargs,
    )


class StubIngestService(IngestService):
    def __init__(self, *args, provider_callable, **kwargs):
        super().__init__(*args, **kwargs)
        self._provider_callable = provider_callable

    async def _invoke_provider(self, job):
        return await self._provider_callable(job)


@pytest.mark.asyncio
async def test_prepare_and_validate(tmp_path) -> None:
    service = build_service(tmp_path)
    job = service.prepare_job("slot-001")

    assert job.job_id is not None
    assert job.result_dir is not None and job.result_dir.exists()

    data = load_asset("tiny.png")
    upload = make_upload(data)
    expected_hash = sha256(data).hexdigest()

    result = await service.validate_upload(job, upload, expected_hash)

    assert result.sha256 == expected_hash
    assert job.upload == result
    assert len(job.temp_media) == 1
    assert job.temp_payload_path is not None
    assert job.temp_payload_path.exists()


@pytest.mark.asyncio
async def test_checksum_mismatch(tmp_path) -> None:
    service = build_service(tmp_path)
    job = service.prepare_job("slot-001")
    upload = make_upload(b"PNGDATA")

    with pytest.raises(ChecksumMismatchError):
        await service.validate_upload(job, upload, "deadbeef")


@pytest.mark.asyncio
async def test_record_success(tmp_path) -> None:
    service = build_service(tmp_path)
    job = service.prepare_job("slot-001")
    data = load_asset("tiny.png")
    upload = make_upload(data, content_type="image/png")
    expected_hash = sha256(data).hexdigest()
    await service.validate_upload(job, upload, expected_hash)
    temp_path = job.temp_payload_path
    assert temp_path is not None and temp_path.exists()

    path = service.record_success(job, data, "image/png")

    assert path.exists()
    assert temp_path is not None and not temp_path.exists()
    with service.job_repo._session_factory() as session:  # type: ignore[attr-defined]
        model = session.get(JobHistoryModel, job.job_id)
        assert model is not None
        assert model.status == JobStatus.DONE.value
        assert model.failure_reason is None


@pytest.mark.asyncio
async def test_record_failure(tmp_path) -> None:
    service = build_service(tmp_path)
    job = service.prepare_job("slot-001")
    directory = job.result_dir
    assert directory and directory.exists()
    data = load_asset("tiny.png")
    upload = make_upload(data, content_type="image/png")
    expected_hash = sha256(data).hexdigest()
    await service.validate_upload(job, upload, expected_hash)
    temp_path = job.temp_payload_path
    assert temp_path is not None and temp_path.exists()

    service.record_failure(
        job,
        failure_reason=FailureReason.PROVIDER_TIMEOUT,
        status=JobStatus.TIMEOUT,
    )

    assert directory and not directory.exists()
    assert temp_path is not None and not temp_path.exists()
    with service.job_repo._session_factory() as session:  # type: ignore[attr-defined]
        model = session.get(JobHistoryModel, job.job_id)
        assert model is not None
        assert model.status == JobStatus.TIMEOUT.value
        assert model.failure_reason == FailureReason.PROVIDER_TIMEOUT.value


@pytest.mark.asyncio
async def test_process_timeout(tmp_path) -> None:
    async def slow_provider(_job: JobContext) -> tuple[bytes, str]:
        try:
            await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            raise
        return b"delayed", "image/png"

    service = build_service(
        tmp_path,
        sync_response_seconds=0.1,
        service_cls=StubIngestService,
        provider_callable=slow_provider,
    )
    job = service.prepare_job("slot-001")
    data = load_asset("tiny.png")
    upload = make_upload(data, content_type="image/png")
    expected_hash = sha256(data).hexdigest()
    await service.validate_upload(job, upload, expected_hash)
    temp_path = job.temp_payload_path
    assert temp_path is not None and temp_path.exists()

    with pytest.raises(ProviderTimeoutError):
        await service.process(job)

    assert job.result_dir is not None and not job.result_dir.exists()
    assert temp_path is not None and not temp_path.exists()
    with service.job_repo._session_factory() as session:  # type: ignore[attr-defined]
        model = session.get(JobHistoryModel, job.job_id)
        assert model is not None
        assert model.status == JobStatus.TIMEOUT.value
        assert model.failure_reason == FailureReason.PROVIDER_TIMEOUT.value
