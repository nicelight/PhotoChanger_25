"""Contract tests covering ingest endpoint behaviour."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from fastapi import status


@pytest.mark.contract
def test_ingest_enqueues_job_and_persists_payload(
    contract_app,
    contract_client,
    ingest_payload,
    fake_job_queue,
):
    """Valid ingest request must store payload and enqueue a job."""

    response = contract_client.post(
        "/ingest/slot-001",
        data=ingest_payload["data"],
        files=ingest_payload["files"],
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert "x-job-id" in response.headers
    job_id = response.headers["x-job-id"]
    UUID(job_id)

    stored_job = fake_job_queue.domain_jobs[job_id]
    assert stored_job.slot_id == "slot-001"
    assert stored_job.payload_path is not None

    media_root: Path = contract_app.state.config.media_root
    payload_path = media_root / stored_job.payload_path
    assert payload_path.exists()
    assert payload_path.read_bytes() == ingest_payload["image_bytes"]


@pytest.mark.contract
def test_ingest_rejects_invalid_password(
    contract_client,
    ingest_payload,
    validate_with_schema,
):
    """401 is returned when ingest password is invalid."""

    request_data = {
        "data": {"password": "wrong-password"},
        "files": ingest_payload["files"],
    }

    response = contract_client.post(
        "/ingest/slot-001",
        data=request_data["data"],
        files=request_data["files"],
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    payload_json = response.json()
    validate_with_schema(payload_json, "Error.json")
    assert payload_json["error"]["code"] == "invalid_credentials"


@pytest.mark.contract
def test_ingest_rejects_unknown_slot(
    contract_client,
    ingest_payload,
    validate_with_schema,
):
    """404 is returned when slot is not found."""

    response = contract_client.post(
        "/ingest/slot-015",
        data=ingest_payload["data"],
        files=ingest_payload["files"],
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    payload_json = response.json()
    validate_with_schema(payload_json, "Error.json")
    assert payload_json["error"]["code"] == "slot_not_found"


@pytest.mark.contract
def test_ingest_rejects_unsupported_mime(
    contract_client,
    ingest_payload,
    validate_with_schema,
):
    """Unsupported MIME types must return 415."""

    files = {"fileToUpload": ("test.txt", ingest_payload["image_bytes"], "text/plain")}
    response = contract_client.post(
        "/ingest/slot-001",
        data=ingest_payload["data"],
        files=files,
    )

    assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    payload_json = response.json()
    validate_with_schema(payload_json, "Error.json")
    assert payload_json["error"]["code"] == "unsupported_media_type"


@pytest.mark.contract
def test_ingest_rejects_empty_payload(
    contract_client,
    ingest_payload,
    validate_with_schema,
):
    """Zero-byte files must trigger a 400 validation error."""

    files = {"fileToUpload": ("empty.jpg", b"", "image/jpeg")}
    response = contract_client.post(
        "/ingest/slot-001",
        data=ingest_payload["data"],
        files=files,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    payload_json = response.json()
    validate_with_schema(payload_json, "Error.json")
    assert payload_json["error"]["code"] == "invalid_payload"


@pytest.mark.contract
def test_ingest_enforces_payload_size_limit(
    contract_client,
    ingest_payload,
    monkeypatch,
    validate_with_schema,
):
    """Payloads exceeding limit produce 413 errors."""

    monkeypatch.setattr(
        "src.app.api.routes.ingest.MAX_PAYLOAD_BYTES",
        1,
    )

    response = contract_client.post(
        "/ingest/slot-001",
        data=ingest_payload["data"],
        files=ingest_payload["files"],
    )

    assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    payload_json = response.json()
    validate_with_schema(payload_json, "Error.json")
    assert payload_json["error"]["code"] == "payload_too_large"
