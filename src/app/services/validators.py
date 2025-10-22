from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from jsonschema import Draft202012Validator

from ..domain.models import ProcessingLog

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_PATH = _PROJECT_ROOT / "spec" / "contracts" / "schemas" / "processing_log.json"


def _normalize_detail_value(value: object) -> object:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _to_contract_payload(log: ProcessingLog) -> dict[str, Any]:
    details = None
    if log.details is not None:
        details = {
            str(key): _normalize_detail_value(value)
            for key, value in log.details.items()
        }
    return {
        "id": str(log.id),
        "job_id": str(log.job_id),
        "slot_id": log.slot_id,
        "status": log.status.value,
        "occurred_at": log.occurred_at.isoformat(),
        "message": log.message,
        "provider_latency_ms": log.provider_latency_ms,
        "details": details,
    }


class ProcessingLogValidator:
    """Validate :class:`ProcessingLog` instances against the public contract."""

    def __init__(self, schema_path: Path | None = None) -> None:
        path = schema_path or _SCHEMA_PATH
        schema = json.loads(path.read_text(encoding="utf-8"))
        self._validator = Draft202012Validator(schema)

    def validate(self, log: ProcessingLog) -> None:
        payload = _to_contract_payload(log)
        errors = sorted(self._validator.iter_errors(payload), key=lambda err: err.path)
        if errors:
            first = errors[0]
            location = "/".join(str(part) for part in first.path) or "$"
            raise ValueError(
                f"ProcessingLog contract violation at {location}: {first.message}"
            )

    def serialize(self, log: ProcessingLog) -> dict[str, Any]:
        """Return the JSON-serialisable payload used for validation."""

        return _to_contract_payload(log)


default_processing_log_validator = ProcessingLogValidator()

__all__ = ["ProcessingLogValidator", "default_processing_log_validator"]
