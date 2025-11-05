"""Dependency wiring helpers."""

from fastapi import FastAPI

from .config import AppConfig
from .ingest.ingest_api import router as ingest_router
from .ingest.ingest_service import IngestService
from .ingest.validation import UploadValidator
from .media.media_service import ResultStore
from .media.public_media_service import PublicMediaService
from .media.temp_media_store import TempMediaStore
from .providers.providers_factory import create_driver
from .public.public_media_router import build_public_media_router
from .repositories.job_history_repository import JobHistoryRepository
from .repositories.media_object_repository import MediaObjectRepository
from .slots.slots_repository import SlotRepository


def include_routers(app: FastAPI, config: AppConfig) -> None:
    """Mount module routers and attach services."""
    slot_repo = SlotRepository(config.session_factory)
    validator = UploadValidator(config.ingest_limits)
    job_repo = JobHistoryRepository(config.session_factory)
    media_repo = MediaObjectRepository(config.session_factory)
    result_store = ResultStore(config.media_paths)
    temp_store = TempMediaStore(
        paths=config.media_paths,
        media_repo=media_repo,
        temp_ttl_seconds=config.temp_ttl_seconds,
    )

    ingest_service = IngestService(
        slot_repo=slot_repo,
        validator=validator,
        job_repo=job_repo,
        media_repo=media_repo,
        result_store=result_store,
        temp_store=temp_store,
        result_ttl_hours=config.result_ttl_hours,
        sync_response_seconds=config.sync_response_seconds,
        provider_factory=lambda provider_name: create_driver(provider_name, media_repo=media_repo),
    )

    app.state.config = config
    app.state.ingest_service = ingest_service
    app.state.result_store = result_store
    app.state.temp_store = temp_store

    public_media_service = PublicMediaService(media_repo=media_repo)

    app.include_router(ingest_router)
    app.include_router(build_public_media_router(public_media_service))

