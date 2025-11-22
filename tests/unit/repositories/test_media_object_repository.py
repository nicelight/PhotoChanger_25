from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.app.db.db_init import init_db
from src.app.repositories.media_object_repository import MediaObjectRepository


def test_register_and_list_expired(tmp_path) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    init_db(engine, session_factory)

    repo = MediaObjectRepository(session_factory)
    expires_at = datetime.utcnow() - timedelta(hours=1)
    media_id = repo.register_result(
        job_id="job123",
        slot_id="slot-001",
        path=tmp_path / "payload.bin",
        preview_path=None,
        expires_at=expires_at,
    )

    expired = repo.list_expired_results(datetime.utcnow())
    target = next((m for m in expired if m.id == media_id), None)
    assert target is not None
    assert target.scope == "result"

    repo.mark_cleaned(media_id, datetime.utcnow())
    expired_after = repo.list_expired_results(datetime.utcnow())
    assert all(m.id != media_id for m in expired_after)


def test_register_temp_and_list_by_scope(tmp_path) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    init_db(engine, session_factory)

    repo = MediaObjectRepository(session_factory)
    expires_at = datetime.utcnow() - timedelta(minutes=1)
    media_id = repo.register_temp(
        job_id="job456",
        slot_id="slot-002",
        path=tmp_path / "upload.bin",
        expires_at=expires_at,
    )

    expired = repo.list_expired_by_scope("provider", datetime.utcnow())
    assert any(m.id == media_id for m in expired)
    assert all(m.scope == "provider" for m in expired)
