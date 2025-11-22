"""Admin authentication and JWT issuance."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import jwt
from jwt import ExpiredSignatureError
from jwt import InvalidTokenError as PyJWTInvalidTokenError
import structlog


logger = structlog.get_logger(__name__)


def _utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(tz=timezone.utc)


def hash_password(value: str) -> str:
    """Return hex sha256 hash for the provided password."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class AdminCredential:
    """Single admin record loaded from runtime_credentials.json."""

    username: str
    password_hash: str
    scope: str = "admin"
    disabled: bool = False

    def verify(self, password: str) -> bool:
        return not self.disabled and self.password_hash == hash_password(password)


@dataclass(slots=True)
class FailedLoginState:
    """Tracks consecutive failures and throttle window per username."""

    failures: int = 0
    blocked_until: datetime | None = None


class AuthError(Exception):
    """Base class for auth failures."""


class InvalidCredentialsError(AuthError):
    """Raised when username/password mismatch."""


class LoginThrottledError(AuthError):
    """Raised when user hit throttle limit."""


class InvalidTokenError(AuthError):
    """Raised when token cannot be decoded."""


class TokenExpiredError(AuthError):
    """Raised when token is expired."""


class InsufficientScopeError(AuthError):
    """Raised when token scope does not match requirement."""


@dataclass(slots=True)
class AuthService:
    """Authenticate static admins and issue JWT tokens."""

    credentials: dict[str, AdminCredential]
    signing_key: str
    token_ttl: timedelta
    scope: str = "admin"
    max_failures: int = 10
    block_duration: timedelta = timedelta(minutes=15)
    _failed_logins: dict[str, FailedLoginState] = field(default_factory=dict)

    @classmethod
    def from_file(
        cls,
        path: Path,
        signing_key: str,
        token_ttl_hours: int,
        scope: str = "admin",
    ) -> "AuthService":
        credentials = cls._load_credentials(path)
        ttl = timedelta(hours=token_ttl_hours)
        if not signing_key:
            raise RuntimeError("JWT_SIGNING_KEY is not configured")
        return cls(
            credentials=credentials, signing_key=signing_key, token_ttl=ttl, scope=scope
        )

    @staticmethod
    def _load_credentials(path: Path) -> dict[str, AdminCredential]:
        if not path.exists():
            raise FileNotFoundError(f"Admin credentials file not found: {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        admins = raw.get("admins", [])
        if not isinstance(admins, Iterable):
            raise ValueError(
                "Invalid admin credentials structure: 'admins' must be an array"
            )
        records: dict[str, AdminCredential] = {}
        for entry in admins:
            username = entry.get("username")
            password_hash = entry.get("password_hash")
            if not username or not password_hash:
                raise ValueError(
                    "Each admin entry must contain username and password_hash"
                )
            records[username] = AdminCredential(
                username=username,
                password_hash=password_hash,
                scope=entry.get("scope", "admin"),
                disabled=entry.get("disabled", False),
            )
        if not records:
            raise ValueError("No admin credentials configured")
        return records

    def authenticate(
        self, username: str, password: str, client_ip: str | None = None
    ) -> tuple[str, int]:
        """Validate credentials and return JWT token + ttl seconds."""
        now = _utcnow()
        state = self._failed_logins.get(username)
        if state and state.blocked_until and now < state.blocked_until:
            logger.warning(
                "auth.login.failure",
                username=username,
                reason="throttled",
                blocked_until=state.blocked_until.isoformat(),
                client_ip=client_ip,
            )
            raise LoginThrottledError("Too many attempts, try later")

        credential = self.credentials.get(username)
        if not credential or not credential.verify(password):
            self._register_failure(username, now)
            logger.warning(
                "auth.login.failure",
                username=username,
                reason="invalid_credentials",
                client_ip=client_ip,
            )
            raise InvalidCredentialsError("Invalid username or password")

        self._reset_failures(username)
        token = self._issue_token(username, now, credential.scope)
        expires_in = int(self.token_ttl.total_seconds())
        logger.info(
            "auth.login.success",
            username=username,
            client_ip=client_ip,
            expires_in=expires_in,
        )
        return token, expires_in

    def _register_failure(self, username: str, now: datetime) -> None:
        state = self._failed_logins.get(username)
        if not state:
            state = FailedLoginState()
            self._failed_logins[username] = state
        state.failures += 1
        if state.failures >= self.max_failures:
            state.failures = 0
            state.blocked_until = now + self.block_duration
        else:
            state.blocked_until = None

    def _reset_failures(self, username: str) -> None:
        self._failed_logins.pop(username, None)

    def _issue_token(self, username: str, issued_at: datetime, scope: str) -> str:
        payload: dict[str, Any] = {
            "sub": username,
            "scope": scope,
            "iat": int(issued_at.timestamp()),
            "exp": int((issued_at + self.token_ttl).timestamp()),
        }
        return jwt.encode(payload, self.signing_key, algorithm="HS256")

    def validate_token(
        self, token: str, required_scope: str | None = None
    ) -> dict[str, Any]:
        """Decode JWT and ensure scope matches requirement."""
        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                self.signing_key,
                algorithms=["HS256"],
                options={"require": ["exp", "iat", "sub", "scope"]},
            )
        except ExpiredSignatureError as exc:
            raise TokenExpiredError("Token expired") from exc
        except PyJWTInvalidTokenError as exc:
            raise InvalidTokenError("Invalid token") from exc

        scope = payload.get("scope")
        if required_scope and scope != required_scope:
            raise InsufficientScopeError("Insufficient scope")
        return payload


__all__ = [
    "AdminCredential",
    "AuthService",
    "AuthError",
    "InvalidCredentialsError",
    "LoginThrottledError",
    "InvalidTokenError",
    "TokenExpiredError",
    "InsufficientScopeError",
    "hash_password",
]
