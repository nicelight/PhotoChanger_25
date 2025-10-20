"""Contract tests covering ingest endpoint behaviour."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from fastapi import status


@pytest.mark.contract
def test_ingest_returns_inline_result(
    contract_app,
    contract_client,
    ingest_payload,
    fake_job_queue,
):
    """Successful ingest must stream inline binary data back to the client."""

    fake_job_queue.auto_finalize_inline = ingest_payload["image_bytes"]
    fake_job_queue.auto_finalize_mime = ingest_payload["mime"]

    response = contract_client.post(
        "/ingest/slot-001",
        data=ingest_payload["data"],
        files=ingest_payload["files_with_unsafe_name"],
    )

    assert response.status_code == status.HTTP_200_OK
    job_id = response.headers["x-job-id"]
    UUID(job_id)
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["content-length"] == str(len(ingest_payload["image_bytes"]))
    assert response.headers["cache-control"] == "no-store"
    assert response.content == ingest_payload["image_bytes"]

    stored_job = fake_job_queue.domain_jobs[job_id]
    assert stored_job.is_finalized is True
    assert stored_job.failure_reason is None
    assert stored_job.result_inline_base64 is None
    assert stored_job.payload_path is not None
    assert Path(stored_job.payload_path).name == ingest_payload["sanitized_filename"]

    media_root: Path = contract_app.state.config.media_root
    payload_path = media_root / stored_job.payload_path
    assert not payload_path.exists()
    fake_job_queue.auto_finalize_inline = None


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


@pytest.mark.contract
def test_ingest_returns_queue_busy_error(
    contract_client,
    ingest_payload,
    validate_with_schema,
    fake_job_queue,
    contract_app,
):
    """429 is returned when the queue reports saturation."""

    fake_job_queue.raise_busy = True
    try:
        response = contract_client.post(
            "/ingest/slot-001",
            data=ingest_payload["data"],
            files=ingest_payload["files"],
        )
    finally:
        fake_job_queue.raise_busy = False

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    payload_json = response.json()
    validate_with_schema(payload_json, "Error.json")
    assert payload_json["error"]["code"] == "queue_busy"
    assert response.headers["cache-control"] == "no-store"

    media_root: Path = contract_app.state.config.media_root
    payload_dir = media_root / "payloads"
    assert not any(path.is_file() for path in payload_dir.rglob("*"))


@pytest.mark.contract
def test_ingest_times_out_when_worker_unavailable(
    contract_client,
    ingest_payload,
    validate_with_schema,
    fake_job_queue,
    contract_app,
):
    """504 is returned when no worker finalises the job within the timeout window."""

    fake_job_queue.auto_finalize_inline = None

    response = contract_client.post(
        "/ingest/slot-001",
        data=ingest_payload["data"],
        files=ingest_payload["files"],
    )

    assert response.status_code == status.HTTP_504_GATEWAY_TIMEOUT
    payload_json = response.json()
    validate_with_schema(payload_json, "Error.json")
    assert payload_json["error"]["code"] == "sync_timeout"
    assert "job_id" in payload_json["error"]["details"]
    assert "expires_at" in payload_json["error"]["details"]
    assert response.headers["cache-control"] == "no-store"
    job_id = payload_json["error"]["details"]["job_id"]
    stored_job = fake_job_queue.domain_jobs[job_id]
    assert stored_job.failure_reason is not None
    assert stored_job.failure_reason.value == "timeout"

    media_root: Path = contract_app.state.config.media_root
    payload_dir = media_root / "payloads" / job_id
    assert not any(path.is_file() for path in payload_dir.rglob("*"))
