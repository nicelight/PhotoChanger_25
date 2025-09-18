# Рекомендации по именам (для ТЗ / API / UI)

## API / multipart поля (рекомендуемые ключи)

* **`content_image`** — ваше фото (исходное, «контент»).
* **`style_image`** — изображение-образец (шаблон, «стиль» / reference).
* Доп. поля формы: `model` (string), `template_id` (optional), `method` (string).

## Альтернативы (короткие ключи, совместимость)

* `image`, `image2` — если DSLR шлёт только один файл, принимать любую первую часть.
* Для backward-compatibility: `file`, `photo`, `reference`.

## UI-лейблы (русский)

* «Исходное фото (ваше)»
* «Шаблон / Пример стиля»
* «Модель»
* «Метод смешивания»
* «Интенсивность эффекта (strength)»

## Названия файлов на диске / в хранилище

Формат: `{timestamp}_{uuid}_{role}.{ext}`

* Пример: `20250917T1920_3f9a1b_content.jpg`
* Пример: `20250917T1920_3f9a1b_style.png`

Дополнительно хранить JSON-метаданные:

```json
{
  "id": "uuid",
  "filename_content": "..._content.jpg",
  "filename_style": "..._style.png",
  "model": "art-v1",
  "method": "style_transfer",
  "strength": 0.8,
  "created_at": "2025-09-17T19:20:00Z",
  "status": "done"
}
```
