import json
import os
from types import SimpleNamespace

from src.app.auth.auth_service import hash_password
from src.app.settings.settings_service import SettingsService


class DummySettingsRepository:
    def __init__(self, store: dict[str, str]) -> None:
        self.store = store

    def read_all(self) -> dict[str, str]:
        return dict(self.store)

    def bulk_upsert(self, payload: dict[str, str], *, updated_by: str | None = None) -> None:
        self.store.update(payload)


class DummyIngestService:
    def __init__(self) -> None:
        self.sync_response_seconds = 0
        self.result_ttl_hours = 0
        self.ingest_password: str | None = None
        self.ingest_password_hash: str | None = None


def test_load_propagates_legacy_ingest_password_hash() -> None:
    legacy_hash = hash_password("legacy-secret")
    repo = DummySettingsRepository(
        {
            "sync_response_seconds": "48",
            "result_ttl_hours": "72",
            "ingest_password_hash": legacy_hash,
        }
    )
    ingest_service = DummyIngestService()
    config = SimpleNamespace(
        sync_response_seconds=48, result_ttl_hours=72, ingest_password=""
    )

    service = SettingsService(
        repo=repo, ingest_service=ingest_service, config=config
    )
    snapshot = service.load()

    assert snapshot["ingest_password"] == ""
    assert ingest_service.ingest_password == ""
    assert ingest_service.ingest_password_hash == legacy_hash


def test_load_applies_provider_keys_to_env(monkeypatch) -> None:
    provider_keys = {
        "gemini": {"value": "gemini-key", "updated_at": "2026-01-14T20:50:00"},
        "gpt-image-1.5": {"value": "openai-key", "updated_at": "2026-01-14T20:50:00"},
        "turbotext": {"value": "", "updated_at": "2026-01-14T20:50:00"},
    }
    repo = DummySettingsRepository(
        {
            "sync_response_seconds": "48",
            "result_ttl_hours": "72",
            "provider_keys": json.dumps(provider_keys),
        }
    )
    ingest_service = DummyIngestService()
    config = SimpleNamespace(
        sync_response_seconds=48, result_ttl_hours=72, ingest_password=""
    )

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("TURBOTEXT_API_KEY", raising=False)

    service = SettingsService(
        repo=repo, ingest_service=ingest_service, config=config
    )
    service.load()

    assert os.getenv("GEMINI_API_KEY") == "gemini-key"
    assert os.getenv("OPENAI_API_KEY") == "openai-key"
    assert os.getenv("TURBOTEXT_API_KEY") in {None, ""}
