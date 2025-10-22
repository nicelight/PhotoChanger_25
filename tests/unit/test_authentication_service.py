from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.app.security.service import (
    AuthenticationError,
    AuthenticationService,
    ThrottlingError,
)

_SERG_HASH = (
    "pbkdf2_sha256$390000$5468b98e343193bd674fdcc63e24c74f$"
    "b78b20878e016f947147690703fe28bd63b7f6ed1f218a30580dc888f4f6a8cd"
)
_IGOR_HASH = (
    "pbkdf2_sha256$390000$4e2f76851d2db157306966d84d1578ef$"
    "194c160e1f13e8213dac3348a4a3413f06ab08b050f9b496531be0a50f68af30"
)
_PERMISSIONS = ["settings:write", "slots:write", "stats:read"]


def _write_credentials(path: Path, throttling: dict[str, int]) -> Path:
    payload = {
        "admins": [
            {
                "username": "serg",
                "password_hash": _SERG_HASH,
                "permissions": _PERMISSIONS,
            },
            {
                "username": "igor",
                "password_hash": _IGOR_HASH,
                "permissions": _PERMISSIONS,
            },
        ],
        "throttling": throttling,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_authenticate_success(tmp_path: Path) -> None:
    credentials_path = _write_credentials(
        tmp_path / "creds.json",
        {"max_attempts": 5, "window_seconds": 60, "lockout_seconds": 300},
    )
    service = AuthenticationService.load_from_file(credentials_path)

    result = service.authenticate("serg", "serg-test-pass")

    assert result.username == "serg"
    assert set(result.permissions) == set(_PERMISSIONS)


def test_authenticate_invalid_password(tmp_path: Path) -> None:
    credentials_path = _write_credentials(
        tmp_path / "creds.json",
        {"max_attempts": 5, "window_seconds": 60, "lockout_seconds": 300},
    )
    service = AuthenticationService.load_from_file(credentials_path)

    with pytest.raises(AuthenticationError):
        service.authenticate("serg", "totally-wrong")


def test_authenticate_throttling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    throttling = {"max_attempts": 2, "window_seconds": 120, "lockout_seconds": 10}
    credentials_path = _write_credentials(tmp_path / "creds.json", throttling)
    service = AuthenticationService.load_from_file(credentials_path)

    first_attempt = datetime(2025, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(service, "_now", lambda: first_attempt)
    with pytest.raises(AuthenticationError):
        service.authenticate("serg", "bad-pass-1")

    second_attempt = first_attempt + timedelta(seconds=1)
    monkeypatch.setattr(service, "_now", lambda: second_attempt)
    with pytest.raises(ThrottlingError):
        service.authenticate("serg", "bad-pass-2")

    locked_attempt = second_attempt + timedelta(seconds=2)
    monkeypatch.setattr(service, "_now", lambda: locked_attempt)
    with pytest.raises(ThrottlingError):
        service.authenticate("serg", "serg-test-pass")

    unlock_time = second_attempt + timedelta(seconds=throttling["lockout_seconds"] + 1)
    monkeypatch.setattr(service, "_now", lambda: unlock_time)
    result = service.authenticate("serg", "serg-test-pass")

    assert result.username == "serg"
    assert set(result.permissions) == set(_PERMISSIONS)
