from __future__ import annotations

import base64
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.app.db.db_models import Base, MediaObjectModel, SlotTemplateMediaModel
from src.app.providers.template_media_resolver import (
    TemplateMediaResolutionError,
    resolve_template_media,
)
from src.app.repositories.media_object_repository import MediaObjectRepository


def setup_repo(tmp_path: Path) -> MediaObjectRepository:
    engine = create_engine("sqlite:///:memory:", future=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    return MediaObjectRepository(Session)


def create_media(
    repo: MediaObjectRepository,
    *,
    media_id: str,
    slot_id: str,
    scope: str,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"binary-image")
    with repo._session_factory() as session:  # type: ignore[attr-defined]
        session.add(
            MediaObjectModel(
                id=media_id,
                job_id="job-1",
                slot_id=slot_id,
                scope=scope,
                path=str(path),
                preview_path=None,
                expires_at=datetime.utcnow() + timedelta(hours=1),
                cleaned_at=None,
            )
        )
        session.commit()


def add_template_binding(
    repo: MediaObjectRepository,
    *,
    slot_id: str,
    media_kind: str,
    media_object_id: str,
) -> None:
    with repo._session_factory() as session:  # type: ignore[attr-defined]
        session.add(
            SlotTemplateMediaModel(
                slot_id=slot_id,
                media_kind=media_kind,
                media_object_id=media_object_id,
            )
        )
        session.commit()


def test_resolve_by_media_object_id(tmp_path: Path) -> None:
    repo = setup_repo(tmp_path)
    create_media(
        repo,
        media_id="mo-1",
        slot_id="slot-001",
        scope="template",
        path=tmp_path / "templates" / "overlay.png",
    )

    bindings = [
        {"role": "overlay", "media_object_id": "mo-1"},
    ]

    result = resolve_template_media(slot_id="slot-001", bindings=bindings, media_repo=repo)
    assert len(result) == 1
    media = result[0]
    assert media.role == "overlay"
    assert media.media_object_id == "mo-1"
    assert media.mime_type == "image/png"
    assert base64.b64decode(media.data_base64) == b"binary-image"


def test_resolve_by_media_kind(tmp_path: Path) -> None:
    repo = setup_repo(tmp_path)
    create_media(
        repo,
        media_id="mo-2",
        slot_id="slot-002",
        scope="template",
        path=tmp_path / "templates" / "background.jpg",
    )
    add_template_binding(repo, slot_id="slot-002", media_kind="background", media_object_id="mo-2")

    bindings = [
        {"role": "background", "media_kind": "background"},
    ]

    result = resolve_template_media(slot_id="slot-002", bindings=bindings, media_repo=repo)
    assert len(result) == 1
    media = result[0]
    assert media.media_kind == "background"
    assert base64.b64decode(media.data_base64) == b"binary-image"


def test_optional_binding_missing(tmp_path: Path) -> None:
    repo = setup_repo(tmp_path)
    bindings = [
        {"role": "overlay", "media_kind": "style", "optional": True},
    ]

    result = resolve_template_media(slot_id="slot-003", bindings=bindings, media_repo=repo)
    assert result == []


def test_duplicate_media_kind_raises(tmp_path: Path) -> None:
    repo = setup_repo(tmp_path)
    create_media(
        repo,
        media_id="mo-3",
        slot_id="slot-004",
        scope="template",
        path=tmp_path / "templates" / "style1.png",
    )
    create_media(
        repo,
        media_id="mo-4",
        slot_id="slot-004",
        scope="template",
        path=tmp_path / "templates" / "style2.png",
    )
    add_template_binding(repo, slot_id="slot-004", media_kind="style", media_object_id="mo-3")
    add_template_binding(repo, slot_id="slot-004", media_kind="style", media_object_id="mo-4")

    bindings = [
        {"role": "style", "media_kind": "style"},
    ]

    with pytest.raises(TemplateMediaResolutionError):
        resolve_template_media(slot_id="slot-004", bindings=bindings, media_repo=repo)


def test_missing_non_optional_raises(tmp_path: Path) -> None:
    repo = setup_repo(tmp_path)
    bindings = [
        {"role": "background", "media_kind": "background", "optional": False},
    ]

    with pytest.raises(TemplateMediaResolutionError):
        resolve_template_media(slot_id="slot-005", bindings=bindings, media_repo=repo)
