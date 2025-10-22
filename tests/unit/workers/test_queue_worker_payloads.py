"""Tests for :meth:`QueueWorker._load_job_context` payload handling."""

from __future__ import annotations

import json
from datetime import datetime, timezone
import sys
import types
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest

if "jsonschema" not in sys.modules:
    jsonschema_stub = types.ModuleType("jsonschema")

    class _Draft202012Validator:  # pragma: no cover - infrastructure stub
        def __init__(self, schema: object) -> None:
            self.schema = schema

        def iter_errors(self, payload: object):  # noqa: D401 - simple stub
            return []

    jsonschema_stub.Draft202012Validator = _Draft202012Validator
    sys.modules["jsonschema"] = jsonschema_stub

from src.app.domain.models import Job, JobStatus
from src.app.workers.queue_worker import QueueWorker


def _make_job(*, payload_path: Path | None) -> Job:
    now = datetime.now(timezone.utc)
    return Job(
        id=uuid4(),
        slot_id="slot-1",
        status=JobStatus.PENDING,
        is_finalized=False,
        failure_reason=None,
        expires_at=now,
        created_at=now,
        updated_at=now,
        payload_path=str(payload_path) if payload_path else None,
    )


def _make_worker() -> QueueWorker:
    return QueueWorker(
        job_service=Mock(name="job_service"),
        slot_service=Mock(name="slot_service"),
        media_service=Mock(name="media_service"),
        settings_service=Mock(name="settings_service"),
        provider_factories={},
    )


def test_load_job_context_reads_json_payload(tmp_path: Path) -> None:
    payload = tmp_path / "payload.json"
    payload.write_text(
        json.dumps({"provider_context": {"prompt": "Render portrait"}}),
        encoding="utf-8",
    )
    worker = _make_worker()
    job = _make_job(payload_path=payload)

    context = worker._load_job_context(job)

    assert context == {"prompt": "Render portrait"}


def test_load_job_context_ignores_binary_payload(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    payload = tmp_path / "image.png"
    payload.write_bytes(b"\x89PNG\r\n\x1a\n")
    worker = _make_worker()
    job = _make_job(payload_path=payload)

    with caplog.at_level("WARNING"):
        context = worker._load_job_context(job)

    assert context == {}
    assert not [record for record in caplog.records if record.levelname == "WARNING"]
