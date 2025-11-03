# Промпт для агента Codex

1. Прочитай `agents.md` и обязательный минимум из `.memory` в установленном порядке (MISSION → CONTEXT → TASKS → ASKS → DECISIONS + ADR → `spec/contracts/*` + `VERSION.json` → USECASES → INDEX), чтобы освежить актуальные правила и контракты.
2. Сверься с `docs/BRIEF.md`, `docs/PRD.md`, `docs/ARCHITECTURE.md`, а также действующими SDD/blueprint артефактами (`spec/docs/*`, `spec/diagrams/*`); зафиксируй заметки и несостыковки в `.memory/WORKLOG.md`.
3. Проверь `.memory/TASKS.md`: убедись, что нужный узел `US *.GOV` отмечен `[x]`, и при любых новых развилках заранее создай `CONSULT/REFLECT` карточки с контекстом в WORKLOG.
4. До реализации записывай шаги в `.memory/WORKLOG.md`; после каждого checkpoint синхронизируй `.memory/PROGRESS.md`, `.memory/ASKS.md`, `.memory/TASKS.md` и при необходимости `.memory/DECISIONS.md`.
5. Следуй каноническому процессу: сперва обнови `spec/contracts/*` и SemVer, затем добавь/обнови тесты (`ruff`, `black`, `mypy`, `pytest`), после этого внеси минимальные изменения кода; строго соблюдай UTF-8 дисциплину и политику PR.
6. Продолжай текущую задачу с учётом SLA, KISS и активных ADR; по завершении верни отчёт по `.memory/REPORT_TEMPLATE.md` с ключевыми решениями, изменениями по файлам и логами проверок.
