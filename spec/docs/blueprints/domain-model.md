# Доменная модель PhotoChanger

## Основные сущности

### Slot
- `id` (`UUID`/`string`) — идентификатор и часть ingest-URL.
- `name` — отображается в UI, помогает операторам выбирать слот.
- `provider` — ключ провайдера (`gemini`, `turbotext`, ...).
- `operation` — выбранная операция провайдера (например, `style_transfer`).
- `settings_json` — параметры операции, включая промпты, ссылки на `template_media` и конфигурацию ретраев.
- `ingest_secret` — пароль для проверки DSLR Remote Pro.
- `ingest_url` — полный URL `POST /ingest/{slotId}`.
- `updated_at`, `created_at` — аудит изменений.

### Job
- `id` (`UUID`).
- `slot_id` — связь с `Slot`.
- `status` — рабочие состояния `pending` → `processing`; финализация описывается отдельными полями `is_finalized` и `failure_reason`.
- `result_inline_base64` / `result_file_path` — данные последнего успешного изображения (inline или путь на диске).
- `result_mime_type`, `result_size_bytes`, `result_checksum` — метаданные результата.
- `provider_job_reference` — единое опциональное поле для async/webhook идентификаторов провайдера.
- `payload_path` — ссылка на исходный файл во временном хранилище (опционально).
- `finalized_at`, `created_at`, `updated_at` — аудит жизненного цикла записи.

### MediaObject (временные ссылки)
- `id` (`UUID`).
- `path` — расположение файла в `MEDIA_ROOT`.
- `mime`, `size_bytes`.
- `expires_at` — фиксированный TTL 60 секунд (`MEDIA_PUBLIC_LINK_TTL_SEC`).
- `job_id` — связь для автоматической очистки.
- `download_quota` — лимиты на скачивания.

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
- Временный файл (`MediaObject`) не живёт дольше `T_sync_response` и автоматически удаляется после финализации Job.
- После `is_finalized = true` задача не возвращается в активное состояние; повторная обработка требует нового ingest.
- В Job хранится только последний успешный результат (`result_*`); при новом запуске поля перезаписываются.
- `Slot` не может быть активирован без валидных параметров провайдера (минимально необходимые поля определяются провайдером).
- `provider_job_reference` заполняется при асинхронных сценариях и может быть пустым для синхронных провайдеров.
- Временные ссылки не продлеваются: по истечении 60 секунд запись удаляется, а связанную `Job` помечают `failure_reason = 'timeout'`.

## Диаграмма сущностей (Mermaid)
```mermaid
erDiagram
    Slot ||--o{ Job : creates
    Slot ||--o{ SlotTemplateBinding : uses
    TemplateMedia ||--o{ SlotTemplateBinding : provides
    Job ||--o{ MediaObject : attaches
    Job }|--|| ProviderAdapter : handled_by
```
