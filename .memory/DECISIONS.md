---
id: decisions
updated: 2025-10-31
canonical_store: spec/adr
---

# ADR-lite

## [2025-10-08] ADR-0001: Монолит FastAPI + cron без очередей
status: accepted
supersedes: []
superseded_by: null
context: >
  Нужна первая итерация PhotoChanger, которая выдерживает синхронную обработку ≤60 с,
  проста в поддержке и укладывается в команду из одного разработчика без DevOps-команды.
decision: >
  Собрать приложение как один процесс FastAPI с модулями ingest/media/slots/settings/stats,
  хранением состояний в PostgreSQL и файловой системе, вызовами провайдеров напрямую через async драйверы
  и cron-скриптом очистки медиа. Отказались от очередей и отдельных воркеров во имя KISS.
alternatives:
  - Шина сообщений + отдельный воркер (сложнее деплой/отладка, выигрыша по SLA нет).
  - Serverless функции для ingest/provide (дороже latency, сложнее контролировать TTL и локальное хранение).
consequences: >
  Проще деплой и сопровождение, меньше подвижных частей; однако долгие задачи ограничены 60 с,
  а для масштабирования придётся выносить воркеров в новой итерации. Cron-очистка становится критической.
links:
  - pr: "#123"  # placeholder, обновить при появлении настоящего PR
  - contracts: "spec/contracts/VERSION.json@0.1.0"
  - docs: "docs/ARCHITECTURE.md"


## Активные решения

| ID | Статус | Файл | Кратко |
| --- | --- | --- | --- |
| ADR-0001 | accepted | `spec/adr/ADR-0001.md` | Монолит FastAPI + cron, без очередей |


## Процесс обновления

1. Создавай новые ADR в `spec/adr/ADR-XXXX.md` (Markdown с front matter).
2. Обновляй таблицу выше после изменения статусов.
3. Фиксируй связи в `.memory/INDEX.yaml`, `.memory/REPORT_TEMPLATE.md` и `spec/contracts/VERSION.json`.
