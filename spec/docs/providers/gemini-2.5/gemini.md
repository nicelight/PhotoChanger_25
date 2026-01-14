# Провайдер Gemini (изображения)

https://ai.google.dev/gemini-api/docs/image-generation

> Статус: сведения из официальной документации Gemini API на октябрь 2024 года. Материал охватывает генерацию изображений, редактирование по текстовому промпту и работу с Files API.

## Поддерживаемые модели и сценарии

| Модель | Особенности |
| --- | --- |
| `gemini-2.5-flash-image` | Основная модель для обработки фотографий людей. Поддерживает смешение нескольких изображений (inline_data или file_data) и текстового промпта. |

> **PhotoChanger** использует один унифицированный сценарий: исходное фото (ingest), текстовый промпт и набор опциональных референсов. Главный приоритет — сохранить лица и фигуры людей на снимке, любые трансформации выполняются вокруг них.



## Метод вызова

```python
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

client = genai.Client()

prompt = (
    "Create a picture of my cat eating a nano-banana in a "
    "fancy restaurant under the Gemini constellation",
)

# img1_bytes = f1.read()
image1 = types.Part.from_bytes(
  data=image1_bytes, mime_type="image/jpeg"
)

# img2_bytes = some_bytes
image2 = types.Part.from_bytes(
  data=image2_bytes, mime_type="image/png"
)

response = client.models.generate_content(
    model="gemini-2.5-flash-image",
    contents=[prompt, image1, image2],
)

image_parts = [
    part.inline_data.data
    for part in response.candidates[0].content.parts
    if part.inline_data
]

if image_parts:
    image = Image.open(BytesIO(image_parts[0]))
    image.save('cat_eats_banana.png')
    image.show()
```


примеры промптов https://ai.google.dev/gemini-api/docs/image-generation#python_1



Все операции выполняются методом [`models.generateContent`](https://ai.google.dev/api/generate-content?utm_source=chatgpt.com) с указанием нужной модели. Базовый REST-вызов:

POST to endpoint: `https://generativelanguage.googleapis.com/v1beta/{model=models/*}:generateContent `

```http
POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent
x-goog-api-key: <GEMINI_API_KEY>
Content-Type: application/json

{
  "contents": [
    {
      "role": "user",
      "parts": [
        { "text": "Create a high-key studio portrait of a violinist" }
      ]
    }
  ]
}
```

Ответ содержит массив кандидатов; готовое изображение приходит в `candidates[0].content.parts[n].inline_data.data` (base64-строка PNG).

## Структура входа `contents`

Каждый элемент `contents` описывает один ход диалога. Части (`parts`) могут смешивать текст и мультимедиа:

- `text`: обычный промпт.
- `inline_data`: объект `{"mime_type": "image/png", "data": "<base64>"}` для небольших изображений, передаваемых напрямую.
- `file_data`: объект `{"mime_type": "image/jpeg", "file_uri": "files/abc123"}` — ссылка на файл, загруженный через Files API.

Для наших сценариев PhotoChanger формирует `contents` следующим образом:

1. `inline_data` с ingest-фотографией людей (обязательный элемент).
2. `text` с инструкцией (`slot.settings.prompt`).
3. Опциональные `inline_data` из списка `template_media` (фон, стиль, атрибуты бренда). Если для роли не найден файл, драйвер пропускает её, если не указано обратное.

Такой подход позволяет изменять окружение, стиль или фон, не трогая лица/фигуры.

### Пример (multi-image fusion)

```json
{
  "model": "gemini-2.5-flash-image",
  "contents": [
    {
      "role": "user",
      "parts": [
        {"file_data": {"mime_type": "image/png", "file_uri": "files/hero_pose"}},
        {"file_data": {"mime_type": "image/png", "file_uri": "files/fantasy_background"}},
        {"text": "Compose a cinematic poster where the hero stands in the fantasy scene, matching the lighting."}
      ]
    }
  ]
}
```

## Files API

Files API используется для передачи крупных изображений или длительного хранения между запросами. Подход: загрузить файл, получить `file.uri` (например, `files/abc123`), подставить его в `file_data`.

| Операция | REST-эндпоинт | Примечания |
| --- | --- | --- |
| Создать «resumable upload» | `POST https://generativelanguage.googleapis.com/upload/v1beta/files` | Заголовки `X-Goog-Upload-Protocol: resumable`, `X-Goog-Upload-Command: start`; тело `{ "file": { "display_name": "example.png" } }`. В ответе заголовок `X-Goog-Upload-URL`. |
| Передать байты | `PUT`/`POST` на `X-Goog-Upload-URL` | Заголовки `X-Goog-Upload-Command: upload, finalize`, `Content-Length`, `X-Goog-Upload-Offset`. |
| Получить метаданные | `GET https://generativelanguage.googleapis.com/v1beta/files/{name}` | Возвращает JSON c `file.uri`, `state`, `mime_type`, `size_bytes`, `create_time`. |
| Удалить файл | `DELETE https://generativelanguage.googleapis.com/v1beta/files/{name}` | Файл удаляется досрочно. |

Пока файл активен (48 часов), его можно переиспользовать в нескольких запросах.

## Лимиты и ограничения

| Ограничение | Значение | Источник |
| --- | --- | --- |
| Максимальный размер одного файла в Files API | 2 ГБ | [Files API Usage info](https://ai.google.dev/gemini-api/docs/files?utm_source=chatgpt.com) |
| Суммарное хранилище на проект | 20 ГБ | [Files API Usage info](https://ai.google.dev/gemini-api/docs/files?utm_source=chatgpt.com) |
| Срок хранения файла | 48 часов | [Files API Usage info](https://ai.google.dev/gemini-api/docs/files?utm_source=chatgpt.com) |
| Поддерживаемые входные MIME | `image/png`, `image/jpeg`, `image/webp`, `image/heic`, `image/heif` | [Image understanding guide](https://ai.google.dev/gemini-api/docs/image-understanding?utm_source=chatgpt.com#supported-formats) |
| Базовый лимит для `gemini-2.5-flash-image` | 500 RPM, 500 000 TPM, 2 000 RPD (Tier 2) | [Rate limits таблица](https://ai.google.dev/gemini-api/docs/rate-limits?utm_source=chatgpt.com) |

Дополнительно: для больших изображений модель автоматически тайлит вход до 768×768 px тайлов (см. раздел про токенизацию изображений в гайде по image understanding). Для inline-передачи учитывайте размер payload — крупные файлы удобнее хранить в Files API.

## Ошибки и валидация

Gemini API использует стандартные коды Google RPC:

- `400 INVALID_ARGUMENT` — неподдерживаемый MIME, превышение лимитов, некорректная структура `contents`.
- `403 PERMISSION_DENIED` — неверный API-ключ или запрет для проекта.
- `404 NOT_FOUND` — ссылка на несуществующий `file_uri`.
- `409 FAILED_PRECONDITION` — использование файлов в состоянии `PROCESSING`.
- `429 RESOURCE_EXHAUSTED` — превышение квот (RPM/IPM/TPM или лимиты Files API).
- `500 INTERNAL` / `503 UNAVAILABLE` — сбои на стороне сервиса.

В ответе ошибки приходит объект `error` с полями `code`, `message`, `status` и, при наличии, `details[]`.

## Аутентификация и квоты

- **API-ключ**: передаётся заголовком `x-goog-api-key` либо параметром `key` в URL (для серверных сценариев используйте заголовок).
- **OAuth2 / сервисные аккаунты**: применяются при работе через Vertex AI, но не требуются для публичного Gemini API с ключами AI Studio.
- **Квоты и апгрейд**: лимиты RPM/TPM/IPM зависят от тарифного Tier (Free, Paid). Повышение квот происходит через AI Studio (кнопка “Upgrade” после выполнения условий) или через форму запроса на повышение лимитов.

## Неподдерживаемые возможности

- Маски (инпейтинг/аутпейтинг) и другие операции, требующие пиксельных масок, не реализованы.
- Нет прямого скачивания файлов через Files API — можно только получать метаданные.
- Генерация возвращает PNG; управление размером/соотношением сторон ограничено подсказками, явных параметров ширины/высоты нет.

## Настройки слота PhotoChanger (Gemini)

Конфигурация хранится в `slot.settings_json` и валидируется схемой `slot-settings-gemini.schema.json`.

```json
{
  "model": "gemini-2.5-flash-image",
  "prompt": "Describe desired result, e.g. keep faces, replace background with studio lights",
  "output": { "mime_type": "image/png" },
  "template_media": [
    {
      "role": "reference_background",
      "media_kind": "background",
      "optional": true
    },
    {
      "role": "brand_overlay",
      "media_object_id": "mo_overlay_logo",
      "optional": true
    }
  ],
  "retry_policy": { "max_attempts": 2, "backoff_seconds": 2.0 }
}
```

- **prompt** — обязательная инструкцию для модели, обязательно содержит указания «сохранить лица/людей».
- **template_media** — список дополнительных изображений (фон, стиль, логотипы). Для каждого элемента указывается либо `media_kind`, либо `media_object_id`, флаг `optional` разрешает пропустить отсутствующий файл.
- **output.mime_type** — целевой формат ответа.
- **retry_policy** и `safety_settings` (не показаны выше) позволяют тонко настроить поведение при ошибках и фильтрах Gemini.

## Ретраи (driver-level)
- Ретраи выполняет драйвер провайдера; ingest только ограничивает общий таймаут `T_sync_response`.
- `retry_policy.max_attempts` ≤ 3, `backoff_seconds` по умолчанию 2s (применяется к transient ошибкам, например `RESOURCE_EXHAUSTED`/`DEADLINE_EXCEEDED`).
- Если Gemini вернул `finishReason=NO_IMAGE`, выполняются до 5 попыток с паузой 3s, только если это укладывается в дедлайн `T_sync_response`; иначе фиксируется `provider_timeout`.

## Логирование (KISS)
- Драйвер пишет подробные логи провайдера, ingest — итоговый статус (success/timeout/provider_error).
- Минимальные поля: `slot_id`, `job_id`, `provider`, `model`, `http_status`, `error_message` (усечённая до 300 символов).
- Запрещено логировать payload и большие response body.

## Рекомендации для PhotoChanger

- Перед формированием `prompt` явно указывайте, что лица людей должны сохраниться («keep all faces intact», «preserve original pose and expressions»).
- `template_media` используйте для фона, фирменных элементов, референсов освещения. При размере файла > 20 МБ стоит грузить его в Files API и ссылаться через `file_data`.
- Обрабатывайте `RESOURCE_EXHAUSTED`/`DEADLINE_EXCEEDED` с учётом `retry_policy`: максимум 2 попытки, пауза ≥2 секунды.
- Все загруженные из UI тестовые изображения проходят ту же цепочку, что и ingest: временный диск → `inline_data` → ответ → запись в `media/results`.

