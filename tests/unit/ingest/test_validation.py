from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile

from src.app.config import IngestLimits
from src.app.ingest.ingest_errors import PayloadTooLargeError, UnsupportedMediaError
from src.app.ingest.validation import UploadValidator

ASSETS = Path(__file__).resolve().parents[2] / "assets"


def load_asset(name: str) -> bytes:
    return (ASSETS / name).read_bytes()


def make_upload(data: bytes, *, content_type: str, filename: str) -> UploadFile:
    return UploadFile(filename=filename, file=BytesIO(data), content_type=content_type)


def build_validator(chunk_size: int = 1024) -> UploadValidator:
    limits = IngestLimits(
        allowed_content_types=("image/jpeg", "image/png", "image/webp"),
        slot_default_limit_mb=15,
        absolute_cap_bytes=50 * 1024 * 1024,
        chunk_size_bytes=chunk_size,
    )
    return UploadValidator(limits)


@pytest.mark.asyncio
async def test_validate_passes_with_allowed_png() -> None:
    data = load_asset("tiny.png")
    upload = make_upload(data, content_type="image/png", filename="tiny.png")
    validator = build_validator(chunk_size=2)

    result = await validator.validate(slot_limit_mb=1, upload=upload)

    assert result.size_bytes == len(data)
    assert result.content_type == "image/png"
    assert await upload.read() == data


@pytest.mark.asyncio
async def test_validate_rejects_unsupported_media() -> None:
    data = load_asset("tiny.png")
    upload = make_upload(data, content_type="image/gif", filename="tiny.gif")
    validator = build_validator()

    with pytest.raises(UnsupportedMediaError):
        await validator.validate(slot_limit_mb=1, upload=upload)


@pytest.mark.asyncio
async def test_validate_rejects_too_large_payload() -> None:
    data = load_asset("tiny.png") * 200
    upload = make_upload(data, content_type="image/png", filename="large.png")
    validator = build_validator(chunk_size=512)

    with pytest.raises(PayloadTooLargeError):
        await validator.validate(slot_limit_mb=0, upload=upload)
