# PhotoChanger_25
AI платформа для генерации вкусных фотографий.

## Development

- `python3 scripts/gen_stubs.py` — регенерирует стаб-обработчики и DTO на
  основе `spec/contracts/openapi.yaml` и `spec/contracts/schemas`.
  Скрипт использует Jinja2 и PyYAML; установите их в окружении перед запуском.
- `./scripts/check_scaffolding.sh` — прогоняет `ruff`, `mypy` и `pytest`
  (если доступны), помогая убедиться, что scaffolding остаётся консистентным.
- Для запуска тестов и валидации контрактов установите опциональные зависимости
  `fastapi`, `sqlalchemy`, `alembic`, `jsonschema` и `pytest-asyncio`. Без них
  часть тестов и утилит (например, проверка `ProcessingLog` или миграций) будет
  пропускаться или падать с `ModuleNotFoundError`.
- Скопируйте `.env.example` в `.env` и при необходимости скорректируйте DSN,
  таймаут очереди, параметры кеша статистики (`PHOTOCHANGER_STATS_*`) и настройки
  воркеров (`PHOTOCHANGER_WORKER_*`). Для выделенной аналитической БД используйте
  `PHOTOCHANGER_STATS_DATABASE_URL`. Эти переменные читает и FastAPI, и фоновые
  воркеры.
- Примеры конфигураций для окружений доступны в `configs/app.dev.json`,
  `configs/app.staging.json` и `configs/app.prod.json`. Они фиксируют DSN очереди
  и статистики, TTL кеша, горизонты `recent_results` и параметры опроса воркера,
  чтобы dev/staging/prod оставались синхронизированными.

## Служебные скрипты

- `./scripts/dev.sh` — единая точка для локальной проверки: компиляция
  модулей, линтеры и тесты (`pytest`, если доступен в окружении).

### Тестовое окружение

- Контрактные и интеграционные тесты очереди выполняются против PostgreSQL 16.
  По умолчанию фикстуры используют DSN
  `postgresql://postgres:postgres@localhost:5432/photochanger_test` и автоматически
  создают/очищают таблицы. Для другого окружения задайте `TEST_POSTGRES_DSN` или
  соответствующие `TEST_POSTGRES_HOST/PORT/DB/USER/PASSWORD`.
- Перед запуском тестов установите пароль пользователя `postgres` и создайте
  базу `photochanger_test`, например:
  ```bash
  sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres';"
  sudo -u postgres createdb photochanger_test
  ```
- Если в `.env` не заданы переменные `PHOTOCHANGER_STATS_*`, интеграционные
  тесты используют дефолтные значения кеша (слоты — 300 с, глобальные — 60 с,
  `recent_results` — 72 ч с лимитом 10 записей).

## Operations

- Подробный запуск ingest и управление таймаутами описаны в
  [spec/docs/operations/ingest_runbook.md](spec/docs/operations/ingest_runbook.md).
- Настройка очереди PostgreSQL, миграций Alembic, `statement_timeout` и лимита
  `QUEUE_MAX_IN_FLIGHT_JOBS` собраны в
  [spec/docs/operations/postgres_queue_runbook.md](spec/docs/operations/postgres_queue_runbook.md).
