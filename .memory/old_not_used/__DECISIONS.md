---
id: decisions
updated: 2025-10-16
canonical_store: spec/adr
---

# ADR-lite

## [2025-10-08] ADR-0001: Пример решения
status: accepted
supersedes: []
superseded_by: null
context: "Кратко: зачем потребовалось решение"
decision: "Что выбрано и почему"
alternatives:
  - "Вариант A — почему не взяли"
  - "Вариант B — почему не взяли"
consequences: "Плюсы/минусы, миграции, стоимость"
links:
  - pr: "#123"
  - contracts: "VERSION.json@0.2.0"
  - docs: "…"

## [2025-10-16] ADR-0002: TTL и очистка медиа
status: accepted
supersedes: []
superseded_by: null
context: "Нужно зафиксировать единый дедлайн T_sync_response, порядок очистки media_object/Files API и TTL публичных ссылок"
decision: |
  1. Job.expires_at фиксирует created_at + T_sync_response и используется ingest/воркерами/публичным API.
  2. Воркеры очищают временные файлы по завершении задачи; фоновые очистители запускаются с периодом ≤ 60 секунд после истечения TTL и удаляют записи media_object старше T_sync_response.
  3. Планировщик удаляет результаты с истёкшим result_expires_at и выдаёт 410 Gone.
  4. Polling провайдеров прекращается при наступлении дедлайна; retry только новой задачей.
  5. Изменение T_sync_response пересчитывает связанные TTL в настройках.
alternatives:
  - "Продлевать TTL воркерами" — нарушает требования провайдеров и усложняет дедлайны.
  - "Хранить логику очистки только в БД" — требует прямого доступа к файловой системе и усложняет масштабирование.
consequences: "Нужны фоновые процессы очистки, метрики просрочек и тесты TTL/410 Gone. Настройка T_sync_response влияет на ingest, воркеры и публичные ссылки."
links:
  - contracts: "spec/contracts/openapi.yaml"
  - docs: "spec/docs/reviews/2025-10-16-provider-contract-review.md"
  - adr: "spec/adr/ADR-0002.md"

## Активные решения

| ID | Статус | Файл | Кратко |
| --- | --- | --- | --- |
| ADR-0001 | accepted | `spec/adr/ADR-0001.md` | Заглушка для проверки процесса |
| ADR-0002 | accepted | `spec/adr/ADR-0002.md` | TTL, polling и очистка медиа |

## Процесс обновления

1. Создавай новые ADR в `spec/adr/ADR-XXXX.md` (Markdown с front matter).
2. Обновляй таблицу выше после изменения статусов.
3. Фиксируй связи в `.memory/INDEX.yaml` и `REPORT_TEMPLATE.md`.
