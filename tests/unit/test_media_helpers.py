from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from unittest.mock import Mock

from src.app.domain.models import MediaObject
from src.app.services.media_helpers import persist_base64_result


def _media(job_id: UUID, finalized_at: datetime) -> MediaObject:
    return MediaObject(
        id=uuid4(),
        path="results/object.png",
        public_url="/media/results/object.png",
        expires_at=finalized_at,
        created_at=finalized_at,
        job_id=job_id,
        mime="image/png",
        size_bytes=128,
    )


def test_persist_base64_result_decodes_and_stores_bytes() -> None:
    media_service = Mock()
    job_id = uuid4()
    finalized_at = datetime.now(timezone.utc)
    media = _media(job_id, finalized_at)
    media_service.save_result_media.return_value = (media, "sha256:abc")
    payload = base64.b64encode(b"payload").decode("ascii")

    stored_media, checksum = persist_base64_result(
        media_service,
        job_id=job_id,
        base64_data=payload,
        finalized_at=finalized_at,
        retention_hours=72,
        mime="image/png",
    )

    assert stored_media is media
    assert checksum == "sha256:abc"
    media_service.save_result_media.assert_called_once_with(
        job_id=job_id,
        data=b"payload",
        mime="image/png",
        finalized_at=finalized_at,
        retention_hours=72,
        suggested_name=None,
    )


def test_persist_base64_result_propagates_decode_errors() -> None:
    media_service = Mock()
    finalized_at = datetime.now(timezone.utc)

    with pytest.raises(binascii.Error):
        persist_base64_result(
            media_service,
            job_id=uuid4(),
            base64_data="not-base64",
            finalized_at=finalized_at,
            retention_hours=72,
            mime="image/png",
        )

    media_service.save_result_media.assert_not_called()

