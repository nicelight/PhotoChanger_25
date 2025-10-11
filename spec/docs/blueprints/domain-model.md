# Доменная модель PhotoChanger

## Основные сущности

### Slot
- `id` (`string`) — статический идентификатор слота (`slot-001` … `slot-015`), создаётся миграцией и не меняется.
- `name` — отображается в UI, помогает операторам выбирать слот.
- `provider` — ключ провайдера (`gemini`, `turbotext`, ...).
- `operation` — выбранная операция провайдера (например, `style_transfer`).
- `settings_json` — параметры операции, включая промпты, ссылки на `template_media` и конфигурацию ретраев.
- `updated_at`, `created_at` — аудит изменений.
- Глобальный ingest-пароль хранится отдельно в `app_settings` и не является полем Slot; ingest-URL вычисляется по шаблону `<BASE_URL>/ingest/{id}` без сохранения в таблице.

### Job
- `id` (`UUID`).
- `slot_id` — связь с `Slot`.
- `status` — рабочие состояния `pending` → `processing`; финализация описывается отдельными полями `is_finalized` и `failure_reason`.
- `expires_at` — фиксированный дедлайн задачи; вычисляется при создании записи как `created_at + T_job_deadline`, где `T_job_deadline = max(T_sync_response, T_media_limit_max)`. Это гарантирует, что даже при использовании публичных ссылок с TTL `T_public_link_ttl = clamp(T_sync_response, 45, 60)` дедлайн не станет короче лимита хранилища и останется единым для API, воркеров и очистки.【F:Docs/brief.md†L33-L132】
- `result_inline_base64` / `result_file_path` — данные последнего успешного изображения (inline или путь на диске).
- `result_mime_type`, `result_size_bytes`, `result_checksum` — метаданные результата.
- `provider_job_reference` — единое опциональное поле для async/webhook идентификаторов провайдера.
- `payload_path` — ссылка на исходный файл во временном хранилище (опционально).
- `finalized_at`, `created_at`, `updated_at` — аудит жизненного цикла записи.

### MediaObject (временные ссылки)
- `id` (`UUID`).
- `path` — расположение файла в `MEDIA_ROOT`.
- `mime`, `size_bytes`.
- `expires_at` — фиксированный TTL `T_public_link_ttl = clamp(T_sync_response, 45, 60)` для публичных ссылок (`MEDIA_PUBLIC_LINK_TTL_SEC`).
- `job_id` — связь для автоматической очистки.

### TemplateMedia (постоянные шаблоны)
- `id` (`UUID`).
- `path`, `mime`, `size_bytes`, `checksum`.
- `label`, `uploaded_by`, `created_at`.

### ProviderAdapter
- Абстракция над внешним API.
- Связывает `Job` c конкретной реализацией (Gemini через `models.generateContent`, Turbotext через `api_ai`).
- Хранит лимиты: допустимые MIME, размер, количество одновременных задач.

## Связи
- `Slot 1 - N Job`: каждый запуск ingest создаёт новую `Job` по настройкам слота.
- `Job` хранит последний успешный результат в собственных полях `result_*`, отдельной таблицы нет.
- `Job 1 - N MediaObject`: временные файлы (исходники, промежуточные) привязаны к задаче для очистки.
- `Slot N - M TemplateMedia`: через `slot_template_binding` слот может ссылаться на несколько шаблонных файлов.
- `Job 1 - 1 ProviderAdapter`: определяется `slot.provider` и выбирается при запуске задачи.

## Инварианты
- Исходный ingest-пейлоад (`Job.payload_path`) очищается по формуле `min(job.expires_at, created_at + T_ingest_ttl)`; поскольку `T_ingest_ttl ≤ T_sync_response`, файл не живёт дольше синхронного окна ожидания и удаляется сразу после финализации задачи.【F:Docs/brief.md†L19-L44】【F:Docs/brief.md†L60-L66】
- Для каждого временного артефакта применяется единая формула TTL: `artifact_expires_at = min(job.expires_at, created_at + T_media_limit)` (где `T_media_limit` задаётся конкретным механизмом хранения: `T_ingest_ttl`, `T_public_link_ttl` и т.д.).【F:Docs/brief.md†L60-L137】
- Временная публичная ссылка (`MediaObject`) живёт `min(job.expires_at, created_at + T_public_link_ttl)`; благодаря `T_job_deadline = max(T_sync_response, T_public_link_ttl)` фактический TTL совпадает с вычисленным `T_public_link_ttl`, после чего ссылка удаляется, а `Job` помечается `failure_reason = 'timeout'`.【F:Docs/brief.md†L19-L137】
- `Job.expires_at` не меняется после создания записи и служит верхней границей для всех связанных TTL (`payload_path`, публичные ссылки, промежуточные файлы).【F:Docs/brief.md†L56-L69】
- После `is_finalized = true` задача не возвращается в активное состояние; повторная обработка требует нового ingest.
- В Job хранится только последний успешный результат (`result_*`); при новом запуске поля перезаписываются.
- `Slot` не может быть активирован без валидных параметров провайдера (минимально необходимые поля определяются провайдером).
- `provider_job_reference` заполняется при асинхронных сценариях и может быть пустым для синхронных провайдеров.
- Временные ссылки не продлеваются: по истечении `T_public_link_ttl` запись удаляется, а связанную `Job` помечают `failure_reason = 'timeout'`.

## Диаграмма сущностей (Mermaid)
```mermaid
erDiagram
    Slot ||--o{ Job : creates
    Slot ||--o{ SlotTemplateBinding : uses
    TemplateMedia ||--o{ SlotTemplateBinding : provides
    Job ||--o{ MediaObject : attaches
    Job }|--|| ProviderAdapter : handled_by
```
