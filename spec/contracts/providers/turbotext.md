# Turbotext — контракт провайдера

## Общие сведения
- Базовый URL: `https://www.turbotext.ru/api_ai`.
- Формат запросов: `application/x-www-form-urlencoded`.
- Авторизация: заголовок `Authorization: Bearer {APIKEY}` обязателен для всех вызовов (API-ключ выдаётся сервисом Turbotext).
- Любая операция состоит из двух фаз:
  1. `do=create_queue` — постановка задачи, в ответ приходит `{"success":true,"queueid":<ID>}`.
  2. `do=get_result` — опрос очереди с передачей `queueid`. Пока задача не готова, `status` равен `processing`.

## Ингест-ограничения
- Допустимые MIME: `image/jpeg`, `image/png`, `image/webp`. Любые другие форматы отклоняются ещё на этапе ingest/UI, чтобы не тратить биллинг.
- Рекомендованный предел размера файла: ≤ 50 МБ. Превышение приводит к `413 Payload Too Large`.
- Все публичные ссылки (`media_object`) должны жить минимум `T_sync_response`; просроченные URL возвращают `410 Gone`, Turbotext прекращает обработку.
- Polling результата обязан завершиться в пределах `T_sync_response` (по умолчанию 48 с). Иначе PhotoChanger возвращает `504` с `failure_reason=provider_timeout`, очищает временные данные.

## Поддерживаемые операции

### Общий протокол
- `POST /api_ai/{method}` с телом `do=create_queue&...`.
- Уникальные параметры операции передаются в теле (`content`, `url`, `url_image_target`, и т.д.).
- После получения `queueid` клиент опрашивает `do=get_result&queueid=...`.
- Адаптер ограничивает частоту poll-запросов (не чаще 1 раза в 2-3 с) и прерывает цикл при первой ошибке или истечении `T_sync_response`.

### `image_edit` — `/api_ai/generate_image2image`
- Поля: `content` (описание правок), `photo_url` (URL исходного фото), опционально `mask_url`, `style`.
- Ответ `get_result`: JSON c `status` и `result_url`. При `status="processing"` задача ещё выполняется.
- Ошибки (`error="face_not_found"`, `error="size_error"`) транслируются в `failure_reason='provider_error'`.

### `style_transfer` — `/api_ai/mix_images`
- Поля: `content` (описание эффекта), `url_image_target` (фото пользователя), `url` (шаблон/стиль).
- Жизненный цикл: `create_queue` → `{"queueid":...}` → несколько `get_result`. Итоговый ответ содержит `result_url`.
- При отсутствующих ссылках Turbotext возвращает `{"success":false,"error":"url_error"}`.

### `identity_transfer` — `/api_ai/deepfake_photo`
- Поля: `content`, `photo1_url` (фон/тело), `photo2_url` (лицо). Дополнительные флаги (`quality`, `alignment`, `face_blur`) кодируются отдельными параметрами.
- Итоговый ответ: `status="success"` и `result_url`. Возможные ошибки — `face_not_detected`, `quality_limit`.

## Лимиты и квоты провайдера
- Turbotext тарифицирует каждую операцию; повторные `create_queue` списываются отдельно, поэтому ретраи следует выполнять только при `error` или `provider_busy`.
- Ограничение частоты — до 1 запроса в секунду. Рекомендуемая задержка между polling-запросами ≥ 2 секунды.
- Публичные ссылки на результаты действуют 24–48 ч и могут быть одномоментными. PhotoChanger должен скачать файл и сохранить локально сразу после получения `result_url`.
- При превышении квот провайдер возвращает ошибки `{"success":false,"error":"LIMIT"}` или HTTP 429. Адаптер транслирует их в `429`/`503` с `failure_reason='provider_error'`.

## Обработка ошибок и SLA
- Ошибки формата (MIME/размер) перехватываются до обращения к Turbotext.
- Ответ Turbotext с `success=false` или `status="error"` приводит к `502`/`503` на ingest (`failure_reason='provider_error'`, `details` — текст из ответа).
- Если `get_result` не успевает завершиться до `T_sync_response`, запрос прерывается, возвращается `504` (`status='timeout'`, `failure_reason='provider_timeout'`).
- Допускается один ретрай `create_queue`, если ошибка `provider_busy` и в окне `T_sync_response` остаётся ≥ 5 с; в остальных случаях задача завершается ошибкой.

## Примечания по данным
- `Slot.settings_json` хранит параметры операций и идентификаторы `template_media`. Перед вызовом API адаптер преобразует их в публичные URL.
- Полученный `result_url` скачивается, сохраняется в `media/results/{job_id}` и фиксируется в `job_history`.
- Очистка временных ссылок (`media_object`) выполняется после завершения работы либо cron-скриптом; повторное использование URL запрещено.
