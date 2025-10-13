---
id: usecases
updated: 2025-10-08
---

# Ключевые сценарии (примерный шаблон)

## UC1: Пользователь загружает фото (sync обработка)
- Actors: DSLR/Operator
- Preconditions: …
- Main flow: …
- Acceptance:
  - API: POST /ingest → 200 с валидным payload (schema: …)
  - Время ответа ≤ 2s (p95)
  - Логи события зафиксированы

## UC2: Async обработка с уведомлением
- Actors: …
- Flow: …
- Acceptance: …

## UC3… (добавить до 5–10 сценариев)
