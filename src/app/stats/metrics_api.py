"""Prometheus /metrics endpoint."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse

from .metrics_exporter import MetricsExporter


def get_metrics_exporter(request: Request) -> MetricsExporter:
    exporter = getattr(request.app.state, "metrics_exporter", None)
    if exporter is None:
        raise RuntimeError("Metrics exporter is not configured")
    return exporter


router = APIRouter()


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics(exp: MetricsExporter = Depends(get_metrics_exporter)) -> str:
    """Expose Prometheus metrics."""
    return exp.collect()
