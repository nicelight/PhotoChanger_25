from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.app.config import MediaPaths
from src.app.db.db_init import init_db
from src.app.media.media_cleanup import cleanup_expired_results
from src.app.media.media_service import ResultStore
from src.app.media.temp_media_store import TempMediaStore
from src.app.repositories.media_object_repository import MediaObjectRepository


def build_repos(tmp_path: Path):
    engine = create_engine("sqlite:///:memory:", future=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    init_db(engine, session_factory)
    media_repo = MediaObjectRepository(session_factory)
    media_paths = MediaPaths(
        root=tmp_path,
        results=tmp_path / "results",
        templates=tmp_path / "templates",
        temp=tmp_path / "temp",
    )
    store = ResultStore(media_paths)
    return media_repo, store, media_paths


def test_cleanup_expired_results(tmp_path):
    media_repo, store, _ = build_repos(tmp_path)
    slot_id = "slot-001"
    job_id = "job123"
    directory = store.ensure_structure(slot_id, job_id)
    (directory / "payload.bin").write_bytes(b"test")

    expires_at = datetime.utcnow() - timedelta(hours=1)
    media_id = media_repo.register_result(
        job_id=job_id,
        slot_id=slot_id,
        path=directory / "payload.bin",
        preview_path=None,
        expires_at=expires_at,
    )

    removed = cleanup_expired_results(media_repo, store)

    assert removed == 1
    assert not directory.exists()
    assert all(
        obj.id != media_id for obj in media_repo.list_expired_results(datetime.utcnow())
    )


def test_cleanup_expired_temp_media(tmp_path):
    media_repo, _, media_paths = build_repos(tmp_path)
    temp_store = TempMediaStore(
        paths=media_paths,
        media_repo=media_repo,
        temp_ttl_seconds=10,
    )
    slot_id = "slot-002"
    job_id = "job456"
    temp_dir = temp_store.ensure_structure(slot_id, job_id)
    payload = temp_dir / "upload.bin"
    payload.write_bytes(b"temp-bytes")
    expires_at = datetime.utcnow() - timedelta(seconds=5)
    media_id = media_repo.register_temp(
        job_id=job_id,
        slot_id=slot_id,
        path=payload,
        expires_at=expires_at,
    )

    removed = temp_store.cleanup_expired()

    assert removed == 1
    assert not payload.exists()
    assert all(
        obj.id != media_id
        for obj in media_repo.list_expired_by_scope("provider", datetime.utcnow())
    )
