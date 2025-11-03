# Domain Model — PhotoChanger

## 1. Сущности и атрибуты

| Сущность | Ключевые поля | Описание и требования |
|----------|---------------|-----------------------|
| Slot | `id`, `display_name`, `provider`, `operation`, `parameters`, `template_media_ids`, `is_active`, `updated_at`, `version` | Определяет правило обработки. Всегда существует 15 предсозданных слотов (`slot-001`…`slot-015`). Конфликт версий предотвращается через optimistic locking (`version`). |
| JobHistory | `job_id`, `slot_id`, `status`, `failure_reason`, `started_at`, `completed_at`, `result_path`, `result_inline_base64`, `result_expires_at`, `metrics` | Фиксирует каждое обращение Ingest API. Статусы: `pending`, `done`, `timeout`, `failed`. `result_expires_at = started_at + T_result_retention`. |
| MediaObject | `id`, `path`, `preview_path`, `media_type`, `expires_at`, `cleaned_at`, `job_id`, `slot_id`, `scope` (`provider|result`) | Отслеживает файлы PhotoChanger. При `scope=result` хранит путь к итоговому изображению и превью (`preview_path`), TTL совпадает с `result_expires_at`. |
| TemplateMedia | `id`, `slot_id`, `path`, `media_type`, `created_at`, `checksum` | Шаблонные изображения, привязанные к слотам; используются провайдерами при генерации. |
| Settings | `id`, `key`, `value`, `updated_at`, `updated_by`, `version` | Глобальные настройки (`T_sync_response`, лимиты размеров, ingest password hash). Хранятся в таблице `settings`. |
| ProviderConfig | `provider`, `rate_limit_window`, `max_payload_mb`, `features`, `timeout_hint` | Метаданные для драйверов; часть конфигурации `AppConfig`, может храниться в YAML/JSON. |

## 2. Связи
- `Slot` 1:N `JobHistory` — каждое обращение маппится на слот.
- `JobHistory` 1:1 `MediaObject` (`scope=result`) — результат хранится как медиа-объект.
- `JobHistory` 1:N `MediaObject` (`scope=provider`) — временные ссылки/файлы для обмена с провайдером (TTL ≤ `T_sync_response`).
- `Slot` 1:N `TemplateMedia` — шаблонные медиа принадлежат слоту.
- `Settings` — глобальная таблица, не связанная напрямую, но используется при сборке `JobContext`.

## 3. Инварианты
- `JobHistory.status` переходит только вперёд: `pending` → `done|timeout|failed`; повторный переход запрещён.
- `MediaObject.expires_at` для `scope=provider` ≤ `JobHistory.started_at + T_sync_response`.
- `MediaObject.scope=result` имеет `expires_at = JobHistory.started_at + 72 ч`. `cleaned_at` обязателен при фактическом удалении файла.
- `Slot.is_active = false` запрещает запуск ingest; попытки → `404`.
- Обновление ingest-пароля требует синхронизации `Settings` (hash) и журналирование в `JobHistory` не выполняется.
- `TemplateMedia` допустимо использовать только в слотах, к которым они привязаны.

## 4. Диаграммы
- Диаграмма классов/ER будет подготовлена в `spec/diagrams/domain-model.mmd` (US PHC-1.0.3).
- Последовательность обновления статусов и медиа описана в `spec/docs/use-cases.md` (UC2/UC3/UC4).
