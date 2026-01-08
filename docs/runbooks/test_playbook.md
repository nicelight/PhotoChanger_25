# Test Playbook — PhotoChanger (KISS)

>  см. в `spec/docs/test-plan.md`.

## Цель
Быстрый, воспроизводимый прогон тестов перед релизом/демо. Основан на  `spec/docs/test-plan.md`(контекст и стратегия тестирования), покрывает API, UI и cron.

## Подготовка (Local/Staging)
- Переменные: `DATABASE_URL`, `MEDIA_ROOT`, `JWT_SIGNING_KEY`, `GEMINI_API_KEY`, `TURBOTEXT_API_KEY`, `RESULT_TTL_HOURS` (72), `TEMP_TTL_SECONDS` (10–60).
- Запусти БД (docker-compose или целевая инстанция), очисти/инициализируй таблицы при необходимости.
- Подними приложение: `uvicorn src.app.main:app --reload` (или gunicorn/uvicorn на staging).
- Убедись, что `media/results` и `media/temp` доступны на запись.

## Шаги тестирования
1) **Статика/линт/типы (обязательно)**
   - `ruff check .`
   - `black --check .`
   - `mypy src/`
2) **Unit/интеграция backend**
   - `py -m pytest tests/unit`
   - (опционально быстро) `py -m pytest tests/unit/slots tests/unit/settings tests/unit/auth`
3) **Контракты провайдеров и публичные ссылки**
   - `py -m pytest tests/unit/providers`
   - `py -m pytest tests/unit/public tests/unit/media/test_public_result_service.py`
4) **UI smoke (ручной или Playwright при наличии)**
   - Логин: `/ui/static/admin/login.html` → получить JWT.
   - Слоты: открыть `slot-001.html`, оставить пустое название/промпт → увидеть подсветку 422; заполнить валидно → `PUT /api/slots/{id}` 200; выполнить Test1 (ожидание статус ok).
   - Настройки: `/ui/static/admin/settings.html`, ввести некорректный `sync_response_seconds` (ожидаем подсветку), затем валидные TTL + ключи провайдеров → 200, статус «Настройки сохранены».
   - Статистика: `/ui/stats` с JWT → загрузка overview/slots без 401/5xx, таблица и графики заполнены.
5) **Приёмочные сценарии (ручные, опора на AC/UC)**
   - Успешный ingest `POST /api/ingest/{slot}` (JPEG/WebP) ≤ `T_sync_response`, результат доступен по `/public/results/{job_id}`.
   - Таймаут провайдера → 504 + `failure_reason=provider_timeout`, temp-файл очищен, recent_results не содержит результата.
   - Публичные ссылки: существующий job → 200/скачивание; просроченный → 410; несуществующий → 404 без утечки путей.
   - Cron: `python scripts/cleanup_media.py --dry-run` (или без) на тестовом каталоге → просрочка удалена, ошибок нет.
6) **Staging smoke перед релизом**
   - Health: `GET /healthz` 200, проверки БД/FS/провайдеров зелёные.
   - Метрики: `GET /metrics` доступен, есть p95/504/share, размер `media/`.
   - Быстрый UI-раунд (логин → слоты → настройки → статистика) с реальными мок-ключами.
7) **Диагностика Gemini на сервере (логи)**
   - Найти ответы без inline_data и причины:
     - `docker compose logs app --since=168h | grep -E "gemini.response.no_inline_data|gemini.response.no_image|finishMessage|finishReason|SAFETY"`
   - Посмотреть текстовые ответы модели (если есть):
     - `docker compose logs app --since=168h | grep -E "gemini.response.body|gemini.response.received"`
   - Проверить ретраи при `NO_IMAGE` (количество попыток и причины):
     - `docker compose logs app --since=168h | grep -E "gemini.response.no_image|finishReason|finish_reason"`

## Выходные артефакты
- Логи команд (ruff/black/mypy/pytest), скрин или краткая запись ручных smoke шагов.
- При дефектах: завести запись в `.memory/WORKLOG.md` и добавить задачу в `.memory/TASKS.md`/ASKS по согласованию.

helloWorld
