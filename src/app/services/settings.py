from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Callable, Mapping, Protocol

from ..domain.models import Settings
from ..infrastructure.settings_repository import SettingsRepository
from ..security.service import SecurityService


class AuditLogger(Protocol):
    """Minimal protocol implemented by audit logging backends."""

    def log(self, *, action: str, actor: str, details: Mapping[str, object]) -> None:
        """Persist an audit record for the supplied action."""


@dataclass(slots=True)
class SettingsUpdate:
    """Payload describing configuration changes requested by administrators."""

    sync_response_timeout_sec: int | None = None


class SettingsService:
    """Coordinates read/write operations for global application settings."""

    def __init__(
        self,
        *,
        repository: SettingsRepository,
        security_service: SecurityService,
        audit_logger: AuditLogger,
        authorize: Callable[[str], bool] | None = None,
        cache_invalidator: Callable[[], None] | None = None,
    ) -> None:
        self._repository = repository
        self._security_service = security_service
        self._audit_logger = audit_logger
        self._authorize = authorize or (lambda _actor: True)
        self._cache_invalidator = cache_invalidator
        self._cached_settings: Settings | None = None
        self._cached_password_hash: str | None = None

    def get_settings(self, *, force_refresh: bool = False) -> Settings:
        """Return the latest settings snapshot, reloading from storage when required."""

        if force_refresh or self._cached_settings is None:
            self._cached_settings = self._repository.load()
        return self._cached_settings

    def verify_ingest_password(self, password: str) -> bool:
        """Validate DSLR ingest credentials without exposing the hash."""

        if not password:
            return False
        password_hash = self._get_ingest_password_hash()
        return self._security_service.verify_password(password, password_hash)

    def update_settings(self, payload: SettingsUpdate, *, updated_by: str) -> Settings:
        """Persist configuration changes coming from the admin UI."""

        self._ensure_authorized(updated_by)
        current = self.get_settings()
        ingest_timeout = payload.sync_response_timeout_sec
        if ingest_timeout is None:
            ingest_timeout = current.ingest.sync_response_timeout_sec
        if ingest_timeout < 1:
            raise ValueError("sync_response_timeout_sec must be positive")

        updated_ingest = replace(
            current.ingest,
            sync_response_timeout_sec=ingest_timeout,
            ingest_ttl_sec=ingest_timeout,
        )
        updated_media_cache = replace(
            current.media_cache,
            public_link_ttl_sec=ingest_timeout,
        )
        updated_settings = replace(
            current,
            ingest=updated_ingest,
            media_cache=updated_media_cache,
        )
        persisted = self._repository.save(updated_settings)
        self._log_audit(
            "settings.update",
            actor=updated_by,
            details={"sync_response_timeout_sec": ingest_timeout},
        )
        self._invalidate_cache()
        return persisted

    def rotate_ingest_password(
        self,
        *,
        rotated_at: datetime,
        updated_by: str,
        new_password: str | None = None,
    ) -> tuple[Settings, str]:
        """Rotate the ingest password hash and update ``Settings.dslr_password``."""

        self._ensure_authorized(updated_by)
        password = new_password or self._security_service.generate_password()
        password_hash = self._security_service.hash_password(password)
        settings = self._repository.update_ingest_password(
            rotated_at=rotated_at,
            updated_by=updated_by,
            password_hash=password_hash,
        )
        self._log_audit(
            "settings.rotate_ingest_password",
            actor=updated_by,
            details={"rotated_at": rotated_at.isoformat()},
        )
        self._invalidate_cache()
        return settings, password

    def _get_ingest_password_hash(self) -> str | None:
        if self._cached_password_hash is None:
            self._cached_password_hash = self._repository.get_ingest_password_hash()
        return self._cached_password_hash

    def _ensure_authorized(self, actor: str) -> None:
        if not actor:
            raise PermissionError("actor must be provided")
        if not self._authorize(actor):
            raise PermissionError(f"actor '{actor}' is not allowed to manage settings")

    def _log_audit(self, action: str, *, actor: str, details: Mapping[str, object]) -> None:
        self._audit_logger.log(action=action, actor=actor, details=dict(details))

    def _invalidate_cache(self) -> None:
        self._cached_settings = None
        self._cached_password_hash = None
        if self._cache_invalidator is not None:
            self._cache_invalidator()
