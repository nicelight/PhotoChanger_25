# Глоссарий PhotoChanger

| Термин | Определение | Источник |
| --- | --- | --- |
| Slot | Конфигурация обработки: выбранный провайдер, операция, параметры, шаблонные медиа и ingest-ссылка. | `/Docs/brief.md`, раздел "Процесс настройки слота" |
| Ingest API | HTTP интерфейс `POST /ingest/{slotId}` для получения фото от DSLR Remote Pro и выдачи результата/504. | `/Docs/brief.md`, раздел "Механизм работы платформы" |
| Job | Задача обработки, создаваемая при ingest; имеет промежуточные статусы `pending`/`processing`, а финализация фиксируется полями `is_finalized` и `failure_reason`. | `/Docs/brief.md`, описание очереди и статусов |
| Job.result_* | Набор полей внутри Job (`result_file_path`, `result_inline_base64`, `result_mime_type`, `result_size_bytes`, `result_checksum`, `result_expires_at`), хранящий последний успешный ответ без отдельной таблицы. Base64-строка присутствует только до завершения синхронного ответа, итоговый файл доступен 72 часа. | `/Docs/brief.md`, раздел "Цель платформы" |
| ProviderAdapter | Компонент, инкапсулирующий вызовы внешнего AI-провайдера (Gemini, Turbotext) с учётом лимитов и форматов. | `/Docs/brief.md`, разделы о провайдерах |
| T_sync_response | Максимальное время ожидания синхронного ответа ingest API, настраивается администратором в диапазоне 45–60 с (по умолчанию 48 с); по истечении возвращается 504 и задача отменяется. | `/Docs/brief.md`, "Механизм работы платформы" |
| T_ingest_ttl | TTL исходной фотографии во временном хранилище: `T_sync_response`; совпадает с общим дедлайном задачи. | `/Docs/brief.md`, "Цель платформы" |
| T_result_retention | TTL итогового файла (`result_file_path`), равен 72 часам; после истечения `GET /public/results/{job_id}` возвращает `410 Gone`. | `/Docs/brief.md`, "Медиа-хранилища и TTL" |
| recent_results | Массив последних успешных задач слота с превью и ссылками для скачивания, возвращается `GET /api/slots/{slot_id}`. | `/Docs/brief.md`, "Пользовательский workflow" |
| media_object | Запись временного публичного файла, доступного по `GET /public/media/{id}` до истечения TTL. | `/Docs/brief.md`, "Временное публичное медиа-хранилище" |
| template_media | Постоянные шаблоны изображений, привязанные к слотам, очищаются только вручную. | `/Docs/brief.md`, "Постоянное хранилище шаблонов" |
| DSLR Remote Pro | Клиент, отправляющий multipart POST с фото, паролем и метаданными. | `/Docs/brief.md`, "Пользовательский workflow" |
| Job queue | Персистентная очередь задач на PostgreSQL (`job` + `SELECT … FOR UPDATE SKIP LOCKED`), обеспечивающая back-pressure и дедлайны. | `/Docs/brief.md`, "Механизм работы платформы" |
| timeout failure_reason | Значение `failure_reason = 'timeout'` у Job при превышении `T_sync_response`; приводит к отмене и очистке временных данных. | `/Docs/brief.md`, "Механизм работы платформы" |
| media public link | Публичная ссылка на временный файл, предназначена для скачивания провайдерами (например, Turbotext). | `/Docs/brief.md`, "Временное публичное медиа-хранилище" |
| queueid | Идентификатор задачи в очереди Turbotext, сохраняется в `Job.provider_job_reference` и используется воркером для polling `do=get_result` в пределах `T_sync_response` без webhook. | `/Docs/brief.md`, раздел "Turbotext"【F:Docs/brief.md†L37-L40】 |
