"""Unit tests for ingest helper utilities."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from datetime import datetime, timezone
from tempfile import SpooledTemporaryFile
from uuid import UUID, uuid4

import pytest
from fastapi import UploadFile

pytestmark = pytest.mark.unit

from src.app.api.routes.ingest import (
    InvalidPayloadError,
    PayloadTooLargeError,
    _decode_inline_result,
    _error_response,
    _sanitize_filename,
    _store_payload,
)
from src.app.domain.models import Job, JobStatus


def _build_job() -> Job:
    now = datetime.now(timezone.utc)
    return Job(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        slot_id="slot-001",
        status=JobStatus.PENDING,
        is_finalized=True,
        failure_reason=None,
        expires_at=now,
        created_at=now,
        updated_at=now,
        payload_path=None,
    )


def _make_upload_file(payload: bytes, filename: str) -> UploadFile:
    file = SpooledTemporaryFile()
    file.write(payload)
    file.seek(0)
    return UploadFile(filename=filename, file=file)


def test_decode_inline_result_success() -> None:
    job = _build_job()
    payload = b"binary-result"
    job.result_inline_base64 = base64.b64encode(payload).decode("ascii")
    job.result_mime_type = "image/jpeg"

    decoded, mime = _decode_inline_result(job)

    assert decoded == payload
    assert mime == "image/jpeg"


def test_decode_inline_result_without_mime() -> None:
    job = _build_job()
    job.result_inline_base64 = base64.b64encode(b"foo").decode("ascii")

    with pytest.raises(ValueError):
        _decode_inline_result(job)


def test_decode_inline_result_invalid_base64() -> None:
    job = _build_job()
    job.result_inline_base64 = "not-base64"
    job.result_mime_type = "image/png"

    with pytest.raises(ValueError):
        _decode_inline_result(job)


def test_sanitize_filename_removes_dangerous_characters() -> None:
    assert _sanitize_filename("../foo bar?.jpg") == "foo_bar_.jpg"


def test_sanitize_filename_defaults_to_placeholder() -> None:
    assert _sanitize_filename("") == "upload.bin"
    assert _sanitize_filename(None) == "upload.bin"


def test_error_response_payload() -> None:
    response = _error_response(
        status_code=400,
        code="invalid_payload",
        message="Uploaded file is empty",
        details={"field": "fileToUpload"},
    )
    assert response.status_code == 400
    assert response.headers["content-type"] == "application/json"
    assert json.loads(response.body.decode("utf-8")) == {
        "error": {
            "code": "invalid_payload",
            "message": "Uploaded file is empty",
            "details": {"field": "fileToUpload"},
        }
    }


def test_store_payload_writes_file(tmp_path) -> None:
    payload = b"example-image"
    upload = _make_upload_file(payload, "example.jpg")
    job_id = uuid4()

    stored = asyncio.run(
        _store_payload(
            upload,
            media_root=tmp_path,
            job_id=job_id,
            filename="example.jpg",
        )
    )

    assert stored.absolute_path.read_bytes() == payload
    assert stored.relative_path.endswith("example.jpg")
    assert stored.size_bytes == len(payload)
    assert stored.checksum == hashlib.sha256(payload).hexdigest()
    asyncio.run(upload.close())


def test_store_payload_rejects_empty_file(tmp_path) -> None:
    upload = _make_upload_file(b"", "empty.jpg")
    job_id = uuid4()

    with pytest.raises(InvalidPayloadError):
        asyncio.run(
            _store_payload(
                upload,
                media_root=tmp_path,
                job_id=job_id,
                filename="empty.jpg",
            )
        )

    asyncio.run(upload.close())
    payload_dir = tmp_path / "payloads" / str(job_id)
    assert not any(path.is_file() for path in payload_dir.rglob("*"))


def test_store_payload_enforces_size_limit(tmp_path, monkeypatch) -> None:
    upload = _make_upload_file(b"too-large", "large.jpg")
    job_id = uuid4()
    monkeypatch.setattr("src.app.api.routes.ingest.MAX_PAYLOAD_BYTES", 4)

    with pytest.raises(PayloadTooLargeError):
        asyncio.run(
            _store_payload(
                upload,
                media_root=tmp_path,
                job_id=job_id,
                filename="large.jpg",
            )
        )

    asyncio.run(upload.close())
    payload_dir = tmp_path / "payloads" / str(job_id)
    assert not any(path.is_file() for path in payload_dir.rglob("*"))
