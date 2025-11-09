---
id: tasks
updated: 2025-11-09
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
- [x] EP PHC-1 — Синхронный ingest 15 слотов  
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

  [x] FEAT PHC-1.1 — Построение ingest API и доменной модели  
    [x] US PHC-1.1.1 — Валидация payload и создание `JobContext`  
        [x] T PHC-1.1.1.1 — Ограничение размера файлов и MIME (JPEG/PNG/WebP)  

          [x] T PHC-1.1.1.1a — REFLECT — выбрать подход к потоковой валидации и определению MIME  
          [x] T PHC-1.1.1.1b — Реализовать проверку размера (per-slot + safety cap) на уровне ingest  
          [x] T PHC-1.1.1.1c — Интегрировать MIME-детекцию и ошибки 415 в ingest pipeline  
        [x] T PHC-1.1.1.1d — Добавить тесты и обновить контракты/документацию по валидации  
        [x] T PHC-1.1.1.1e — Инициализировать реальную БД, миграции и репозитории (`slot`, `job_history`, `media_object`, `settings`)
      [x] T PHC-1.1.1.2 — Хранение temp файлов с TTL = `T_sync_response`  
          [x] T PHC-1.1.1.2a — REFLECT — спроектировать управление temp-файлами и TTL (создание, обновление, очистка)  
          [x] T PHC-1.1.1.2b — Реализовать TempMediaStore (API, TTL-метаданные, файловая структура)  
          [x] T PHC-1.1.1.2c — Интегрировать TempMediaStore с JobContext и ingest сервисом  
          [x] T PHC-1.1.1.2d — Написать тесты на TTL/очистку temp-файлов и синхронизировать документацию  
    [x] US PHC-1.1.2 — Таймауты и статусы `pending/done/timeout/failed`
      [x] T PHC-1.1.2.1 — REFLECT — сверить переходы состояний с PRD (§4/§5), SDD (`spec/docs/use-cases.md`) и `ingest-errors.md`, подготовить диаграмму для `JobContext`/БД
      [x] T PHC-1.1.2.2 — Управление статусами и `failure_reason`
        [x] T PHC-1.1.2.2a — Сформировать enum статусов и перечень `failure_reason` на базе `spec/contracts/ingest-errors.md` и доменной модели
        [x] T PHC-1.1.2.2b — Интегрировать установки статусов и `failure_reason` в `IngestService` (успех/ошибки провайдера)
        [x] T PHC-1.1.2.2c — Синхронизировать API-ответы, логи, тесты и документацию (OpenAPI, PRD/SDD) с новой моделью статусов
      [x] T PHC-1.1.2.3 — Обработка таймаута и очистки
        [x] T PHC-1.1.2.3a — REFLECT — согласовать отмену `asyncio.wait_for`, очистку ресурсов и логирование с ограничениями SLA (`T_sync_response`, TTL)
        [x] T PHC-1.1.2.3b — Реализовать обработку таймаута: отмена провайдера, статус `timeout`, cleanup
        [x] T PHC-1.1.2.3c — Написать тесты/контракты и обновить документацию по статусам/таймаутам
    [x] US PHC-1.1.3 — Публичная выдача результатов `/public/results/{job_id}`
      [x] T PHC-1.1.3.1 — REFLECT — сценарии и ограничения публичной выдачи результатов
      [x] T PHC-1.1.3.2 — Реализовать сервис/роутер `/public/results/{job_id}` и интеграцию с `ResultStore`
      [x] T PHC-1.1.3.3 — Тесты выдачи результатов (unit/contract)
    [x] FEAT PHC-1.2 — Интеграция провайдеров Gemini/Turbotext  
      [x] US PHC-1.2.0 — Инфраструктура провайдеров  
        [x] T PHC-1.2.0.1 — REFLECT — продумать `_invoke_provider`, выбор драйвера и маппинг ошибок  
        [x] T PHC-1.2.0.2 — Реализовать `_invoke_provider` и wiring фабрики драйверов в ingest  
        [x] T PHC-1.2.0.3 — Написать unit-тесты на выбор провайдера и обработку ошибок  
        [x] T PHC-1.2.0.4 — REFLECT — определить недостающие поля `Slot`/`slot` (settings_json, шаблоны, параметры провайдеров)  
        [x] T PHC-1.2.0.5 — CONSULT — согласовать структуру слота и миграцию с тимлидом  
        [x] T PHC-1.2.0.6 — Расширить модель слота (ORM, доменная модель, репозиторий, миграции) 
        [x] T PHC-1.2.0.7 — Тесты и фиксация контрактов по обновлённому слоту  
      [x] T PHC-1.2.1 — Реализовать `GeminiDriver` (inline/ошибки)  
        [x] T PHC-1.2.1a — REFLECT — спроектировать адаптер Gemini (inline, retries, ограничения)  
        [x] T PHC-1.2.1b — REFLECT — определить структуру `slot.settings` для операций Gemini  
        [x] T PHC-1.2.1c — CONSULT — утвердить структуру `slot.settings` для Gemini у тимлида  
        [x] T PHC-1.2.1d — Обновить спецификации/схемы для `slot.settings` и операций Gemini  
        [x] T PHC-1.2.1e — Реализовать доступ к `template_media` (репозиторий + файловая система)  
        [x] T PHC-1.2.1f — Имплементация клиента Gemini + интеграция с JobContext  
        [x] T PHC-1.2.1g — Тесты/контракты для GeminiDriver (успех, timeout, ошибки)  

      [x] T PHC-1.2.2 — Реализовать `TurbotextDriver`  

        [x] T PHC-1.2.2a — REFLECT — определить поток Turbotext (временные URL, polling, TTL, cleanup)  
        [x] T PHC-1.2.2b — CONSULT — утвердить публичный доступ `/public/provider-media/{media_id}` и параметры polling  
        [x] T PHC-1.2.2c — Реализовать генерацию ссылок и эндпоинт `/public/provider-media/{media_id}`  

        [x] T PHC-1.2.2d — Имплементация клиента Turbotext (create_queue, polling, скачивание результата)  
        [x] T PHC-1.2.2e — Тесты для TurbotextDriver и публичного эндпоинта (успех, timeout, ошибки)  
        [x] T PHC-1.2.2f — Обновить PRD и связанные артефакты (описание временных ссылок Turbotext)  

    [x] FEAT PHC-1.3 — TTL и очистка медиа  
      [x] US PHC-1.3.GOV — Governance & Discovery  
        [x] T PHC-1.3.GOV.1 — CONSULT — утвердить формат логов cron cleanup   
      [x] US PHC-1.3.1 — Cron очистка медиа  
        [x] T PHC-1.3.1.1 — REFLECT — определить стратегию очистки и инструменты (FS/DB)  
        [x] T PHC-1.3.1.2 — Обновить `scripts/cleanup_media.py` (TTL, простые логи)  
        [x] T PHC-1.3.1.3 — Тесты/проверки для cron (unit/integration)  
      [x] US PHC-1.3.3 — Контракты и документация TTL  
        [x] T PHC-1.3.3.1 — REFLECT — определить сценарии тестирования TTL (results/public API)  
        [x] T PHC-1.3.3.2 — Реализовать контрактные тесты истечения (result TTL, 410)  
        [x] T PHC-1.3.3.3 — Обновить OpenAPI/PRD/репортинг результатов тестов  

- [ ] EP PHC-2 — Админ-панель и статистика  
  [ ] US PHC-2.GOV — Governance & Discovery  
    [x] T PHC-2.GOV.1 — REFLECT — определить границы админ-панели (API, UI, статистика, доступы)  
    [x] T PHC-2.GOV.2 — CONSULT — согласовать ключевые контракты `/api/slots`, `/api/settings`, `/api/stats`, test-run  
  [x] FEAT PHC-2.0 — Спецификации админ API и UI  
    [x] US PHC-2.0.1 — OpenAPI `/api/slots`, `/api/settings`, `/api/stats/overview`  
      [x] T PHC-2.0.1.1 — Описать схемы запросов/ответов и ошибки в `spec/contracts/schemas/`  
      [x] T PHC-2.0.1.2 — Зафиксировать аутентификацию/авторизацию и бизнес-правила в OpenAPI  
    [x] US PHC-2.0.2 — Документация UI и blueprints  
      [x] T PHC-2.0.2.1 — Обновить `docs/PRD.md` и `spec/docs/use-cases.md` (CRUD слотов, статистика)  
      [x] T PHC-2.0.2.2 — Подготовить мок-эндпоинты/пример HTML в `spec/docs/ui/`  
  [ ] FEAT PHC-2.1 — CRUD слотов и глобальных настроек  
    [x] US PHC-2.1.GOV — Governance & Discovery  
      [x] T PHC-2.1.GOV.1 — REFLECT — собрать требования к CRUD слотов и глобальных настроек (UI, авторизация, синхронизация данных) и зафиксировать риски внедрения  
      [x] T PHC-2.1.GOV.2 — CONSULT — утвердить у тимлида минимальный набор полей/валидаций для форм слота и глобальных настроек в первой итерации  
      [x] T PHC-2.1.GOV.3 — CONSULT — согласовать стратегию интеграции HTML-форм с REST `/api/slots` и `/api/settings` (ответы, ошибки, версия слота)  
    [x] US PHC-2.1.2.GOV — Governance & Discovery  
      [x] T PHC-2.1.2.GOV.1 — REFLECT — определить требования к тестовому запуску слота (Admin UI → backend)  
      [x] T PHC-2.1.2.GOV.2 — CONSULT — утвердить контракт `/api/slots/{slot_id}/test-run` и маркировку задач  
    [x] US PHC-2.1.2 — Тестовый ендпоинт слотов
      [x] T PHC-2.1.2.1 — Реализовать эндпоинт `/api/slots/{slot_id}/test-run` и повторное использование IngestService  
      [x] T PHC-2.1.2.2 — Маркировать `job_history` (`source=ui_test`) и обновить логи/статистику  
      [x] T PHC-2.1.2.3 — Тесты и документация (OpenAPI/PRD/spec) для test-run  
    [x] US PHC-2.1.3.GOV — Governance & Discovery  
      [x] T PHC-2.1.3.GOV.1 — REFLECT — декомпозировать DTO/валидацию для `/api/slots*` и `/api/settings*`, учесть `recent_results`, `template_media`, masking секретов  
      [x] T PHC-2.1.3.GOV.2 — CONSULT — утвердить у тимлида состав editable полей (slots/settings), лимиты (`size_limit_mb ≤ 20`, глобальный `sync_response_seconds`), формат `provider_keys`  
      [x] T PHC-2.1.3.GOV.3 — CONSULT — подтвердить форматы ответов/ошибок (чистый JSON, без optimistic locking) и требования к аудиту (`updated_by`, журнал)  

    [x] US PHC-2.1.3 — REST API слотов и настроек  
      [x] T PHC-2.1.3.1 — Реализовать `GET /api/slots` + `GET /api/slots/{slot_id}` (DTO, recent_results, template_media)  
      [x] T PHC-2.1.3.2 — Реализовать `PUT /api/slots/{slot_id}` (валидация настроек, обновление template_media, журналирование)  
      [x] T PHC-2.1.3.3 — Реализовать `GET /api/settings` (агрегация TTL/T_sync/password metadata)  
      [x] T PHC-2.1.3.4 — Реализовать `PUT /api/settings` (sync_response_seconds, result_ttl_hours, ingest_password, provider_keys)  
      [x] T PHC-2.1.3.5 — Unit/contract тесты и обновление OpenAPI/PRD для админских API  
  [x] FEAT PHC-2.2 — Просмотр статистики и графики  
    [x] US PHC-2.2.GOV — Governance & Discovery  
      [x] T PHC-2.2.GOV.1 — REFLECT — сформулировать требования к метрикам SLA и визуализациям страницы статистики  
      [x] T PHC-2.2.GOV.2 — CONSULT — утвердить формат `/api/stats/slots` и набор графиков/таблиц у тимлида  
    [x] US PHC-2.2.1 — API и UI статистики слотов  
      [x] T PHC-2.2.1.1 — REST `/api/stats/slots`
      [x] T PHC-2.2.1.2 — UI-графики и таблицы SLA  
    [x] US PHC-2.2.2 — Тесты UI статистики  
      [x] T PHC-2.2.2.1 — Добавить e2e сценарий `/ui/stats` (Playwright/Cypress, happy-path обновление данных)  
  [ ] FEAT PHC-2.3 — Авторизация админов (JWT)  
    [ ] T PHC-2.3.1 — REFLECT — описать требования к JWT-слою (аккаунты, срок жизни токена, области доступа)  
    [ ] T PHC-2.3.2 — CONSULT — утвердить подход к аутентификации и перечень защищаемых эндпоинтов  
    [ ] T PHC-2.3.3 — Реализовать `POST /api/login` и выдачу JWT для статических админов  
    [ ] T PHC-2.3.4 — Добавить проверку JWT ко всем `/api/slots*`, `/api/settings*`, `/api/slots/{slot_id}/test-run`  
    [ ] T PHC-2.3.5 — Unit/интеграционные тесты + обновление PRD/OpenAPI/документации по авторизации  

- [ ] EP PHC-3 — Фронтенд
  [ ] US PHC-3.1.GOV — Governance & Discovery  
    [ ] T PHC-2.1.GOV.1 — REFLECT
    [ ] T PHC-2.1.GOV.3 — CONSULT
  [ ] FEAT PHC-3.2 — UX Слотов  
       [x] T PHC-3.2.1 — Разметка и валидация формы слота (адаптировать текущий шаблон под рабочий UI)  
       [x] T PHC-3.2.2 — Вынести CSS/JS страницы слота в общие файлы (palette/эффекты остаются без изменений)  
       [x] T PHC-3.2.3 — Подготовить 15 статических страниц `slot-001`…`slot-015` (отдельные HTML с общими ресурсами)
       [ ] T PHC-3.2.4 — Валидация и подключение форм слотов.
       [ ] T PHC-3.2.5 — Подсветить поля форм слотов и настроек при ответах 422 (JSON ошибки)  
       [ ] T PHC-3.2.6 — Реализовать боевые страницы логина/дашборда/настроек на основе шаблонов `login-page.html` и `main-page.html`  


- [ ] EP PHC-4 — Ops и наблюдаемость  
  [ ] US PHC-4.GOV — Governance & Discovery  
    [ ] T PHC-4.GOV.1 — CONSULT — стратегия хранения секретов (Vault vs .env)  
    [ ] T PHC-4.GOV.2 — REFLECT — сценарии деградации при недоступности Turbotext/Gemini  
  [ ] FEAT PHC-4.0 — Спецификации наблюдаемости и релизных процедур  
    [ ] US PHC-4.0.1 — Документировать мониторинг и алерты  
      [ ] T PHC-4.0.1.1 — Описать `/metrics` и пороги SLA в `spec/contracts/schemas/metrics.yaml`  
      [ ] T PHC-4.0.1.2 — Зафиксировать алертинг-плейбуки и деградации в `spec/docs/blueprints/ops.md`  
    [ ] US PHC-4.0.2 — Процедуры выпуска и версии контрактов  
      [ ] T PHC-4.0.2.1 — Обновить `spec/contracts/VERSION.json` (SemVer bump, summary)  
      [ ] T PHC-4.0.2.2 — Синхронизировать `.memory/INDEX.yaml` и подготовить checklist для spec handoff  
  [ ] FEAT PHC-4.1 — Мониторинг и алерты  
    [ ] T PHC-4.1.1.1 — `/metrics` + экспортер 504  
    [ ] T PHC-4.1.1.2 — Алерты на заполнение `media/` и рост 504  
  [ ] FEAT PHC-4.2 — Процедуры выпуска  
    [ ] T PHC-4.2.1.1 — Документация deploy checklist  
    [ ] T PHC-4.2.1.2 — Авто-проверка cron очистки (smoke)  


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

