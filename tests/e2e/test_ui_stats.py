from __future__ import annotations

import json
import os
import threading
import time

import httpx
import pytest
from uvicorn import Config, Server

from src.app.main import app

playwright_mod = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # type: ignore  # noqa: E402


def _obtain_token(base_url: str) -> str:
    response = httpx.post(
        f"{base_url}/api/login",
        json={"username": "serg", "password": "admin123"},
        timeout=5.0,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _start_uvicorn_server(port: int) -> tuple[Server, threading.Thread]:
    config = Config(app=app, host="127.0.0.1", port=port, log_level="warning")
    server = Server(config=config)
    server.install_signal_handlers = lambda: None  # type: ignore[assignment]
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.1)
    return server, thread


@pytest.fixture(scope="session")
def e2e_server() -> str:
    port = int(os.getenv("E2E_SERVER_PORT", "8123"))
    server, thread = _start_uvicorn_server(port)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)


@pytest.mark.e2e
def test_stats_page_happy_path(e2e_server: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        token = _obtain_token(e2e_server)
        page = browser.new_page()
        page.add_init_script(
            f"""
() => {{
    try {{
        window.localStorage.setItem('photochanger.jwt', {json.dumps(token)});
    }} catch (error) {{
        console.error('Failed to store token', error);
    }}
}}
"""
        )

        page.goto(f"{e2e_server}/ui/stats", wait_until="networkidle")
        heading = page.locator("h1")
        heading.wait_for(state="visible", timeout=5000)
        assert "Статистика AI-слотов" in heading.inner_text()

        window_input = page.locator("#window-minutes")
        window_input.fill("10")
        page.locator("#refresh-button").click()

        summary_chip = page.locator("#summary-window")
        summary_chip.wait_for(state="visible", timeout=5000)
        summary_text = summary_chip.inner_text()
        assert "Окно" in summary_text
        assert "мин" in summary_text

        table_rows = page.locator("#slots-table-body tr")
        assert table_rows.count() >= 1

        chart_items = page.locator("#slots-chart li")
        assert chart_items.count() >= 1

        failure_rows = page.locator("#failures-table-body tr")
        assert failure_rows.count() >= 1

        browser.close()
