---
id: progress
updated: 2025-11-06
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
