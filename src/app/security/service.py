"""High level security helpers used by application services."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

from .passwords import DEFAULT_ALGORITHM, DEFAULT_ITERATIONS, verify_password


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
