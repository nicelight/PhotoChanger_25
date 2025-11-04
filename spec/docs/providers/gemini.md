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

const result = await model.generateContent({
  contents: [
    {
      role: "user",
      parts: [{ text: "Create a vintage postcard style photo of the Eiffel Tower" }],
    },
  ],
});

const imageBase64 = result.response.candidates[0].content.parts[0].inlineData.data;
```

### Python (`google-generativeai`)

```python
import google.generativeai as genai

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.5-flash-image")

response = model.generate_content(
    [
        {
            "role": "user",
            "parts": [
                {"text": "Create a neon cyberpunk city skyline at night"},
            ],
        }
    ]
)

image_base64 = response.candidates[0].content.parts[0].inline_data.data
```

## Рекомендации для PhotoChanger

- Сохраняйте `job.metadata["provider"]` и параметры слота, чтобы адаптер мог подставить нужную конфигурацию (операция, стили, дополнительные изображения).
- Передавайте файлы через Files API при размере > 20 MB или при повторном использовании (`template_media`).
- Следите за лимитами RPM/TPM: при `RESOURCE_EXHAUSTED` реализуйте экспоненциальный backoff.
- При `PROCESSING`/`FAILED_PRECONDITION` делайте повторный опрос Files API, прежде чем запускать `generateContent`.

