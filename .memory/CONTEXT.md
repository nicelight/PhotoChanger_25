---
id: context
version: 1
updated: 2025-01-14
owner: techlead
---

# Устойчивый контекст

## Среды/URL
- **Prod:** не развёрнут (MVP в разработке); конечная цель — развёртывание на одном сервере в Docker с публичным HTTPS-доменом для ingest и публичных ссылок. Требования к готовности описаны в roadmap Фазы 6–7 (обсервабилити, SLA 99 %).【F:spec/docs/implementation_roadmap.md】
- **Staging:** планируется как основная интеграционная среда для проверки очереди, воркеров и моков провайдеров; до запуска продакшена используется для e2e/нагрузочных тестов и валидации OpenAPI-контрактов.【F:spec/docs/implementation_roadmap.md】【F:spec/docs/blueprints/test-plan.md】
- **Local:** разработчики поднимают FastAPI-приложение и PostgreSQL (очередь) локально; медиа хранятся в файловой системе (`MEDIA_ROOT`), моки провайдеров подключаются через фикстуры. UI (HTMX) работает на том же сервере.【F:/brief.md】【F:spec/docs/blueprints/test-plan.md】

## Стек/версии
- **Backend:** Python 3.12 + FastAPI; доменный слой выделяет `JobService`, `SlotService`, `SettingsService`, `MediaService`, воркеры и адаптеры провайдеров. Очередь реализована на PostgreSQL с `SELECT … FOR UPDATE SKIP LOCKED` и встроенными воркерами.【F:spec/docs/blueprints/domain-model.md】【F:spec/docs/implementation_roadmap.md】
- **Front:** Административный UI на HTMX/Vanilla JS, использует REST-контракты (`/api/slots`, `/api/settings`, `/public/results/{job_id}`) для настройки слотов и просмотра `recent_results`. Примеры макетов — в `spec/docs/frontend-examples`.【F:/brief.md】【F:spec/docs/blueprints/use-cases.md】
- **DB/Queue/Infra:** PostgreSQL (очередь `job`, TTL/lock-инварианты), файловое хранилище для `MEDIA_ROOT` (постоянные шаблоны и результаты 72 ч), временное публичное хранилище (`media_object`) с TTL = `T_sync_response`, интеграция с внешними AI API (Gemini, Turbotext).【F:spec/docs/blueprints/context.md】【F:spec/docs/blueprints/constraints-risks.md】

## Команды разработчика (pre-commit чек-лист)
- Линт/формат: `ruff check . && ruff format .` — единый стиль Python модулей и сгенерированных стабов.【F:spec/docs/sdd_roadmap.md】
- Type-check: `mypy src/` — контроль контрактов доменных сервисов и адаптеров.
- Unit: `pytest -q -m unit` — покрытие валидации слотов, дедлайнов, расчёта TTL и state machine Job.【F:spec/docs/blueprints/test-plan.md】
- Contract: `pytest -q -m contract` — валидация OpenAPI (`POST /ingest`, `/api/settings`, `/public/results/{job_id}`) и JSON Schema для сущностей.【F:spec/docs/blueprints/test-plan.md】
- Сборка локально: `uvicorn src.app.main:app --reload` (или скрипт `scripts/dev.sh` после его добавления) с поднятой PostgreSQL и настройкой переменных `MEDIA_ROOT`, `DATABASE_URL`, ключей провайдеров (моки).
- Быстрые e2e/снимки (опционально): `pytest -q -m e2e` с моками Gemini/Turbotext для сценариев «успех», «504», истечение публичных ссылок и скачивание из UI; проверяет соответствие TTL и расчёт `result_inline_base64`.【F:spec/docs/blueprints/test-plan.md】

## Политики качества
- **Простота важнее стабильности и удобства тестирования:** при выборе решений держим минимальную комплексность архитектуры и контрактов, даже если это снижает покрытие сценариев или требует ручных проверок. Придерживаемся принципов KISS. Любые улучшения стабильности/тестопригодности допускаются только если не увеличивают заметно сложность и не усложняют пользовательские контракты.

- При выборе менее стабильных, оптимальных, качественных или надёжных решений ради упрощения архитектуры или кода заранее фиксируем риски и уведомляем тимлида, подчёркивая, что компромисс сделан в пользу простоты.
- Перед предложением увеличить комплексность кода, контрактов или архитектуры обязательно консультируемся с тимлидом и получаем подтверждение на изменение курса.

- Покрытие: ≥ 80 % unit-тестами (критичные доменные функции, расчёт TTL) и 100 % контрактами на публичные API, как закреплено в test-plan и NFR. Провалы фиксируются до merge.【F:spec/docs/blueprints/test-plan.md】【F:spec/docs/blueprints/nfr.md】
- Security: запрещено логировать бинарные изображения и секреты; JWT выдаётся только статическим администраторам; ingest-пароль хранится в виде хэша, ротация требует права `settings:write`. Секреты провайдеров — только в секрет-хранилищах/окружении. Регулярные проверки лицензий зависимостей перед релизом.【F:spec/docs/blueprints/nfr.md】【F:spec/docs/blueprints/acceptance-criteria.md】

- Во время тестирования можно использовать боевую базу данных и не создавать обходных путей или дополнительных тестовых баз данных. Мы не боимся утери данных внутри БД.

## Deprecation policy
- SemVer: MAJOR — breaking изменения контрактов; MINOR — новые возможности без поломок; PATCH — фиксы и документация.【F:agents.md】
- Любой деприкейт API получает notice минимум на один MINOR; сроки и миграции документируются в `spec/contracts/VERSION.json` и ADR (см. roadmap Фаза 0/7 для Re-Sync).【F:agents.md】【F:spec/contracts/VERSION.json】

## Секреты/лицензии
- Не коммитить API-ключи (Gemini, Turbotext), ingest-пароли, JWT-секреты, приватные медиа. Секреты хранятся в `secrets/runtime_credentials.json` и `app_settings`, доступ ограничен, ротация — через `/api/settings`.【F:spec/docs/blueprints/context.md】【F:spec/docs/blueprints/constraints-risks.md】
- Перед PR проверять лицензии зависимостей и соответствие требованиям провайдеров; фиксировать нарушения в ADR/roadmap. При работе с внешними провайдерами соблюдать их SLA и rate limit (Gemini 500 rpm, Turbotext billing).
