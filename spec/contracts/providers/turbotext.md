# Turbotext — контракт провайдера

## Общие сведения
- Интеграция выполняется через REST API Turbotext (`https://www.turbotext.ru`) с формой `application/x-www-form-urlencoded`.
- Авторизация: заголовок `Authorization: Bearer {APIKEY}` обязателен для всех вызовов.

## Ингест-ограничения
- Допустимые входные форматы: `image/jpeg`, `image/png`, `image/webp`. Форматы HEIC/HEIF отклоняются на этапе ingest/UI.
- Ингест завершает запрос при наступлении `T_sync_response` (504, `failure_reason = 'timeout'`)

## Поддерживаемые операции
### Общий протокол
TODO

### `image_edit` (`/api_ai/generate_image2image`)

### `style_transfer` (`/api_ai/mix_images`)

### `identity_transfer` (`/api_ai/deepfake_photo`)

## Лимиты и квоты провайдера

- Turbotext учитывает каждую операцию как биллинговую единицу; повторные попытки требуют нового `create_queue`.
- TTL публичных ссылок должен соответствовать `T_public_link_ttl = T_sync_response`; просрочка ведёт к ошибкам скачивания (`410 Gone`).

## Обработка ошибок и SLA
- Ошибки формата (например, неподдерживаемый MIME) должны отлавливаться до обращения к Turbotext.


## Примечания по данным
- `Slot.settings_json` хранит идентификаторы `template_media` и `media_object`; адаптер конвертирует их в публичные URL при вызове API.
- Результирующий файл скачивается и сохраняется под `MEDIA_ROOT/results`, а метаданные фиксируются.
- Очистка временных файлов выполняется после финализации задачи или по истечении TTL фоновой процедурой.
