---
id: tasks
updated: 2025-11-02
---

# Tasks (канбан)
> Политика: вместе с имплементационными пунктами обязательно веди задачи для размышлений и консультаций с тимлидом.  Формулируй их с префиксом `CONSULT` или `REFLECT`, следуя разделу «Практика CONSULT/REFLECT» в `agents.md`. 

> Формат Kanban с иерархией:  
> `[ ]` — не начато, `[~]` — в работе, `[x]` — выполнено.  
> Уровни: **EP → FEAT → US → T**.  
---
## 📘 Формат
**Уровни задач:**
- `EP` — Epic (цель, объединяет фичи)  
- `FEAT` — Feature (функциональная часть)  
- `US` — User Story (поведение пользователя)  
- `T` — Task (конкретное действие)


## TODO
- [ ] EP PHC-1 — Синхронный ingest 15 слотов  
  [x] US PHC-1.GOV — Governance & Discovery  
    [x] T PHC-1.GOV.1 — CONSULT — подтвердить лимиты конкурентных ingest-запросов и необходимость внешнего rate limiting (тимлид)  
    [x] T PHC-1.GOV.2 — REFLECT — баланс KISS vs SLA при росте количества провайдеров  
    [x] T PHC-1.GOV.3 — CONSULT — утвердить состав SDD-пакета спецификаций (vision/context/glossary/domain-model/constraints-risks/nfr/use-cases/acceptance-criteria/test-plan)  
    [x] T PHC-1.GOV.4 — REFLECT — оценить риски и зависимости подготовки полного SDD-пакета  
  [x] FEAT PHC-1.0 — Спецификации ingest API  
    [x] US PHC-1.0.0 — Базовые SDD документы  
      [x] T PHC-1.0.0.1 — Подготовить `spec/docs/vision.md` (видение продукта и целевые метрики)  
      [x] T PHC-1.0.0.2 — Описать `spec/docs/context.md` (границы системы, акторы, контекстная диаграмма)  
      [x] T PHC-1.0.0.3 — Составить `spec/docs/glossary.md` (термины и обозначения)  
      [x] T PHC-1.0.0.4 — Разработать `spec/docs/domain-model.md` (сущности, связи, инварианты)  
      [x] T PHC-1.0.0.5 — Зафиксировать `spec/docs/constraints-risks.md` (ограничения, допущения, риски)  
      [x] T PHC-1.0.0.6 — Уточнить `spec/docs/nfr.md` (нефункциональные требования и SLA)  
      [x] T PHC-1.0.0.7 — Обновить `spec/docs/use-cases.md` с диаграммами последовательностей/состояний  
      [x] T PHC-1.0.0.8 — Сформировать `spec/docs/acceptance-criteria.md` по основным сценариям  
      [x] T PHC-1.0.0.9 — Составить `spec/docs/test-plan.md` (стратегия тестирования и ответственность)  
      [x] T PHC-1.0.0.10 — REFLECT — сверить `spec/docs/use-cases.md` с BRIEF/PRD/ARCHITECTURE и зафиксировать правки  
      [x] T PHC-1.0.0.11 — CONSULT — утвердить обновлённые use-case у тимлида  
    [x] US PHC-1.0.1.GOV — Governance & Discovery  
      [x] T PHC-1.0.1.GOV.1 — REFLECT — сопоставить требования ingest payload/ответов из BRIEF/PRD/ARCHITECTURE и выявить расхождения  
      [x] T PHC-1.0.1.GOV.2 — CONSULT — подтвердить формат успешного ответа (`binary` vs JSON) и состав обязательных полей/заголовков ingest API у тимлида  
    [x] US PHC-1.0.1 — OpenAPI `/api/ingest/{slot_id}` и SLA  
      [x] T PHC-1.0.1.1 — Описать JSON Schema multipart payload и ответы (успех/ошибки)  
      [x] T PHC-1.0.1.2 — Зафиксировать коды ошибок/таймаутов и семантику `failure_reason`  
      [x] T PHC-1.0.1.3 — REFLECT — оценить поддержку `format: binary`/`contentMediaType` выбранными инструментами OpenAPI и при необходимости скорректировать схемы  
      [x] T PHC-1.0.1.4 — Добавить примеры запросов/ошибок и описание SLA (`T_sync_response`, TTL) в `spec/contracts/openapi.yaml`  
    [x] US PHC-1.0.2 — Провайдерские спецификации Gemini/Turbotext  
      [x] T PHC-1.0.2.1 — Обновить `spec/contracts/providers/gemini.md` и `turbotext.md` (лимиты, форматы, SLA)  
      [x] T PHC-1.0.2.2 — Задокументировать деградации/ретраи в `spec/docs/providers/*.md`  
    [x] US PHC-1.0.3 — Диаграммы для SDD
      [x] T PHC-1.0.3.1 — Подготовить C4-диаграммы контекста/контейнера в `spec/diagrams/`
      [x] T PHC-1.0.3.2 — Добавить sequence/state диаграммы (Mermaid/PlantUML) для ключевых use-case в `spec/diagrams/`

  [ ] FEAT PHC-1.1 — Построение ingest API и доменной модели  
    [ ] US PHC-1.1.1 — Валидация payload и создание `JobContext`  
        [x] T PHC-1.1.1.1 — Ограничение размера файлов и MIME (JPEG/PNG/WebP)  
          [x] T PHC-1.1.1.1a — REFLECT — выбрать подход к потоковой валидации и определению MIME  
          [x] T PHC-1.1.1.1b — Реализовать проверку размера (per-slot + safety cap) на уровне ingest  
          [x] T PHC-1.1.1.1c — Интегрировать MIME-детекцию и ошибки 415 в ingest pipeline  
        [x] T PHC-1.1.1.1d — Добавить тесты и обновить контракты/документацию по валидации  
        [x] T PHC-1.1.1.1e — Инициализировать реальную БД, миграции и репозитории (`slot`, `job_history`, `media_object`, `settings`)
      [ ] T PHC-1.1.1.2 — Хранение temp файлов с TTL = `T_sync_response`  
          [x] T PHC-1.1.1.2a — REFLECT — спроектировать управление temp-файлами и TTL (создание, обновление, очистка)  
          [x] T PHC-1.1.1.2b — Реализовать TempMediaStore (API, TTL-метаданные, файловая структура)  
          [x] T PHC-1.1.1.2c — Интегрировать TempMediaStore с JobContext и ingest сервисом  
          [x] T PHC-1.1.1.2d — Написать тесты на TTL/очистку temp-файлов и синхронизировать документацию  
    [ ] US PHC-1.1.2 — Таймауты и статусы `pending/done/timeout/failed`
      [ ] T PHC-1.1.2.1 — REFLECT — сверить переходы состояний с PRD (§4/§5), SDD (`spec/docs/use-cases.md`) и `ingest-errors.md`, подготовить диаграмму для `JobContext`/БД
      [ ] T PHC-1.1.2.2 — Управление статусами и `failure_reason`
        [ ] T PHC-1.1.2.2a — Сформировать enum статусов и перечень `failure_reason` на базе `spec/contracts/ingest-errors.md` и доменной модели
        [ ] T PHC-1.1.2.2b — Интегрировать установки статусов и `failure_reason` в `IngestService` (успех/ошибки провайдера)
        [ ] T PHC-1.1.2.2c — Синхронизировать API-ответы, логи, тесты и документацию (OpenAPI, PRD/SDD) с новой моделью статусов
      [ ] T PHC-1.1.2.3 — Обработка таймаута и очистки
        [ ] T PHC-1.1.2.3a — REFLECT — согласовать отмену `asyncio.wait_for`, очистку ресурсов и логирование с ограничениями SLA (`T_sync_response`, TTL)
        [ ] T PHC-1.1.2.3b — Реализовать обработку таймаута: отмена провайдера, статус `timeout`, cleanup
        [ ] T PHC-1.1.2.3c — Написать тесты/контракты и обновить документацию по статусам/таймаутам
    [ ] FEAT PHC-1.2 — Интеграция провайдеров Gemini/Turbotext  
      [ ] US PHC-1.2.0 — Инфраструктура провайдеров  
        [ ] T PHC-1.2.0.1 — REFLECT — продумать `_invoke_provider`, выбор драйвера и маппинг ошибок  
        [ ] T PHC-1.2.0.2 — Реализовать `_invoke_provider` и wiring фабрики драйверов в ingest  
        [ ] T PHC-1.2.0.3 — Написать unit-тесты на выбор провайдера и обработку ошибок  
        [ ] T PHC-1.2.0.4 — REFLECT — определить недостающие поля `Slot`/`slot` (settings_json, шаблоны, параметры провайдеров)  
        [ ] T PHC-1.2.0.5 — CONSULT — согласовать структуру слота и миграцию с тимлидом  
        [ ] T PHC-1.2.0.6 — Расширить модель слота (ORM, доменная модель, репозиторий, миграции)  
        [ ] T PHC-1.2.0.7 — Тесты и фиксация контрактов по обновлённому слоту  
      [ ] T PHC-1.2.1 — Реализовать `GeminiDriver` (inline/ошибки)  
        [ ] T PHC-1.2.1a — REFLECT — спроектировать адаптер Gemini (inline, retries, ограничения)  
        [ ] T PHC-1.2.1b — Имплементация клиента Gemini + интеграция с JobContext  
        [ ] T PHC-1.2.1c — Тесты/контракты для GeminiDriver (успех, timeout, ошибки)  
      [ ] T PHC-1.2.2 — Реализовать `TurbotextDriver` (polling, без публичных ссылок)  
        [ ] T PHC-1.2.2a — REFLECT — спроектировать адаптер Turbotext (polling, квоты, локальные данные)  
        [ ] T PHC-1.2.2b — Имплементация клиента Turbotext + обновление JobContext  
        [ ] T PHC-1.2.2c — Тесты/контракты для TurbotextDriver (успех, очередь, ошибки)  
    [ ] FEAT PHC-1.3 — TTL и очистка медиа  
      [ ] T PHC-1.3.1.1 — Cron `scripts/cleanup_media.py`  
        [ ] T PHC-1.3.1.1a — REFLECT — определить стратегию очистки и инструменты (FS/DB)  
        [ ] T PHC-1.3.1.1b — Имплементация скрипта cleanup_media.py (TTL, логи, dry-run)  
        [ ] T PHC-1.3.1.1c — Тесты/проверки для cron (unit/integration)  
      [ ] T PHC-1.3.1.2 — Контрактные тесты на истечение и 410  
        [ ] T PHC-1.3.1.2a — REFLECT — определить сценарии тестирования (results/public API)  
        [ ] T PHC-1.3.1.2b — Реализовать контрактные тесты истечения (result TTL, 410)  
        [ ] T PHC-1.3.1.2c — Документация/репортинг результатов тестов  

- [ ] EP PHC-2 — Админ-панель и статистика  
  [ ] FEAT PHC-2.0 — Спецификации админ API и UI  
    [ ] US PHC-2.0.1 — OpenAPI `/api/slots`, `/api/settings`, `/api/stats`  
      [ ] T PHC-2.0.1.1 — Описать схемы запросов/ответов и ошибки в `spec/contracts/schemas/`  
      [ ] T PHC-2.0.1.2 — Зафиксировать аутентификацию/авторизацию и бизнес-правила в OpenAPI  
    [ ] US PHC-2.0.2 — Документация UI и blueprints  
      [ ] T PHC-2.0.2.1 — Обновить `docs/PRD.md` и `spec/docs/use-cases.md` (CRUD слотов, статистика)  
      [ ] T PHC-2.0.2.2 — Подготовить мок-эндпоинты/пример HTML для HTMX в `spec/docs/ui/`  
  [ ] FEAT PHC-2.1 — CRUD слотов и глобальных настроек  
    [ ] US PHC-2.1.1 — UI форм редактирования (HTMX)  
      [ ] T PHC-2.1.1.1 — Разметка и валидация формы слота  
      [ ] T PHC-2.1.1.2 — API `/api/slots` и `/api/settings`  
  [ ] FEAT PHC-2.2 — Просмотр статистики и графики  
    [ ] T PHC-2.2.1.1 — REST `/api/stats/slots` (p95, доля 504)  
    [ ] T PHC-2.2.1.2 — UI-графики и таблицы SLA  

- [ ] EP PHC-3 — Ops и наблюдаемость  
  [ ] US PHC-3.GOV — Governance & Discovery  
    [ ] T PHC-3.GOV.1 — CONSULT — стратегия хранения секретов (Vault vs .env)  
    [ ] T PHC-3.GOV.2 — REFLECT — сценарии деградации при недоступности Turbotext/Gemini  
  [ ] FEAT PHC-3.0 — Спецификации наблюдаемости и релизных процедур  
    [ ] US PHC-3.0.1 — Документировать мониторинг и алерты  
      [ ] T PHC-3.0.1.1 — Описать `/metrics` и пороги SLA в `spec/contracts/schemas/metrics.yaml`  
      [ ] T PHC-3.0.1.2 — Зафиксировать алертинг-плейбуки и деградации в `spec/docs/blueprints/ops.md`  
    [ ] US PHC-3.0.2 — Процедуры выпуска и версии контрактов  
      [ ] T PHC-3.0.2.1 — Обновить `spec/contracts/VERSION.json` (SemVer bump, summary)  
      [ ] T PHC-3.0.2.2 — Синхронизировать `.memory/INDEX.yaml` и подготовить checklist для spec handoff  
  [ ] FEAT PHC-3.1 — Мониторинг и алерты  
    [ ] T PHC-3.1.1.1 — `/metrics` + экспортер p95/504  
    [ ] T PHC-3.1.1.2 — Алерты на заполнение `media/` и рост 504  
  [ ] FEAT PHC-3.2 — Процедуры выпуска  
    [ ] T PHC-3.2.1.1 — Документация deploy checklist  
    [ ] T PHC-3.2.1.2 — Авто-проверка cron очистки (smoke)  


## IN PROGRESS
- _(пусто; добавь новые задачи после консультации с тимлидом)_

## DONE
- [x] REFLECT — проверить таймауты `T_sync_response` в тестах (2025-10-08)
- [x] EP PHC-0 — Организация знаний и процессов (2025-10-31)
 [x] FEAT PHC-0.1 — Инициализация меморибанка и служебных артефактов
  [x] T PHC-0.1.1 — Заполнить `.memory/*`, `spec/contracts/VERSION.json`, REPORT шаблоны
   - owner: codex
   - priority: P0
   - estimate: 0.5d
   - notes: выполнено 2025-10-31, запрос ASK-2025-10-31-001
- [x] T PHC-0.1.2 — Удалить `.memory/REPORT.json` и `.memory/REPORT_SCHEMA.json`, скорректировать инструкции (2025-10-31)
 - owner: codex
 - priority: P0
 - notes: инициировано тимлидом 2025-10-31
- [x] T PHC-0.1.3 — Синхронизировать `.memory/CONTEXT.md` с PRD/ARCHITECTURE (2025-10-31)
 - owner: codex
 - priority: P0
 - notes: сверка требований разделов 10–11 PRD и архитектурного гида

## GOV Template (reference)
- [ ] EP XXX — Название эпика  
  [ ] US XXX.GOV — Governance & Discovery  
    [ ] T XXX.GOV.1 — CONSULT — ключевой вопрос к тимлиду  
    [ ] T XXX.GOV.2 — REFLECT — анализ рисков/альтернатив  
  [ ] FEAT XXX.Y — Функциональный блок (открывать после закрытия GOV)
