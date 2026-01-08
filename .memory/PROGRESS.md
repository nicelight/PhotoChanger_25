---
id: progress
updated: 2026-01-09
---

# Progress (changelog — одна строка на событие)

- 2025-10-08: ADR-0001 accepted — см. DECISIONS.md; contracts v0.1.0 → init.

- 2025-10-31: Исключены REPORT-артефакты из `.memory`, обновлены инструкции `agents.md`.
- 2025-10-31: `.memory/CONTEXT.md` приведён в соответствие PRD/ARCHITECTURE (среды, стек, ops).
- 2025-10-31: Подготовлены базовые SDD документы (`spec/docs/*.md` — vision/context/glossary/domain-model/constraints-risks/nfr/use-cases/acceptance-criteria/test-plan).
- 2025-11-02: Обновлён промпт агента Codex (`.TMP/PROMTS.md`), синхронизированы ASKS/WORKLOG.
- 2025-11-03: Завершены диаграммы UC6 и cron cleanup (`spec/diagrams/uc6-ops-sequence.mmd`, `cron-cleanup-state.mmd`).
- 2025-11-03: Выполнен прогон unit-тестов FEAT PHC-1.1 (py -m pytest tests/unit) — 13 passed; добавлен pytest-asyncio.
- 2025-11-04: Восстановлено состояние PHC-1.1/PHC-1.2 из stash GitHub Desktop, py -m pytest tests/unit — 13 passed.
- 2025-11-06: FEAT PHC-2.0 завершена — спецификации админ API (`/api/slots`, `/api/settings`, `/api/stats/overview`) обновлены в PRD/OpenAPI; pytest (48 passed).
- 2025-11-06: Завершена FEAT PHC-1.3 — публичные результаты и cron cleanup; контракты обновлены до 0.2.0, добавлены runbook/README для скрипта.
- 2025-11-09: FEAT PHC-2.2 завершена — добавлен `/api/stats/slots`, KPI для активных слотов, статическая страница статистики и e2e-тест `/ui/stats`; контракты bump до 0.5.0.
- 2025-11-10: FEAT PHC-2.3 завершена — реализованы /api/login, JWT-проверка админских API/UI, обновлены контракты до 0.6.0.
- 2025-11-11: T PHC-3.2.5 закрыта — slot UI переведён на AdminAuth, добавлена серверная гидратация и поддержка `slot_payload` для test-run.
- 2025-11-22: US PHC-2.1.4 завершена — merge template_media без удаления, обязательный role в admin API/test-run, OpenAPI bump до 0.7.0.
- 2025-12-02: FEAT PHC-4.0 — оформлены метрики/алерты `/metrics`, ops blueprint и релизный чеклист; contracts bump до 0.8.0.
- 2025-12-02: FEAT PHC-4.1/4.2 — реализован endpoint `/metrics` (Prometheus текст), добавлены unit-тесты, финализирован ops checklist + smoke cron cleanup.
- 2025-12-02: EP PHC-5 — ingest пароль хранится/возвращается в plaintext, UI настроек показывает пароль, ingest проверяет plaintext; contracts bump до 0.9.0.
- 2026-01-06: EP PHC-8 — исправлен GeminiDriver (responseMimeType для image, улучшена диагностика no_inline_data), unit-тесты провайдера зелёные.
- 2026-01-08: PHC-9 — GeminiDriver теперь запрашивает responseModalities=IMAGE для image-модели; добавлены команды диагностики в test_playbook.
- 2026-01-09: Gemini NO_IMAGE — добавлены ретраи (5 попыток, 3с) и маппинг в 504 provider_timeout, обновлены тесты и runbook; contracts bump до 0.10.1.
- 2026-01-09: PHC-10 — статистика неудач: окно до 72 часов, recent_failures в /api/stats/slots, UI таблица последних 20 ошибок; contracts bump до 0.11.0.
