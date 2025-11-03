# Провайдер Gemini (изображения)

> Статус: сведения из официальной документации Gemini API на октябрь 2024 года. Материал охватывает генерацию изображений, редактирование по текстовому промпту и работу с Files API.

## Поддерживаемые модели и сценарии

| Модель | Сценарии | Особенности |
| --- | --- | --- |
| `gemini-2.5-flash-image` | Генерация изображений по промпту, редактирование «edit-with-prompt», комбинирование нескольких изображений (multi-image fusion), стилизация | Основная модель для работы с изображениями в публичном Gemini API. Подтверждена в гайде по image generation и в анонсе multi-image fusion. |


## Метод вызова

Все операции выполняются методом [`models.generateContent`](https://ai.google.dev/api/generate-content?utm_source=chatgpt.com) с указанием нужной модели. Базовый REST-вызов:

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

Для мульти-изображений добавьте несколько частей с `inline_data` или `file_data`. В редактировании «edit-with-prompt» дайте исходное изображение + текст, описывающий изменения. Multi-image fusion (объединение сцен или перенос стиля) подтверждён в [официальном анонсе Gemini 2.5 Flash Image](https://developers.googleblog.com/en/introducing-gemini-2-5-flash-image/?utm_source=chatgpt.com).

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

## Примеры кода

### JavaScript (официальная библиотека `@google/generative-ai`)

```javascript
import { GoogleGenerativeAI } from "@google/generative-ai";

const client = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
const model = client.getGenerativeModel({ model: "gemini-2.5-flash-image" });

const prompt = {
  contents: [
    {
      role: "user",
      parts: [
        { text: "Add a knitted wizard hat to this cat" },
        {
          file_data: {
            mime_type: "image/png",
            file_uri: "files/cat-original"
          }
        }
      ]
    }
  ]
};

const result = await model.generateContent(prompt);
const imageBase64 = result.response.candidates[0].content.parts[0].inline_data.data;
// Платформа PhotoChanger декодирует base64 и сохраняет файл на диск под MEDIA_ROOT/results,
// временно фиксируя исходную строку в Job.result_inline_base64, чтобы API могло отдать её DSLR,
// и обновляя поля Job.result_* (result_file_path, MIME, размер, checksum). После отправки HTTP 200
// поле result_inline_base64 очищается.
```

### Python (`google-generativeai`)

```python
import base64
import os
import google.generativeai as genai

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.5-flash-image")

response = model.generate_content([
    {
        "role": "user",
        "parts": [
            {"text": "Combine the landscape and character into a matte painting"},
            {"file_data": {"mime_type": "image/png", "file_uri": "files/landscape"}},
            {"file_data": {"mime_type": "image/png", "file_uri": "files/character"}}
        ],
    }
])

image_base64 = response.candidates[0].content.parts[0].inline_data["data"]
image_bytes = base64.b64decode(image_base64)
# Платформа PhotoChanger записывает image_bytes в файл внутри MEDIA_ROOT/results,
# проставляет Job.result_inline_base64 на время синхронного ответа ingest и
# обновляет метаданные Job.result_* вместо долгосрочного хранения base64 в очереди.
```

### REST (inline изображение)

```bash
BASE64_IMAGE=$(base64 -w 0 source.png)

curl \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -X POST "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent" \
  -d @- <<JSON
{
  "contents": [
    {
      "role": "user",
      "parts": [
        {"text": "Reimagine this room in Scandinavian minimalism"},
        {
          "inline_data": {
            "mime_type": "image/png",
            "data": "$BASE64_IMAGE"
          }
        }
      ]
    }
  ]
}
JSON
# Ответ Gemini вернёт inline_data с base64: сервис сохраняет результат как файл,
# держит строку в Job.result_inline_base64 до завершения ответа ingest и
# фиксирует путь в Job.result_file_path, очищая base64 сразу после финализации.
```

## Деградации и ретраи

### Files API зависает в `PROCESSING`
- После загрузки файла проверяйте `file.state`. Если значение не сменилось на `ACTIVE` за 5 с, выполните `GET /files/{name}` повторно.
- По превышении 10 с или получении `DEADLINE_EXCEEDED` завершайте операцию `provider_timeout`: очищайте временные ссылки, возвращайте 504.
- Повторная загрузка допустима только при остатке ≥ 15 с в окне `T_sync_response`.

### Ошибки валидации (`INVALID_ARGUMENT`, `FAILED_PRECONDITION`)
- Причины — некорректная структура `contents`, неподдерживаемый MIME, отсутствующий `file_data`.
- Ретраи запрещены: завершайте задачу `failure_reason='provider_error'`, фиксируйте проблему в логах, обновляйте валидацию слота.

### Ограничения квот (`RESOURCE_EXHAUSTED`, `429`)
- Первый ответ → backoff 5 с, повтор запрос допускается, если осталось ≥ 10 с SLA.
- Повторный отказ → завершение `provider_error`, уведомление админа через UI (блок деградаций) и перевод слота в ограниченный режим.

### Системные сбои (`UNAVAILABLE`, `500`, `503`)
- Выполняйте один повторный вызов через 3 с. Если неудачно — задача завершается `provider_error`.
- При двух и более подряд сбоях по одному слоту рекомендуется временно отключить слот и проинформировать эксплуатацию.

### Массовые таймауты
- Три и более подряд таймаута за 5 минут → включить «деградацию слота»:
  1. Отключить слот (`slot.disabled=true`).
  2. Создать запись для оповещения админа.
  3. Собрать метрики/логи, проверить Files API и лимиты.

## Ссылки

1. [Gemini API — Image generation guide](https://ai.google.dev/gemini-api/docs/image-generation?utm_source=chatgpt.com)
2. [Gemini API — Files API](https://ai.google.dev/gemini-api/docs/files?utm_source=chatgpt.com)
3. [Gemini API — Image understanding guide](https://ai.google.dev/gemini-api/docs/image-understanding?utm_source=chatgpt.com)
4. [Gemini API — Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits?utm_source=chatgpt.com)
5. [Introducing Gemini 2.5 Flash Image (Google Developers Blog)](https://developers.googleblog.com/en/introducing-gemini-2-5-flash-image/?utm_source=chatgpt.com)
