"""Utility helpers for hashing and verifying ingest passwords."""

from __future__ import annotations

import binascii
import hashlib
import hmac
from dataclasses import dataclass

DEFAULT_ALGORITHM = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 390_000


@dataclass(slots=True)
class PasswordHash:
    """Structured representation of a PBKDF2 hash entry."""

    algorithm: str
    iterations: int
    salt: bytes
    digest: bytes

    @classmethod
    def parse(cls, encoded: str) -> "PasswordHash":
        """Parse an encoded password hash string."""

        try:
            algorithm, iterations, salt_hex, digest_hex = encoded.split("$")
        except ValueError as exc:  # pragma: no cover - defensive branch
            raise ValueError("invalid password hash format") from exc
        iterations_int = int(iterations)
        salt = binascii.unhexlify(salt_hex)
        digest = binascii.unhexlify(digest_hex)
        return cls(
            algorithm=algorithm,
            iterations=iterations_int,
            salt=salt,
            digest=digest,
        )

    def verify(self, password: str) -> bool:
        """Check ``password`` against the stored digest using constant time."""

        if self.algorithm != DEFAULT_ALGORITHM:
            raise ValueError(f"unsupported algorithm: {self.algorithm}")
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            self.salt,
            self.iterations,
        )
        return hmac.compare_digest(derived, self.digest)


def verify_password(password: str, encoded: str) -> bool:
    """Return ``True`` when ``password`` matches ``encoded`` hash."""

    if not encoded:
        return False
    parsed = PasswordHash.parse(encoded)
    return parsed.verify(password)


__all__ = ["PasswordHash", "verify_password"]
