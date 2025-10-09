# Глоссарий PhotoChanger

| Термин | Определение | Источник |
| --- | --- | --- |
| Slot | Конфигурация обработки: выбранный провайдер, операция, параметры, шаблонные медиа и ingest-ссылка. | `/Docs/brief.md`, раздел "Процесс настройки слота" |
| Ingest API | HTTP интерфейс `POST /ingest/{slotId}` для получения фото от DSLR Remote Pro и выдачи результата/504. | `/Docs/brief.md`, раздел "Механизм работы платформы" |
| Job | Задача обработки, создаваемая при ingest; имеет промежуточные статусы `pending`/`processing`, а финализация фиксируется полями `is_finalized` и `failure_reason`. | `/Docs/brief.md`, описание очереди и статусов |
| Job.result_* | Набор полей внутри Job (`result_inline_base64`, `result_file_path`, `result_mime_type`, `result_size_bytes`, `result_checksum`), хранящий последний успешный ответ без отдельной таблицы. | `/Docs/brief.md`, раздел "Цель платформы" |
| ProviderAdapter | Компонент, инкапсулирующий вызовы внешнего AI-провайдера (Gemini, Turbotext) с учётом лимитов и форматов. | `/Docs/brief.md`, разделы о провайдерах |
| T_sync_response | Максимальное время ожидания синхронного ответа ingest API (≤ 50 с), после истечения возвращается 504 и задача отменяется. | `/Docs/brief.md`, "Механизм работы платформы" |
| T_ingest_ttl | TTL исходной фотографии во временном хранилище, ≤ 50 с и не превосходит `T_sync_response`. | `/Docs/brief.md`, "Цель платформы" |
| media_object | Запись временного публичного файла, доступного по `GET /public/media/{id}` до истечения TTL. | `/Docs/brief.md`, "Временное публичное медиа-хранилище" |
| template_media | Постоянные шаблоны изображений, привязанные к слотам, очищаются только вручную. | `/Docs/brief.md`, "Постоянное хранилище шаблонов" |
| DSLR Remote Pro | Клиент, отправляющий multipart POST с фото, паролем и метаданными. | `/Docs/brief.md`, "Пользовательский workflow" |
| Job queue | Персистентная очередь задач на PostgreSQL (`job` + `SELECT … FOR UPDATE SKIP LOCKED`), обеспечивающая back-pressure и дедлайны. | `/Docs/brief.md`, "Механизм работы платформы" |
| timeout failure_reason | Значение `failure_reason = 'timeout'` у Job при превышении `T_sync_response`; приводит к отмене и очистке временных данных. | `/Docs/brief.md`, "Механизм работы платформы" |
| media public link | Публичная ссылка на временный файл, предназначена для скачивания провайдерами (например, Turbotext). | `/Docs/brief.md`, "Временное публичное медиа-хранилище" |
| webhook | Обратный вызов от Turbotext при асинхронной обработке, содержит `asyncid`/`queueid`. | `/Docs/brief.md`, раздел "Turbotext: очередь, polling и webhook" |
