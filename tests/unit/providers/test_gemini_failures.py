
import pytest
import asyncio
from src.app.providers.providers_gemini import GeminiDriver, ProviderExecutionError
from src.app.ingest.ingest_models import JobContext
from src.app.repositories.media_object_repository import MediaObjectRepository
from unittest.mock import MagicMock

class DummyResponse:
    def __init__(self, status_code: int, json_data: dict):
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        return self._json_data

class DummyAsyncClient:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def post(self, url, headers, json):
        return self.response

@pytest.fixture
def mock_driver(monkeypatch):
    repo = MagicMock(spec=MediaObjectRepository)
    driver = GeminiDriver(media_repo=repo)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    return driver

@pytest.fixture
def job_context(tmp_path):
    job = JobContext(slot_id="slot-001")
    job.job_id = "test-job"
    job.temp_payload_path = tmp_path / "payload.png"
    job.temp_payload_path.write_bytes(b"data")
    job.slot_settings = {"prompt": "test"}
    return job

@pytest.mark.asyncio
async def test_text_response_error(monkeypatch, mock_driver, job_context):
    response_data = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Safety violation"}]
                },
                "finishReason": "SAFETY"
            }
        ]
    }
    
    client = DummyAsyncClient(DummyResponse(200, response_data))
    monkeypatch.setattr("httpx.AsyncClient", lambda timeout: client)
    
    with pytest.raises(ProviderExecutionError) as excinfo:
        await mock_driver.process(job_context)
    
    assert "Gemini response does not contain inline data" in str(excinfo.value)
    assert "Text: Safety violation" in str(excinfo.value)
    assert "Reasons: SAFETY" in str(excinfo.value)

@pytest.mark.asyncio
async def test_multiple_candidates_text_error(monkeypatch, mock_driver, job_context):
    response_data = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Attempt 1 failed"}]
                },
                "finishReason": "OTHER"
            },
            {
                "content": {
                    "parts": [{"text": "Attempt 2 failed"}]
                },
                "finishReason": "STOP"
            }
        ]
    }
    
    client = DummyAsyncClient(DummyResponse(200, response_data))
    monkeypatch.setattr("httpx.AsyncClient", lambda timeout: client)
    
    with pytest.raises(ProviderExecutionError) as excinfo:
        await mock_driver.process(job_context)
    
    msg = str(excinfo.value)
    assert "Reasons: OTHER, STOP" in msg
    assert "Text: Attempt 1 failed; Attempt 2 failed" in msg

