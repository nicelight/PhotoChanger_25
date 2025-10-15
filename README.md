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

## Operations

- Подробный запуск ingest и управление таймаутами описаны в
  [Docs/operations/ingest_runbook.md](Docs/operations/ingest_runbook.md).
