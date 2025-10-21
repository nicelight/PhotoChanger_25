# Административная схема БД

Документ описывает таблицы, созданные миграциями Alembic (`202510280001` и `202511010001`), которые поддерживают административный API платформы PhotoChanger.

## admin_settings

- **Назначение:** хранение глобальных настроек и состояния секретов (`/api/settings`). Значения сериализуются в JSON, чтобы без миграций сохранять структуры `Settings`, `SettingsIngestConfig`, `SettingsProviderKeyStatus` и т.д.
- **Ключ:** `key` (PK). Рекомендуется использовать пространные ключи (`settings.ingest`, `provider_keys.gemini`).
- **Основные поля:**
  - `value` (`JSONB`) — произвольный JSON блок, совместимый с контрактами OpenAPI.
  - `value_type` — тип значения (например, `config`, `status`, `provider_status`).
  - `is_secret` — маркер секретных записей (не выводятся в UI без фильтрации).
  - `etag`, `updated_at`, `updated_by` — используются для `If-Match` и аудита обновлений.
- **Индексы:** `ix_admin_settings_updated_at` ускоряет выборку свежих записей для UI и фоновых задач ротации.
- **TTL/политики:** записи не удаляются автоматически; TTL контролируется клиентским кодом через поля `value`.

## slots

- **Назначение:** статические ingest-слоты (`slot-001`…`slot-015`) с параметрами провайдеров и настройками UI.
- **Ключ:** `id` (PK) с проверкой формата `slot-\d{3}`.
- **Основные поля:**
  - `settings_json` (`JSONB`) — сериализованная конфигурация провайдера, включая ссылки на шаблоны и ретраи.
  - `last_reset_at` — фиксация сброса статистики для `/api/slots/{id}/reset_stats`.
  - `etag`, `updated_at` — используются в `If-Match` и `SlotUpdateRequest.updated_at`.
- **Индексы:**
  - `ix_slots_provider_operation` — покрывает фильтры `provider_id`/`operation_id` в `GET /api/slots`.
  - `ix_slots_updated_at` — выборка недавних изменений для UI и фонового sync.
- **Связи:** внешний ключ на `slot_templates.slot_id` и `processing_log_aggregates.slot_id`.

## slot_templates

- **Назначение:** шаблонные медиа и привязки к ключам конфигурации слота (`TemplateMediaObject`).
- **Ключ:** `id` (UUID, PK).
- **Основные поля:** `setting_key`, `path`, `mime`, `size_bytes`, `checksum` (SHA-256), `label`, `uploaded_by`, `created_at`.
- **Связи:** `slot_id` → `slots.id` (CASCADE). Единственный активный шаблон на пару `(slot_id, setting_key)` enforced by `uq_slot_templates_slot_key`.
- **Индексы:** `ix_slot_templates_slot_id` для быстрого получения всех шаблонов слота.

## processing_log_aggregates

- **Назначение:** агрегированные счётчики статистики по логам обработки для UI `/api/stats/*`.
- **Ключ:** `id` (UUID, PK). Дополнительный `UNIQUE (slot_id, granularity, period_start, period_end)` гарантирует идемпотентность расчётов.
- **Основные поля:**
  - `slot_id` (nullable) — `NULL` хранит глобальные метрики, значение ссылается на конкретный слот.
  - `granularity` (`hour|day|week`) — согласовано с параметром `group_by` в контрактах статистики.
  - `period_start`/`period_end` — интервал агрегации, защищён `CHECK period_end >= period_start`.
  - `success`, `timeouts`, `provider_errors`, `cancelled`, `errors`, `ingest_count` — целочисленные счётчики с серверным default `0`.
  - `created_at`/`updated_at` — контроль свежести и TTL (очистка данных за пределами retention window реализуется сервисом статистики).
- **Индексы:**
  - `ix_processing_log_aggregates_slot_period` — фильтры по слоту и диапазону дат.
  - `ix_processing_log_aggregates_period_end` — ускоряет очистку по TTL (`period_end < now - retention`).

## Жизненный цикл и миграции

1. **Первичная миграция** `202510280001_create_queue_tables` поднимает очередь (`jobs`, `processing_logs`).
2. **Миграция** `202511010001_create_admin_tables` добавляет административные таблицы из этого документа.
3. Smoke-тест `tests/integration/db/test_migrations.py` прогоняет `downgrade base → upgrade head` и проверяет наличие таблиц, индексов и ограничений.

## Использование фикстур

- Примерные данные для локальных тестов хранятся в `tests/fixtures/*.json` и соответствуют схемам `Settings`, `Slot`, `TemplateMediaObject`, `StatsMetricBase` из OpenAPI.
- Данные можно загружать в PostgreSQL через `COPY` или пользовательские скрипты перед запуском контрактных тестов UI.
