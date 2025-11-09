---
title: Local Stats UI Runbook
updated: 2025-11-09
---

# Запуск страницы статистики локально

## Цель
Быстро поднять FastAPI-приложение и посмотреть дашборд `/ui/stats`, который использует REST эндпоинты `/api/stats/overview` и `/api/stats/slots`.

## Предпосылки
- Python 3.11+ и виртуальное окружение (например, `.venv`).
- Установленные зависимости `pip install -r requirements.txt`.
- Локальная БД (по умолчанию `sqlite:///photochanger.db` создаётся автоматически) + директория `media/`.

## Шаги
1. **Подготовка среды**  
   ```bash
   uv venv .venv         # или python -m venv .venv
   source .venv/Scripts/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
2. **Запуск приложения**  
   ```bash
   uvicorn src.app.main:app --reload --log-level info
   ```
   По умолчанию сервис доступен на `http://127.0.0.1:8000`.
3. **Проверка API** (опционально):  
   ```bash
   curl "http://127.0.0.1:8000/api/stats/overview?window_minutes=60"
   curl "http://127.0.0.1:8000/api/stats/slots?window_minutes=60"
   ```
4. **Просмотр UI**  
   Откройте браузер по адресу `http://127.0.0.1:8000/ui/stats`.  
   Кнопка «Обновить» запрашивает оба эндпоинта и отрисовывает карточки, таблицу SLA и графики.

## Тестовые данные
- Страница корректно работает даже на пустой базе: показатели будут по нулям.
- Для проверки non-zero значений можно вручную вставить записи в `job_history` (статусы `done`/`timeout`) или прогнать unit/integration тесты ingest — они создают фиктивные записи.

## E2E тест (Playwright)
1. Установите браузеры Playwright (один раз после установки пакета):
   ```bash
   playwright install chromium
   ```
2. Запустите e2e тест (сервер стартует автоматически внутри теста):
   ```bash
   py -m pytest tests/e2e/test_ui_stats.py
   ```
   Тест поднимает uvicorn на `127.0.0.1:8123`, открывает `/ui/stats`, меняет окно на 10 минут и проверяет, что таблица и графики появились.

## Troubleshooting
- **404 на `/ui/stats`** — убедитесь, что `frontend/stats/index.html` существует и приложение было перезапущено (FastAPI читает HTML с диска).
- **Пустые таблицы/графики** — в окне нет активных слотов; уменьшите `window_minutes` до 5 или создайте тестовые записи в `job_history`.
- **Ассеты не грузятся** — маршруты `/ui/static/...` должны раздавать каталог `frontend/`; проверьте логи uvicorn и права доступа к файлам.
