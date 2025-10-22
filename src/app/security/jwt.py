"""Minimal JWT helpers used for issuing admin access tokens."""

from __future__ import annotations

import base64
import hmac
import json
from hashlib import sha256
from typing import Any, Mapping


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def encode_jwt(claims: Mapping[str, Any], secret: str, *, algorithm: str = "HS256") -> str:
    """Return a compact JWT string signed with HS256."""

    if algorithm != "HS256":  # pragma: no cover - defensive branch
        raise ValueError(f"unsupported algorithm: {algorithm}")
    header = {"alg": algorithm, "typ": "JWT"}
    header_segment = _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_segment = _b64encode(
        json.dumps(dict(claims), separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, sha256).digest()
    signature_segment = _b64encode(signature)
    return f"{header_segment}.{payload_segment}.{signature_segment}"


def decode_jwt(token: str, secret: str, *, algorithm: str = "HS256") -> dict[str, Any]:
    """Decode and verify a JWT signed with HS256."""

    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError as exc:  # pragma: no cover - defensive branch
        raise ValueError("invalid token format") from exc
    header_bytes = _b64decode(header_segment)
    payload_bytes = _b64decode(payload_segment)
    signature = _b64decode(signature_segment)
    header = json.loads(header_bytes)
    if header.get("alg") != algorithm:
        raise ValueError("unexpected signing algorithm")
    expected = hmac.new(
        secret.encode("utf-8"),
        f"{header_segment}.{payload_segment}".encode("ascii"),
        sha256,
    ).digest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError("invalid token signature")
    payload = json.loads(payload_bytes)
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    return payload


__all__ = ["encode_jwt", "decode_jwt"]
