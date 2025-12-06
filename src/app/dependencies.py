"""Dependency wiring helpers."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .auth.auth_api import router as auth_router
from .auth.auth_service import AuthService
from .config import AppConfig
from .ingest.ingest_api import router as ingest_router
from .ingest.ingest_service import IngestService
from .ingest.validation import UploadValidator
from .media.media_service import ResultStore
from .media.public_media_service import PublicMediaService
from .media.public_result_service import PublicResultService
from .media.template_media_api import router as template_media_router
from .media.temp_media_store import TempMediaStore
from .providers.providers_factory import create_driver
from .public.public_media_router import build_public_media_router
from .public.public_results_router import build_public_results_router
from .public.public_gallery_router import build_public_gallery_router
from .public.public_gallery_admin_router import build_public_gallery_admin_router
from .public.public_gallery_service import GalleryCache, GalleryRateLimiter, GalleryShareState
from .repositories.job_history_repository import JobHistoryRepository
from .repositories.media_object_repository import MediaObjectRepository
from .slots.slots_repository import SlotRepository
from .slots.slots_api import router as slots_router
from .settings.settings_api import router as settings_router
from .settings.settings_repository import SettingsRepository
from .settings.settings_service import SettingsService
from .stats.stats_api import router as stats_router
from .stats.metrics_api import router as metrics_router
from .stats.metrics_exporter import MetricsExporter
from .stats.stats_repository import StatsRepository
from .stats.stats_service import StatsService
from .ui.stats_router import router as ui_stats_router


FRONTEND_ROOT = Path(__file__).resolve().parents[2] / "frontend"


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
        ingest_password=config.ingest_password,
        provider_factory=lambda provider_name: create_driver(
            provider_name, media_repo=media_repo
        ),
    )

    settings_repo = SettingsRepository(config.session_factory)
    settings_service = SettingsService(
        repo=settings_repo, ingest_service=ingest_service, config=config
    )
    settings_service.load()
    stats_repo = StatsRepository(config.session_factory)
    stats_service = StatsService(repo=stats_repo, media_paths=config.media_paths)
    metrics_exporter = MetricsExporter(
        stats_repo=stats_repo,
        media_root=config.media_paths.root,
        sync_response_seconds=config.sync_response_seconds,
    )
    auth_service = AuthService.from_file(
        path=config.admin_credentials_path,
        signing_key=config.jwt_signing_key,
        token_ttl_hours=config.admin_jwt_ttl_hours,
    )

    app.state.config = config
    app.state.ingest_service = ingest_service
    app.state.result_store = result_store
    app.state.temp_store = temp_store
    app.state.slot_repo = slot_repo
    app.state.job_repo = job_repo
    app.state.media_repo = media_repo
    app.state.settings_service = settings_service
    app.state.stats_service = stats_service
    app.state.auth_service = auth_service
    app.state.metrics_exporter = metrics_exporter
    app.state.gallery_share_state = GalleryShareState()
    app.state.gallery_rate_limiter = GalleryRateLimiter(limit_per_minute=30)
    app.state.gallery_cache = GalleryCache(ttl_seconds=30)

    public_media_service = PublicMediaService(media_repo=media_repo)
    public_result_service = PublicResultService(job_repo=job_repo)

    app.include_router(auth_router)
    app.include_router(ingest_router)
    app.include_router(template_media_router)
    app.include_router(slots_router)
    app.include_router(settings_router)
    app.include_router(stats_router)
    app.include_router(metrics_router)
    app.include_router(ui_stats_router)
    app.include_router(build_public_media_router(public_media_service))
    app.include_router(build_public_results_router(public_result_service))
    app.include_router(
        build_public_gallery_router(
            share_state=app.state.gallery_share_state,
            rate_limiter=app.state.gallery_rate_limiter,
            cache=app.state.gallery_cache,
            slot_repo=slot_repo,
            job_repo=job_repo,
            settings_service=settings_service,
            gallery_page_path=str(FRONTEND_ROOT / "public" / "gallery.html"),
        )
    )
    app.include_router(build_public_gallery_admin_router(app.state.gallery_share_state))

    if FRONTEND_ROOT.exists():
        app.mount(
            "/ui/static",
            StaticFiles(directory=FRONTEND_ROOT),
            name="ui-static",
        )
