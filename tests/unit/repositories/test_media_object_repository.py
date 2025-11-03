from datetime import datetime, timedelta
from pathlib import Path

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
    assert any(m.id == media_id for m in expired)

    repo.mark_cleaned(media_id, datetime.utcnow())
    expired_after = repo.list_expired_results(datetime.utcnow())
    assert all(m.id != media_id for m in expired_after)
