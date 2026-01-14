# Gemini 3 Pro Image Preview (gemini-3-pro-image-preview)

## Главное (base64 only)
- Модель: `gemini-3-pro-image-preview` (Preview).
- Генерация и редактирование изображений выполняется через `generateContent`.
- Изображения передаются и возвращаются как base64 в `inline_data`.
- Для получения изображений нужно включить `responseModalities` с `"IMAGE"` (например `["TEXT","IMAGE"]` или только `["IMAGE"]`).
- Авторизация: заголовок `x-goog-api-key: $GEMINI_API_KEY`.

Источник:
- https://ai.google.dev/gemini-api/docs/models#gemini-3-pro-image-preview
- https://ai.google.dev/gemini-api/docs/image-generation#gemini-image-editing

## ImageConfig: aspect_ratio и resolution
- `aspect_ratio` задаётся в `imageConfig.aspectRatio`.
- `resolution` задаётся в `imageConfig.imageSize` и принимает `1K`, `2K`, `4K`.
- Доступные aspect_ratio и соответствующие разрешения — см. таблицу в `image-config.md`.

Источник:
- https://ai.google.dev/gemini-api/docs/image-generation#gemini-image-editing

## Retries
- `retry_policy.max_attempts` (<= 3) и `retry_policy.backoff_seconds` (default 2s) для transient ошибок.
- `NO_IMAGE`: до 5 попыток с паузой 3s при наличии времени до дедлайна.

## Логирование
- Логи драйвера: `provider`, `model`, `http_status`, `provider_error_message` (<= 300), без payload.
- Логи ingest: только итоговый статус (success/timeout/provider_error).
