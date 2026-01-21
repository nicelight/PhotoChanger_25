# CODEMAP — навигация по PhotoChanger

Краткая карта стабильных артефактов для разработки и LLM. Опирается на файлы из `spec/` и основные каталоги исходников; обновляется вместе с изменениями архитектуры или API.

## Стартовые точки
- Контракты и версии: `spec/contracts/openapi.yaml`, `spec/contracts/VERSION.json`, схемы в `spec/contracts/schemas/`.
- Архитектура и решения: ADR `spec/adr/`, SDD пакет `spec/docs/` (vision/context/glossary/domain-model/nfr/use-cases/blueprints).
- Карта терминов и соглашений: `spec/docs/glossary.md`.

## Backend (FastAPI, src/app)
- Сборка приложения и конфигурации: `src/app/main.py`, зависимости в `src/app/dependencies.py`.
- Основные домены: `ingest`, `media`, `slots`, `settings`, `stats` — по каталогу на модуль с API, сервисом и репозиторием.
- Провайдеры AI: драйверы в `src/app/providers/`, фабрика `providers_factory.py`, общие типы `providers_schemas.py`.
- Настройки окружения и глобальные параметры: `src/app/config.py`, `src/app/settings/settings_service.py`.

## Frontend (статические страницы)
- Admin: `frontend/admin/` (login, dashboard, settings; общий модуль `assets/auth.js`).
- Slots UI: `frontend/slots/` (template.html и `slot-XXX.html`, логика в `frontend/slots/assets/*.js`).
- Stats UI: `frontend/stats/` (страница `/ui/stats`).
- Public gallery: `frontend/public/` (временные публичные ссылки).

## Данные и конфигурация
- Медиа: `media/temp`, `media/results`, `media/templates` (TTL описаны в `spec/docs/glossary.md`).
- Секреты и примеры: `secrets/` (runtime_credentials пример), `.env.local` для локальной разработки.
- Миграции БД: `alembic/` и `alembic.ini`.

## Скрипты и ops
- Очистка медиа/TTL: `scripts/cleanup_media.py` (cron), сопроводительные инструкции — `docs/runbooks/cron_cleanup.md`.
- Деплой и локальный запуск: `README.md`, `docs/runbooks/init_deploy.md`.
- Диагностика и тест-плейбуки: `docs/runbooks/test_playbook.md`, `docs/runbooks/stats_ui_local.md`.

## Тесты и проверки
- Unit/интеграционные: `tests/unit`, `tests/e2e`, `tests/integration` (если есть).
- Команды чек-листа: `ruff check .`, `black .`, `mypy src/`, `py -m pytest` (см. `.memory/CONTEXT.md`).

## Дополнительно
- При поиске терминов и правил именования см. `spec/docs/glossary.md`.
