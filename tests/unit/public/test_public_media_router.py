from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.app.db.db_models import Base, JobHistoryModel, MediaObjectModel, SlotModel
from src.app.media.public_media_service import PublicMediaService
from src.app.public.public_media_router import build_public_media_router
from src.app.repositories.media_object_repository import MediaObjectRepository


@pytest.fixture()
def session_factory(tmp_path) -> sessionmaker:
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'public-test.db').as_posix()}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    return Session


@pytest.fixture()
def client(tmp_path: Path, session_factory) -> TestClient:
    repo = MediaObjectRepository(session_factory)
    service = PublicMediaService(media_repo=repo)
    app = FastAPI()
    app.include_router(build_public_media_router(service))
    return TestClient(app)


def add_media(session_factory, media_id: str, path: Path, *, expires_in_seconds: int = 60) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"data")
    with session_factory() as session:
        if not session.query(SlotModel).filter(SlotModel.id == "slot").count():
            session.add(
                SlotModel(
                    id="slot",
                    display_name="Slot",
                    provider="turbotext",
                    operation="image_edit",
                    settings_json="{}",
                    size_limit_mb=15,
                    is_active=True,
                )
            )
        session.add(
            JobHistoryModel(
                job_id=f"job-{media_id}",
                slot_id="slot",
                status="pending",
            )
        )
        session.add(
            MediaObjectModel(
                id=media_id,
                job_id=f"job-{media_id}",
                slot_id="slot",
                scope="provider",
                path=str(path),
                preview_path=None,
                expires_at=datetime.utcnow() + timedelta(seconds=expires_in_seconds),
                cleaned_at=None,
            )
        )
        session.commit()


def test_public_media_serves_file(client: TestClient, tmp_path: Path, session_factory) -> None:
    add_media(session_factory, "media-1", tmp_path / "provider" / "file.png")
    response = client.get("/public/provider-media/media-1")
    assert response.status_code == 200
    assert response.content == b"data"
    assert response.headers["content-type"].startswith("image/")


def test_public_media_404(client: TestClient) -> None:
    response = client.get("/public/provider-media/missing")
    assert response.status_code == 404


def test_public_media_expired(client: TestClient, tmp_path: Path, session_factory) -> None:
    add_media(session_factory, "media-expired", tmp_path / "provider" / "old.png", expires_in_seconds=-1)
    response = client.get("/public/provider-media/media-expired")
    assert response.status_code == 410
