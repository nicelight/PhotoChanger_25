# Image API — edits (параметры, base64)

Эндпоинт: `POST https://api.openai.com/v1/images/edits`

Источник: https://platform.openai.com/docs/api-reference/images/createEdit

## Обязательные параметры
- `image` (string|array): изображения для редактирования. Для GPT Image моделей: `png`/`webp`/`jpg`, < 50MB, до 16 файлов. Для DALL-E 2: один квадратный `png` < 4MB.
- `prompt` (string): описание желаемого результата. Максимум 32000 символов для GPT Image моделей.

## Опциональные параметры (актуально для GPT Image моделей)
- `background` (string|null, default `auto`): `transparent`/`opaque`/`auto`. При `transparent` формат должен поддерживать прозрачность (png/webp).
- `output_format` (string|null, default `png`): `png`/`jpeg`/`webp`.
- `output_compression` (int 0–100, default 100): только для `jpeg`/`webp`.
- `quality` (string|null, default `auto`): `high`/`medium`/`low` (для GPT Image).
- `size` (string|null, default `auto`): `1024x1024`, `1536x1024`, `1024x1536`, `auto`.
- `partial_images` (int, default 0): 0–3, количество частичных изображений при стриминге.
- `stream` (bool, default false): стриминговый режим; поддерживается только GPT Image моделями.

## Опциональные параметры (дополнительно)
- `mask` (file): PNG < 4MB, те же размеры, что и `image`; применяется к первому изображению.
- `model` (string): `dall-e-2`, `dall-e-3` или GPT Image модели.
- `n` (int, default 1): 1–10 (для DALL-E 3 только 1).
- `response_format` (string|null, default `url`): **не поддерживается GPT Image моделями**, они всегда возвращают base64-encoded изображения.
- `user` (string): идентификатор конечного пользователя.

Источник: https://platform.openai.com/docs/api-reference/images/createEdit

## Минимальный пример (успех)
```json
{
  "created": 1713833628,
  "data": [
    { "b64_json": "<BASE64_IMAGE_DATA>" }
  ]
}
```
