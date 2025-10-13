# Codex Cloud — Operating Guide (Core)

> Ядро правил. Подробные плейбуки и команды — в `.memory/CONTEXT.md`.
> Политика автономности и пороги — `.memory/AUTONOMY.md`.
> Миссия/контекст/таски/прогресс — в `.memory/*`. Контракты — в `spec/contracts/*`. ADR — в `spec/adr/*` (индекс — `.memory/DECISIONS.md`). Блюпринты — в `spec/docs/blueprints/*`.

---

## 0) Контроль автономности
- Если в пользовательском запросе прямо указано «автономность 0» или «автономность 1», соблюдай соответствующие правила из `.memory/AUTONOMY.md`.
- Во всех остальных случаях работай с автономностью **2** (полная автономия без дополнительного запроса).

## 1) Must-Read перед задачей
Последовательность чтения:
1) `.memory/MISSION.md` → зачем/ценность/scope.
2) `.memory/CONTEXT.md` → окружения, стек, команды, quality policy, Deprecation.
3) `.memory/TASKS.md` → активные задачи (запомни id/owner).
4) `.memory/ASKS.md` → история пользовательских запросов.
5) `.memory/DECISIONS.md` → индекс ADR (учти `status/supersedes`) + соответствующие файлы в `spec/adr/`.
6) `spec/contracts/*` + `spec/contracts/VERSION.json` → версия API и изменения.
7) `.memory/USECASES.md` → сценарии + acceptance criteria.
8) `.memory/INDEX.yaml` → быстрый контроль актуальности артефактов.

## 2) Рабочий журнал
- До checkpoint все шаги записывай в `.memory/WORKLOG.md` (черновик).
- После прохождения checkpoint (см. ниже) — синхронизируй `.memory/TASKS.md`, `.memory/PROGRESS.md`, при необходимости — `.memory/DECISIONS.md` и `.memory/ASKS.md`.

## 3) Канонический процесс (SDD)
**Contracts → Tests → Code → ADR → Progress**
1) Любые изменения поведения/публичных интерфейсов — **сначала** `spec/contracts/*`.
2) Добавь/обнови unit + contract-тесты; прогон pre-commit чек-листа (см. CONTEXT).
3) Внеси минимально достаточные изменения кода.
4) Если принято архитектурное решение — оформи ADR в `spec/adr/ADR-XXXX.md` и обнови индекс `.memory/DECISIONS.md`.
5) Обнови прогресс (после checkpoint): `.memory/PROGRESS.md` (1 строка), `.memory/ASKS.md` (фиксируй выполненный запрос) и статус в `.memory/TASKS.md`.

## 4) Checkpoints (минимум)
Считается пройденным, если одновременно:
- `spec/contracts/*` валидны и версия в `spec/contracts/VERSION.json` обновлена по правилам SemVer (MAJOR/MINOR/PATCH);
- unit + contract тесты зелёные;
- дельта изменений ≤ порога или подтверждена пользователем (см. AUTONOMY);
- ADR (если нужно) создан/обновлён (`spec/adr/` + `.memory/DECISIONS.md`);
- в `WORKLOG.md` зафиксированы шаги, согласованные на уровне автономности.

## 5) Пороговые триггеры согласования (см. `.memory/AUTONOMY.md`)
- Изменение **публичного контракта** (OpenAPI/JSON Schema), bump MAJOR/MINOR;
- Добавление новой внешней зависимости/инфры/пермишенов/секретов;
- Дельта **LOC > 150** или **files_changed > 5** в одной задаче;
- Смена асимптотики/режима хранения; добавление внешнего сетевого вызова;
- Изменения, затрагивающие безопасность/лицензии/конфиденциальность.

## 6) Финальный ответ
- Верни **текстовый отчёт** по `.memory/REPORT_TEMPLATE.md`.
- Приложи **`REPORT.json`**, валидный по `.memory/REPORT_SCHEMA.json`.
- Укажи: key decisions, прочие шаги, архитектурные изменения, изменения по файлам, риски, синхронизацию артефактов (`spec/contracts/*`, `spec/adr/*`, `.memory/*`).

## 7) Политика PR
Один PR — одна цель. Перед PR:
- пройди pre-commit чек-лист (см. `.memory/CONTEXT.md`),
- проверь SemVer/Deprecation,
- синхронизируй ADR/ASKS/PROGRESS/TASKS/INDEX.

## 8) Антипаттерны (запрещено)
- Менять публичные контракты без `spec/contracts/*` и VERSION bump.
- Игнорировать синхронизацию `.memory/ASKS.md` и `.memory/PROGRESS.md` после завершения задачи.
- Вносить «временные» костыли без ADR/срока удаления.
- Коммитить секреты/ключи; нарушать лицензионные условия.

## 9) Доказательства
К отчёту приложи: команды запуска тестов/линта и краткие логи/снимки версий контрактов.
