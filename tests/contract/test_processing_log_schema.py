from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator, ValidationError

from src.app.domain.models import ProcessingLog, ProcessingStatus
from src.app.services.validators import ProcessingLogValidator


@pytest.mark.contract
def test_processing_log_schema_accepts_valid_payload(schema_loader) -> None:
    schema, schema_path = schema_loader.load('processing_log.json')
    validator = Draft202012Validator(schema)
    log = ProcessingLog(
        id=uuid4(),
        job_id=uuid4(),
        slot_id='slot-001',
        status=ProcessingStatus.PROVIDER_RESPONDED,
        occurred_at=datetime(2025, 11, 5, 10, 15, 30, tzinfo=timezone.utc),
        message='Provider responded with result',
        details={'provider_id': 'gemini', 'provider_reference': 'gemini-job-123', 'attempt': 1},
        provider_latency_ms=1200,
    )
    payload = ProcessingLogValidator(schema_path=schema_path).serialize(log)

    validator.validate(payload)


@pytest.mark.contract
def test_processing_log_schema_rejects_invalid_payload(schema_loader) -> None:
    schema, schema_path = schema_loader.load('processing_log.json')
    validator = Draft202012Validator(schema)
    log = ProcessingLog(
        id=uuid4(),
        job_id=uuid4(),
        slot_id='slot-999',
        status=ProcessingStatus.RECEIVED,
        occurred_at=datetime(2025, 11, 5, 10, 0, 0, tzinfo=timezone.utc),
        message=None,
        details={'attempt': 0},
        provider_latency_ms=None,
    )
    payload = ProcessingLogValidator(schema_path=schema_path).serialize(log)
    payload['slot_id'] = 'invalid-slot'

    with pytest.raises(ValidationError):
        validator.validate(payload)

    payload['slot_id'] = 'slot-001'
    payload['details']['attempt'] = 0

    with pytest.raises(ValidationError):
        validator.validate(payload)
