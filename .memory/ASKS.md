---
id: asks
updated: 2025-10-22
---

# Asks (запросы пользователей)

- 2025-10-08 | id:ASK-0001 | source:user | summary:"Инициализация шаблона" | status:done | notes:"Регистрируется автоматически после закрытия задачи."
- 2025-10-16 | id:ASK-0002 | source:user | summary:"Выполнить задачи 1.3–1.4 (SPEC REVIEW)" | status:done | notes:"Обновлены контракты Gemini/Turbotext, оформлен ADR по TTL."
- 2025-10-16 | id:ASK-0002 | source:user | summary:"Фаза 1.1-1.2: ревью OpenAPI и JSON Schema" | status:done | notes:"OpenAPI выровнен, схемы TTL уточнены, версии обновлены до 0.1.1"
- 2025-10-16 | id:ASK-0003 | source:user | summary:"Зафиксировать завершение фазы 1 в мемори-банке" | status:done | notes:"Обновлены TASKS (фаза 1 → DONE), PROGRESS и ASKS, записи в WORKLOG"
- 2025-10-16 | id:ASK-0004 | source:user | summary:"Закрыть сабтаск 2.1 и синхронизировать стаб-код со спецификацией" | status:done | notes:"OpenAPI поднят до 0.1.2, стабы пересобраны, enum-параметры и клиент обновлены"
- 2025-10-18 | id:ASK-0005 | source:user | summary:"Фаза 2: провести аудит сервисов и подготовить инфраструктурные заглушки" | status:done | notes:"Обновлены стабы домена/очереди, добавлен providers.json и backlog"
- 2025-10-18 | id:ASK-0006 | source:user | summary:"Зафиксировать завершение фазы 2 в мемори-банке" | status:done | notes:"Обновлены TASKS, PROGRESS, ASKS и INDEX"
- 2025-10-18 | id:ASK-0007 | source:user | summary:"Реализовать контрактные тесты ingest/админ-API/публичных ссылок (фаза 3.1)" | status:done | notes:"Добавлены фикстуры, позитивные и негативные сценарии, pytest -m contract зелёный"
- 2025-10-19 | id:ASK-0008 | source:user | summary:"Сабтаск 3.3 — разработать моки провайдеров Gemini/Turbotext" | status:done | notes:"Созданы deterministic mocks, pytest фикстуры и контрактные тесты provider_mocks"
- 2025-10-21 | id:ASK-0009 | source:user | summary:"Повторно подтвердить готовность Фазы 3, обновить тестовый отчёт" | status:done | notes:"Перезапущены pytest unit/contract, установлены зависимости, tests/TEST_REPORT_PHASE3.md и .memory синхронизированы"
- 2025-10-22 | id:ASK-0010 | source:user | summary:"Устранить DI-провайдеров и реализовать QueueWorker.dispatch_to_provider" | status:done | notes:"Расширен ServiceRegistry, реализован полный цикл QueueWorker, добавлены интеграционные проверки успех/timeout/error"
