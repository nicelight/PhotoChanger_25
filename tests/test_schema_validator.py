"""Tests for the schema validation helpers used by contract fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import SchemaLoader, SimpleSchemaValidator


def _job_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "00000000-0000-0000-0000-000000000001",
        "slot_id": "slot-001",
        "status": "pending",
        "is_finalized": False,
        "expires_at": "2025-01-01T00:00:00Z",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }
    payload.update(overrides)
    return payload


def test_job_failure_reason_accepts_enum(schema_loader: SchemaLoader) -> None:
    """Values allowed by the schema should pass validation."""

    validator = SimpleSchemaValidator(schema_loader)
    payload = _job_payload(failure_reason="timeout")

    validator(payload, "Job.json")


def test_job_failure_reason_rejects_invalid_value(schema_loader: SchemaLoader) -> None:
    """The validator must reject values outside the enumerated oneOf options."""

    validator = SimpleSchemaValidator(schema_loader)
    payload = _job_payload(failure_reason="definitely-not-supported")

    with pytest.raises(AssertionError, match="does not match exactly one schema in oneOf"):
        validator(payload, "Job.json")


def test_one_of_raises_when_multiple_schemas_match(schema_loader: SchemaLoader) -> None:
    """Exactly one sub-schema must match a ``oneOf`` declaration."""

    validator = SimpleSchemaValidator(schema_loader)
    schema = {"oneOf": [{"type": "string"}, {"pattern": "^foo"}]}

    with pytest.raises(AssertionError, match="matches multiple oneOf schemas"):
        validator._validate("foo", schema, Path("inline.json"), "$")
