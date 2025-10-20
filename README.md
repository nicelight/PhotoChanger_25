# PhotoChanger_25
AI платформа для генерации вкусных фотографий.

## Development

- `python3 scripts/gen_stubs.py` — регенерирует стаб-обработчики и DTO на
  основе `spec/contracts/openapi.yaml` и `spec/contracts/schemas`.
  Скрипт использует Jinja2 и PyYAML; установите их в окружении перед запуском.
- `./scripts/check_scaffolding.sh` — прогоняет `ruff`, `mypy` и `pytest`
  (если доступны), помогая убедиться, что scaffolding остаётся консистентным.

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

## Operations

- Подробный запуск ingest и управление таймаутами описаны в
  [Docs/operations/ingest_runbook.md](Docs/operations/ingest_runbook.md).
- Настройка очереди PostgreSQL, миграций Alembic, `statement_timeout` и лимита
  `QUEUE_MAX_IN_FLIGHT_JOBS` собраны в
  [Docs/operations/postgres_queue_runbook.md](Docs/operations/postgres_queue_runbook.md).
