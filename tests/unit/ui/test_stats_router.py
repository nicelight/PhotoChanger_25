import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:  # pragma: no cover
    sys.path.append(str(ROOT))

from src.app.ui.stats_router import router  # noqa: E402


def test_stats_page_served() -> None:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get("/ui/stats")

    assert response.status_code == 200
    assert "<!doctype html>" in response.text.lower()
