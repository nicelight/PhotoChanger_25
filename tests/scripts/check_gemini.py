"""
Quick manual check for Gemini test-run flow against the local API.

Как запустить (из корня проекта):
    # активируй .venv и убедись, что установлен requests (pip install requests)
    set API_URL=http://127.0.0.1:8000
    set ADMIN_USER=serg
    set ADMIN_PASSWORD=admin123
    set SLOT_ID=slot-001
    set TEST_IMAGE_PATH=sample.png
    set PROMPT=Промпт для проверки
    python tests/scripts/check_gemini.py

Что делает скрипт:
    1) Берёт параметры из переменных окружения (см. выше) с разумными дефолтами.
    2) Логинится в /api/login, получает JWT.
    3) Отправляет multipart POST /api/slots/{slot_id}/test-run с:
         - slot_payload: provider=gemini, operation=identity_transfer, settings.prompt=PROMPT
         - test_image: файл с диска (TEST_IMAGE_PATH)
    4) Печатает HTTP-статус и тело ответа (или ошибку) в stdout, чтобы быстро понять, почему падает UI/Test1.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests


def env(name: str, default: str) -> str:
    return os.getenv(name, default)


def main() -> int:
    api_url = env("API_URL", "http://127.0.0.1:8000").rstrip("/")
    admin_user = env("ADMIN_USER", "serg")
    admin_password = env("ADMIN_PASSWORD", "admin123")
    slot_id = env("SLOT_ID", "slot-001")
    image_path = Path(env("TEST_IMAGE_PATH", "sample.png"))
    prompt = env("PROMPT", "Проверка Gemini через скрипт")

    if not image_path.exists():
        print(f"[error] test image not found: {image_path}")
        return 1

    try:
        login_resp = requests.post(
            f"{api_url}/api/login",
            json={"username": admin_user, "password": admin_password},
            timeout=10,
        )
    except Exception as exc:  # pragma: no cover - network errors
        print(f"[error] login request failed: {exc}")
        return 1

    if login_resp.status_code != 200:
        print(f"[error] login failed: {login_resp.status_code} {login_resp.text}")
        return 1

    token = login_resp.json().get("access_token")
    if not token:
        print(f"[error] login response missing token: {login_resp.text}")
        return 1

    payload = {
        "provider": "gemini",
        "operation": "identity_transfer",
        "settings": {"prompt": prompt},
    }

    files = {
        "slot_payload": (None, json.dumps(payload)),
        "test_image": (image_path.name, image_path.open("rb"), "image/png"),
    }

    try:
        resp = requests.post(
            f"{api_url}/api/slots/{slot_id}/test-run",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            timeout=120,
        )
    except Exception as exc:  # pragma: no cover - network errors
        print(f"[error] test-run request failed: {exc}")
        return 1

    print(f"[info] status: {resp.status_code}")
    try:
        print(json.dumps(resp.json(), ensure_ascii=False, indent=2))
    except Exception:
        print(resp.text)
    return 0 if resp.ok else 1


if __name__ == "__main__":
    sys.exit(main())
