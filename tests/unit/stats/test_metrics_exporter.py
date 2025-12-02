from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.app.stats.metrics_api import router as metrics_router
from src.app.stats.metrics_exporter import (
    DurationSample,
    MetricsSnapshot,
    SlotTotals,
    format_prometheus,
)


def test_format_prometheus_renders_counters_and_histogram() -> None:
    snapshot = MetricsSnapshot(
        totals=[
            SlotTotals(
                slot_id="slot-001",
                provider="gemini",
                jobs_total=5,
                timeouts_total=1,
                provider_errors_total=2,
                success_total=3,
            )
        ],
        durations=[
            DurationSample(slot_id="slot-001", provider="gemini", seconds=1.0),
            DurationSample(slot_id="slot-001", provider="gemini", seconds=6.5),
        ],
        media_usage_bytes=1024,
        media_capacity_bytes=2048,
        window_minutes=5,
        sync_response_seconds=48,
    )

    text = format_prometheus(snapshot)

    assert (
        'ingest_requests_total{slot_id="slot-001",provider="gemini"} 5'
        in text
    )
    assert (
        'ingest_duration_seconds_bucket{slot_id="slot-001",provider="gemini",le="5"} 1'
        in text
    )
    assert (
        'ingest_duration_seconds_bucket{slot_id="slot-001",provider="gemini",le="+Inf"} 2'
        in text
    )
    assert "media_storage_bytes 1024" in text
    assert "media_disk_capacity_bytes 2048" in text


def test_metrics_router_uses_exporter_from_state() -> None:
    class StubExporter:
        def __init__(self) -> None:
            self.called = False

        def collect(self, window_minutes: int = 5) -> str:  # noqa: ARG002
            self.called = True
            return "ok"

    stub = StubExporter()
    app = FastAPI()
    app.state.metrics_exporter = stub
    app.include_router(metrics_router)
    client = TestClient(app)

    resp = client.get("/metrics")

    assert resp.status_code == 200
    assert resp.text == "ok"
    assert stub.called
    assert resp.headers["content-type"].startswith("text/plain")
