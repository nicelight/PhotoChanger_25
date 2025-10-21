from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from src.app.domain.models import (
    MediaCacheSettings,
    Settings,
    SettingsDslrPasswordStatus,
    SettingsIngestConfig,
)
from src.app.services.settings import SettingsService, SettingsUpdate


class DummySecurityService:
    """Deterministic security helper used for unit tests."""

    def __init__(self) -> None:
        self.generated_passwords: list[str] = []
        self.hashed_passwords: list[str] = []

    def hash_password(self, password: str) -> str:
        token = f"hashed:{password}"
        self.hashed_passwords.append(token)
        return token

    def verify_password(self, password: str, encoded: str | None) -> bool:
        return encoded == f"hashed:{password}"

    def generate_password(self) -> str:
        value = "generated-secret"
        self.generated_passwords.append(value)
        return value


class DummyAuditLogger:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def log(self, *, action: str, actor: str, details: dict[str, object]) -> None:
        self.records.append({"action": action, "actor": actor, "details": dict(details)})


class DummyRepository:
    def __init__(self, settings: Settings, password_hash: str | None = None) -> None:
        self.settings = settings
        self.password_hash = password_hash
        self.load_calls = 0
        self.save_calls = 0
        self.update_calls = 0
        self.hash_calls = 0

    def load(self) -> Settings:
        self.load_calls += 1
        return self.settings

    def save(self, settings: Settings) -> Settings:
        self.save_calls += 1
        self.settings = settings
        return settings

    def get_ingest_password_hash(self) -> str | None:
        self.hash_calls += 1
        return self.password_hash

    def update_ingest_password(
        self, *, rotated_at: datetime, updated_by: str, password_hash: str
    ) -> Settings:
        self.update_calls += 1
        self.password_hash = password_hash
        password_status = replace(
            self.settings.dslr_password,
            is_set=True,
            updated_at=rotated_at,
            updated_by=updated_by,
        )
        self.settings = replace(self.settings, dslr_password=password_status)
        return self.settings


class CacheProbe:
    def __init__(self) -> None:
        self.calls = 0

    def invalidate(self) -> None:
        self.calls += 1


@pytest.fixture
def sample_settings() -> Settings:
    now = datetime.now(timezone.utc)
    return Settings(
        dslr_password=SettingsDslrPasswordStatus(
            is_set=True,
            updated_at=now,
            updated_by="bootstrap",
        ),
        ingest=SettingsIngestConfig(
            sync_response_timeout_sec=50,
            ingest_ttl_sec=50,
        ),
        media_cache=MediaCacheSettings(
            processed_media_ttl_hours=72,
            public_link_ttl_sec=50,
        ),
        provider_keys={},
    )


@pytest.fixture
def repository(sample_settings: Settings) -> DummyRepository:
    return DummyRepository(sample_settings, password_hash="hashed:secret")


@pytest.fixture
def audit_logger() -> DummyAuditLogger:
    return DummyAuditLogger()


@pytest.fixture
def security() -> DummySecurityService:
    return DummySecurityService()


@pytest.fixture
def cache_probe() -> CacheProbe:
    return CacheProbe()


@pytest.fixture
def service(
    repository: DummyRepository,
    security: DummySecurityService,
    audit_logger: DummyAuditLogger,
    cache_probe: CacheProbe,
) -> SettingsService:
    return SettingsService(
        repository=repository,
        security_service=security,
        audit_logger=audit_logger,
        authorize=lambda actor: actor == "admin",
        cache_invalidator=cache_probe.invalidate,
    )


@pytest.mark.unit
def test_get_settings_uses_cache(repository: DummyRepository, service: SettingsService) -> None:
    first = service.get_settings()
    second = service.get_settings()
    assert first is second
    assert repository.load_calls == 1

    refreshed = service.get_settings(force_refresh=True)
    assert refreshed is first
    assert repository.load_calls == 2


@pytest.mark.unit
def test_update_settings_updates_ttl_and_logs(
    repository: DummyRepository,
    service: SettingsService,
    audit_logger: DummyAuditLogger,
    cache_probe: CacheProbe,
) -> None:
    service.get_settings()
    updated = service.update_settings(
        SettingsUpdate(sync_response_timeout_sec=55),
        updated_by="admin",
    )

    assert repository.save_calls == 1
    assert updated.ingest.sync_response_timeout_sec == 55
    assert updated.ingest.ingest_ttl_sec == 55
    assert updated.media_cache.public_link_ttl_sec == 55
    assert cache_probe.calls == 1
    assert any(record["action"] == "settings.update" for record in audit_logger.records)

    repository.load_calls = 0
    service.get_settings()
    assert repository.load_calls == 1


@pytest.mark.unit
def test_update_settings_denies_without_permission(
    repository: DummyRepository, service: SettingsService
) -> None:
    with pytest.raises(PermissionError):
        service.update_settings(SettingsUpdate(sync_response_timeout_sec=52), updated_by="guest")
    assert repository.save_calls == 0


@pytest.mark.unit
def test_rotate_ingest_password_hashes_and_logs(
    repository: DummyRepository,
    service: SettingsService,
    audit_logger: DummyAuditLogger,
    cache_probe: CacheProbe,
) -> None:
    rotated_at = datetime.now(timezone.utc)
    settings, password = service.rotate_ingest_password(
        rotated_at=rotated_at,
        updated_by="admin",
    )

    assert password == "generated-secret"
    assert repository.update_calls == 1
    assert repository.password_hash == "hashed:generated-secret"
    assert settings.dslr_password.updated_by == "admin"
    assert cache_probe.calls == 1
    assert any(
        record["action"] == "settings.rotate_ingest_password"
        for record in audit_logger.records
    )


@pytest.mark.unit
def test_verify_ingest_password_uses_security_service(
    repository: DummyRepository, service: SettingsService
) -> None:
    assert service.verify_ingest_password("secret") is True
    assert service.verify_ingest_password("wrong") is False
    assert repository.hash_calls == 1

    # Cached hash should prevent additional repository access
    service.verify_ingest_password("secret")
    assert repository.hash_calls == 1
