---
id: context
version: 1
updated: 2025-10-08
owner: techlead
---

# Устойчивый контекст

## Среды/URL
- Prod: …
- Staging: …
- Local: …

## Стек/версии
- Backend: FastAPI x.y (Python 3.12)
- Front: HTMX + Vanilla JS
- DB/Queue/Infra: …

## Команды разработчика (pre-commit чек-лист)
- Линт/формат: `ruff check . && ruff format .`
- Type-check: `mypy src/`
- Unit: `pytest -q -m unit`
- Contract: `pytest -q -m contract`
- Сборка локально: …
- Быстрые e2e/снимки (опционально): …

## Политики качества
- Coverage ≥ 80% (unit), ≥ 100% на критичных контрактах
- Error budgets/latency цели: …
- Security: no secrets in VCS, SAST/DAST при необходимости


## Deprecation policy
- SemVer: MAJOR — breaking; MINOR — новые фичи без ломаний; PATCH — фиксы/доки.
- Любая устаревающая часть API получает notice (минимум один MINOR цикл).
- Миграции и сроки снятия — фиксировать в `spec/contracts/VERSION.json` и ADR.

## Секреты/лицензии
- DO NOT COMMIT: ключи/токены, приватные артефакты.
- Проверка лицензий зависимостей перед PR.
