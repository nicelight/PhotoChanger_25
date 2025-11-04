---
id: context
version: 1
updated: 2025-10-31
owner: techlead
---

# Устойчивый контекст

## Среды и развёртывания
- **Prod (план):** один Docker/VM-хост с FastAPI (uvicorn), PostgreSQL 15 и внешним cron `python scripts/cleanup_media.py` каждые 15 минут; общий том `media/`. Горизонтальное масштабирование не закладываем (ADR-0001).
- **Staging:** приёмочная среда для этапа Ops (PRD §12/E4) — тот же стек с мок-ключами провайдеров и прогоном health-check перед релизом.
- **Local:** `uvicorn src.app.main:app --reload` + локальная PostgreSQL (docker-compose). Итоговые файлы сохраняются в `./media/results` (payload + preview), шаблоны — в `./media/templates`; UI макеты лежат в `spec/docs/ui/frontend-examples/`.

## Стек и архитектура
- **Backend:** однопроцессное FastAPI-приложение на Python ≥ 3.11 (uvicorn). Конфигурация собирается через `AppConfig` (`app/main.py`), модули `ingest`, `media`, `slots`, `settings`, `stats` подключаются через `Depends`. `IngestService` ограничивает обработку `asyncio.wait_for(..., timeout=T_sync_response)`.
- **Provider drivers:** `GeminiDriver` и `TurbotextDriver` используют `httpx.AsyncClient`, соблюдают лимиты провайдеров и возвращают путь/байты результата.
- **Data stores:** PostgreSQL 15 (`slot`, `settings`, `job_history`, `media_object`) и файловая система `media/results` с `T_result_retention = 72 ч`. Входящие файлы буферизуются в памяти; очередей и фоновых воркеров нет (KISS, ADR-0001).
- **Frontend:** Админ-UI и публичная галерея — статические страницы/HTMX + Vanilla JS (шаблоны в `spec/docs/ui/frontend-examples/`), работают поверх REST (`/api/login`, `/api/slots`, `/api/settings`, `/api/stats`, `/public/results/{job_id}`).
- **Observability:** `structlog` для ingest/ошибок, Prometheus `/metrics`, `/healthz` проверяет БД, файловую систему и быстродоступность провайдеров.

## Конфигурация и секреты
- Переменные окружения (PRD §10):
  - `DATABASE_URL`
  - `MEDIA_ROOT`
  - `RESULT_TTL_HOURS` (72)
  - `TEMP_TTL_SECONDS` (`T_sync_response`, 10–60 с)
  - `JWT_SIGNING_KEY`
  - `GEMINI_API_KEY`, `TURBOTEXT_API_KEY`
- Пароли ingest и админов хранятся как хэши (`slot`, `secrets/runtime_credentials.json`); `.env` не коммитится.
- Реальные ключи хранятся во внешнем секрет-хранилище (Vault/1Password); в репозитории допускается только `.env.example`.

## Команды разработчика (pre-commit чек-лист)
- Линт: `ruff check .`
- Форматирование: `black .`
- Type-check: `mypy src/`
- Pytest-наборы:
  - unit-тесты сервисов модулей и драйверов провайдеров (pytest с фейковыми адаптерами);
  - интеграционные тесты FastAPI с временными каталогами и PostgreSQL (`pytest-postgresql`);
  - контрактные тесты провайдеров (мок-серверы Gemini/Turbotext);
  - тест `scripts/cleanup_media.py`.
- UI smoke (по мере готовности): Playwright/Cypress сценарии логина, редактирования слота, просмотра статистики.

## Политики качества и безопасности
- Строго придерживаемся KISS: монолит FastAPI + cron, без очередей и фоновых потоков (ADR-0001).
- `T_sync_response` конфигурируется в диапазоне 10–60 с; по превышению возвращаем 504 и удаляем временные файлы.
- Итоговые файлы доступны 72 ч (`RESULT_TTL_HOURS`); cron очищает `media/results` и обновляет `media_object.cleaned_at`.
- Ограничение загрузки ingest: по умолчанию 20 МБ (жёсткий предел сервиса).
- Логи не содержат бинарных payload/секретов; события авторизации логируются как `auth.login.success`/`auth.login.failure`.
- Throttling входа: блокировка после 10 неудачных попыток на 15 минут.
- Секреты провайдеров, JWT-подписи и ingest-пароль не попадают в репозиторий; пароль обновляется через `/api/settings`.

## Deprecation / SemVer
- Придерживаемся SemVer: MAJOR — breaking изменения, MINOR — новые возможности без поломок, PATCH — фиксы/документация.
- Любой деприкейт фиксируем в `spec/contracts/VERSION.json`, ADR и `.memory/DECISIONS.md` минимум за один MINOR до удаления.

## Мониторинг и Ops
- Cron: `python scripts/cleanup_media.py` каждые 15 минут; результаты логируются в syslog (PRD §10).
- `/metrics` (Prometheus) публикует p95 ingest, долю 504, размер `media/*`; алерты управляются через Alertmanager.
- `/healthz` проверяет PostgreSQL, наличие путей файловой системы и быстрый ping провайдеров.
- Деплой: `alembic upgrade head`, проверка health-check, синхронизация контрактов/ADR.
- Бэкапы: ежедневный dump PostgreSQL + снапшоты `media/results` на период релиза.
