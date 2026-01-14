# GPT-image-1.5 (base64 only) — краткая справка

## Главное
- GPT Image модели: `gpt-image-1.5`, `gpt-image-1`, `gpt-image-1-mini`.
- Два API: Image API (эндпоинты generations/edits/variations) и Responses API (image_generation tool).
- В Image API результат возвращается как base64-encoded изображение.
- Авторизация: заголовок `Authorization: Bearer $OPENAI_API_KEY`.

Источник: https://platform.openai.com/docs/guides/image-generation#edit-images

## Base64-вывод
- В Image API ответы возвращаются base64-encoded.
- Параметр `response_format` применим к DALL-E 2/3 (url или b64_json), но **не** поддерживается GPT Image моделями — они всегда возвращают base64-encoded изображение.

Источник: https://platform.openai.com/docs/api-reference/images/createEdit

## Входные изображения для edits
- `image` обязателен: строка или массив изображений для редактирования.
- Для GPT Image моделей каждый файл должен быть `png`, `webp` или `jpg` и < 50MB; можно до 16 изображений.
- Для DALL-E 2: только одно изображение, квадратный `png` < 4MB.

Источник: https://platform.openai.com/docs/api-reference/images/createEdit

## Прочее (если нужно учитывать в интеграции)
- `prompt` обязателен; максимальная длина для GPT Image моделей — 32000 символов.
- `mask` (опционально) — PNG < 4MB, те же размеры, что и `image`, применяется к первому изображению.

Источник: https://platform.openai.com/docs/api-reference/images/createEdit

## Retries
- `retry_policy.max_attempts` (<= 3) и `retry_policy.backoff_seconds` (default 2s) для transient ошибок.

## Логирование
- Логи драйвера: `provider`, `model`, `http_status`, `provider_error_message` (<= 300), без payload.
- Логи ingest: только итоговый статус (success/timeout/provider_error).
