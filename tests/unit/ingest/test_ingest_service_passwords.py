from typing import Any, cast

from src.app.auth.auth_service import hash_password
from src.app.ingest.ingest_service import IngestService


def build_service(**overrides: Any) -> IngestService:
    defaults: dict[str, Any] = {
        "slot_repo": cast(Any, object()),
        "validator": cast(Any, object()),
        "job_repo": cast(Any, object()),
        "media_repo": cast(Any, object()),
        "result_store": cast(Any, object()),
        "temp_store": cast(Any, object()),
        "result_ttl_hours": 72,
        "sync_response_seconds": 48,
        "ingest_password": "",
    }
    defaults.update(overrides)
    return IngestService(**defaults)


def test_verify_ingest_password_prefers_plaintext_over_hash() -> None:
    legacy_hash = hash_password("legacy-secret")
    service = build_service(
        ingest_password="new-secret", ingest_password_hash=legacy_hash
    )

    assert service.verify_ingest_password("new-secret") is True
    assert service.verify_ingest_password("legacy-secret") is False


def test_verify_ingest_password_supports_legacy_hash_when_plain_missing() -> None:
    legacy_hash = hash_password("legacy-secret")
    service = build_service(ingest_password="", ingest_password_hash=legacy_hash)

    assert service.verify_ingest_password("legacy-secret") is True
    assert service.verify_ingest_password("wrong") is False
