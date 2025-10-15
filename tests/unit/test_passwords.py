from __future__ import annotations

import pytest

from src.app.security.passwords import PasswordHash, verify_password


@pytest.mark.unit
def test_verify_password_accepts_valid_secret() -> None:
    encoded = (
        "pbkdf2_sha256$390000$70686f746f6368616e6765722d696e676573742d73616c74$"
        "4fb957db11f5dc3c987b7dd81e5ce44a25fd9c4601093921d9a48df767fdcb0a"
    )
    assert verify_password("correct-horse-battery", encoded) is True


@pytest.mark.unit
def test_verify_password_rejects_invalid_secret() -> None:
    encoded = (
        "pbkdf2_sha256$390000$70686f746f6368616e6765722d696e676573742d73616c74$"
        "4fb957db11f5dc3c987b7dd81e5ce44a25fd9c4601093921d9a48df767fdcb0a"
    )
    assert verify_password("wrong", encoded) is False


@pytest.mark.unit
def test_password_hash_parse_rejects_invalid_format() -> None:
    with pytest.raises(ValueError):
        PasswordHash.parse("invalid-format")
