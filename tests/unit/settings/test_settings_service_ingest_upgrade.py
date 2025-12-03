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
