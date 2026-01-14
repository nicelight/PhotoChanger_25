# Base64 inline_data (input/output)

## Входные изображения (редактирование)
- Изображения отправляются в `inline_data` c `mime_type` и `data` (base64).
- Документация прямо показывает пример "base64 encoded images" и структуру:
  - `"inline_data": {"mime_type": "image/png", "data": "<BASE64_IMAGE_DATA>"}`

## Выходные изображения
- В ответе изображения приходят как `inline_data.data` (base64).
- Пример обработки: извлечь base64 и сохранить в файл (JS/Python примеры в документации).

Источник:
- https://ai.google.dev/gemini-api/docs/image-generation#gemini-image-editing

## Минимальный пример (успех)
Структура запроса и ответа из документации (REST, сокращено):

```json
{
  "model": "gemini-3-pro-image-preview",
  "contents": [
    {
      "role": "user",
      "parts": [
        {
          "inline_data": {
            "mime_type": "image/png",
            "data": "<BASE64_IMAGE_DATA>"
          }
        },
        { "text": "Update this infographic to be in Spanish." }
      ]
    }
  ],
  "generationConfig": {
    "responseModalities": ["TEXT", "IMAGE"]
  }
}
```

```json
{
  "candidates": [
    {
      "content": {
        "parts": [
          {
            "inline_data": {
              "mime_type": "image/png",
              "data": "<BASE64_IMAGE_DATA>"
            }
          }
        ]
      }
    }
  ]
}
```
