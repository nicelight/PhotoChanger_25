"""High level security helpers used by application services."""
from __future__ import annotations

import hashlib
import json
import logging
import secrets
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Deque, Mapping

from .passwords import DEFAULT_ALGORITHM, DEFAULT_ITERATIONS, verify_password


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SecurityService:
    """Encapsulates hashing and password generation routines."""

    iterations: int = DEFAULT_ITERATIONS
    algorithm: str = DEFAULT_ALGORITHM
    salt_bytes: int = 16
    password_length: int = 32

    def hash_password(self, password: str) -> str:
        """Return a PBKDF2 hash encoded with algorithm metadata."""

        if not password:
            raise ValueError("password must not be empty")
        salt = secrets.token_bytes(self.salt_bytes)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, self.iterations
        )
        return "$".join(
            (
                self.algorithm,
                str(self.iterations),
                salt.hex(),
                digest.hex(),
            )
        )

    def verify_password(self, password: str, encoded: str | None) -> bool:
        """Check ``password`` against ``encoded`` using constant time operations."""

        if not encoded:
            return False
        return verify_password(password, encoded)

    def generate_password(self) -> str:
        """Generate a random password compatible with DSLR Remote Pro."""

        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        return "".join(secrets.choice(alphabet) for _ in range(self.password_length))


@dataclass(slots=True)
class ThrottlingSettings:
    """Immutable throttling configuration loaded from credentials file."""

    max_attempts: int
    window_seconds: int
    lockout_seconds: int


@dataclass(slots=True)
class AdminCredential:
    """Runtime state for an administrator account."""

    username: str
    password_hash: str
    permissions: tuple[str, ...]
    locked_until: datetime | None = None
    attempt_timestamps: Deque[datetime] = field(default_factory=deque)


@dataclass(slots=True)
class AuthenticatedAdmin:
    """Authentication result returned to the API layer."""

    username: str
    permissions: tuple[str, ...]


class AuthenticationError(RuntimeError):
    """Raised when provided credentials are invalid."""


class ThrottlingError(RuntimeError):
    """Raised when login attempts exceed throttling limits."""


class AuthenticationService:
    """Authenticate administrators defined in ``runtime_credentials.json``."""

    def __init__(
        self,
        credentials: Mapping[str, AdminCredential],
        *,
        throttling: ThrottlingSettings,
    ) -> None:
        self._credentials = dict(credentials)
        self._throttling = throttling

    @classmethod
    def empty(cls) -> "AuthenticationService":
        """Return a service without administrator accounts."""

        return cls(
            {},
            throttling=ThrottlingSettings(
                max_attempts=5, window_seconds=60, lockout_seconds=300
            ),
        )

    @classmethod
    def load_from_file(cls, path: Path) -> "AuthenticationService":
        """Create a service instance from a JSON credentials file."""

        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("credentials file must contain an object")
        admins_raw = raw.get("admins")
        if not isinstance(admins_raw, list):
            raise ValueError("admins section must be a list")
        throttling_raw = raw.get("throttling")
        if not isinstance(throttling_raw, dict):
            raise ValueError("throttling section must be an object")

        try:
            throttling = ThrottlingSettings(
                max_attempts=int(throttling_raw["max_attempts"]),
                window_seconds=int(throttling_raw["window_seconds"]),
                lockout_seconds=int(throttling_raw["lockout_seconds"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid throttling configuration") from exc

        if throttling.max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if throttling.window_seconds < 1:
            raise ValueError("window_seconds must be positive")
        if throttling.lockout_seconds < 0:
            raise ValueError("lockout_seconds must be non-negative")

        credentials: dict[str, AdminCredential] = {}
        for entry in admins_raw:
            if not isinstance(entry, dict):
                raise ValueError("admin entry must be an object")
            username = entry.get("username")
            password_hash = entry.get("password_hash")
            permissions_raw = entry.get("permissions")
            if not isinstance(username, str) or not username:
                raise ValueError("username must be a non-empty string")
            if not isinstance(password_hash, str) or not password_hash:
                raise ValueError("password_hash must be a non-empty string")
            if not isinstance(permissions_raw, list) or not all(
                isinstance(permission, str) and permission
                for permission in permissions_raw
            ):
                raise ValueError("permissions must be a non-empty list of strings")
            if username in credentials:
                raise ValueError(f"duplicate administrator {username!r}")
            credentials[username] = AdminCredential(
                username=username,
                password_hash=password_hash,
                permissions=tuple(permissions_raw),
            )

        return cls(credentials, throttling=throttling)

    def authenticate(self, username: str, password: str) -> AuthenticatedAdmin:
        """Validate credentials, applying throttling and returning claims."""

        credential = self._credentials.get(username)
        now = self._now()
        if credential is None:
            logger.warning(
                "login failed",
                extra={"username": username, "reason": "unknown_user"},
            )
            raise AuthenticationError("invalid username or password")

        if credential.locked_until and now < credential.locked_until:
            logger.warning(
                "login throttled",
                extra={
                    "username": username,
                    "reason": "locked",  # noqa: ERA001 - structured logging key
                    "locked_until": credential.locked_until.isoformat(),
                },
            )
            raise ThrottlingError("too many login attempts")

        self._prune_attempts(credential, now)

        if not verify_password(password, credential.password_hash):
            self._register_failed_attempt(credential, now)
            logger.warning(
                "login failed",
                extra={"username": username, "reason": "invalid_password"},
            )
            raise AuthenticationError("invalid username or password")

        credential.attempt_timestamps.clear()
        credential.locked_until = None
        logger.info(
            "login succeeded",
            extra={"username": username, "reason": "authenticated"},
        )
        return AuthenticatedAdmin(
            username=credential.username, permissions=credential.permissions
        )

    def _register_failed_attempt(
        self, credential: AdminCredential, now: datetime
    ) -> None:
        credential.attempt_timestamps.append(now)
        if len(credential.attempt_timestamps) < self._throttling.max_attempts:
            return
        credential.locked_until = now + timedelta(
            seconds=self._throttling.lockout_seconds
        )
        credential.attempt_timestamps.clear()
        logger.warning(
            "login throttled",
            extra={
                "username": credential.username,
                "reason": "threshold_exceeded",  # noqa: ERA001 - structured logging key
                "locked_until": credential.locked_until.isoformat()
                if credential.locked_until
                else None,
            },
        )
        raise ThrottlingError("too many login attempts")

    def _prune_attempts(self, credential: AdminCredential, now: datetime) -> None:
        cutoff = now - timedelta(seconds=self._throttling.window_seconds)
        while (
            credential.attempt_timestamps and credential.attempt_timestamps[0] < cutoff
        ):
            credential.attempt_timestamps.popleft()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)


__all__ = [
    "AdminCredential",
    "AuthenticatedAdmin",
    "AuthenticationError",
    "AuthenticationService",
    "SecurityService",
    "ThrottlingError",
    "ThrottlingSettings",
]
