# Turbotext — контракт провайдера

## Общие сведения
- Интеграция выполняется через HTTP API Turbotext с очередью: задачи регистрируются запросом `do=create_queue`, а результат читается polling-запросом `do=get_result` либо принимается через webhook с тем же форматом JSON.【F:Docs/brief.md†L300-L350】
- Провайдер работает с публичными ссылками на изображения и не хранит файлы: воркер обязан выдавать URL, доступные не менее `T_public_link_ttl = clamp(T_sync_response, 45, 60)` секунд, опираясь на дедлайн `Job.expires_at = max(T_sync_response, T_public_link_ttl)` для синхронной очистки и отмены.【F:Docs/brief.md†L19-L137】

## Ингест-ограничения
- Допустимые MIME: `image/jpeg`, `image/png`, `image/webp`; остальные форматы отклоняются ещё на этапе ingest/UI.【F:Docs/brief.md†L674-L678】【F:Docs/brief.md†L102-L115】
- Максимальный размер входного файла — 15 МБ; превышение приводит к ошибке валидации до обращения к Turbotext.【F:Docs/brief.md†L672-L680】
- Провайдер требует подготовленные публичные ссылки (`requires_public_media = true`), поэтому воркер обязан регистрировать временные файлы через `media_object` и контролировать TTL `T_public_link_ttl`, чтобы Turbotext гарантированно успел скачать их в пределах окна задачи.【F:Docs/brief.md†L19-L137】
- Параллелизм ограничен двумя одновременными задачами на провайдера; остальные ожидают в очереди платформы.【F:Docs/brief.md†L669-L686】
- В ожидании синхронного ответа API придерживается `timeout_sec = 48`; по истечении окна ingest завершает запрос кодом 504 и фиксирует `failure_reason = 'timeout'`.【F:Docs/brief.md†L672-L686】【F:Docs/brief.md†L31-L48】

## Поддерживаемые операции
### `style_transfer`
- Назначение: смешивание стилевого и целевого изображения для переноса художественного стиля.【F:Docs/brief.md†L692-L707】
- Endpoint Turbotext: `/api_ai/mix_images` с полями формы `url_image_target`, `url`, `content` и флагом очереди.【F:Docs/brief.md†L700-L711】
- Обязательные настройки слота: `prompt`, `target_media_id`, `style_media_id`; валидируются по общей схеме операции.【F:Docs/brief.md†L693-L733】
- Маппинг полей: воркер подставляет публичные ссылки шаблонных изображений (`template_media`) в `url_image_target`/`url`, а текстовый промпт — в `content`. Результат приходит ссылкой `uploaded_image`, которую нужно скачать и записать в поля `Job.result_*` (например, `result_file_path` + метаданные).【F:Docs/brief.md†L704-L710】【F:Docs/brief.md†L333-L350】

### `image_edit`
- Назначение: image-to-image редактирование по текстовому описанию с дополнительными параметрами силы эффекта, seed и масштаба.【F:Docs/brief.md†L738-L789】
- Endpoint Turbotext: `/api_ai/generate_image2image`; используется очередь и (при наличии) webhook.【F:Docs/brief.md†L753-L766】【F:Docs/brief.md†L300-L350】
- Обязательные настройки: `prompt` и `source_media_id`; опционально — `strength`, `seed`, `scale`, `negative_prompt`, `original_language`, параметры блока `output`.【F:Docs/brief.md†L741-L788】
- Маппинг полей формы: `url` ← публичная ссылка по `source_media_id` (`media_object`), `content` ← `prompt`, остальные числовые и строковые поля подставляются согласно `field_map`. Результирующая ссылка `uploaded_image` скачивается и сохраняется в полях `Job.result_*`.【F:Docs/brief.md†L754-L766】【F:Docs/brief.md†L333-L350】

### `identity_transfer`
- Назначение: deepfake/face swap с использованием фотографий субъекта и лица; выполняется через очередь Turbotext.【F:Docs/brief.md†L791-L813】【F:Docs/brief.md†L300-L350】
- Endpoint Turbotext: `/api_ai/deepfake_photo` с полями `url`, `url_image_target`, `face_restore` и поддержкой webhook.【F:Docs/brief.md†L805-L813】
- Обязательные настройки: `subject_media_id`, `face_media_id`; опционально `face_restore`, `output`.【F:Docs/brief.md†L795-L845】
- Маппинг: `subject_media_id` и `face_media_id` конвертируются в публичные ссылки из `template_media`; булевый `face_restore` передаётся напрямую. Финальный `uploaded_image` скачивается и сохраняется в полях `Job.result_*` как файл (`result_file_path` + метаданные).【F:Docs/brief.md†L805-L810】【F:Docs/brief.md†L333-L350】

## Лимиты и квоты провайдера
- Turbotext потребляет публичные ссылки с TTL `T_public_link_ttl = clamp(T_sync_response, 45, 60)` и форматами JPEG/PNG/WEBP; воркер не продлевает ссылки автоматически, повторная регистрация выполняется заново по необходимости.【F:Docs/brief.md†L108-L137】
- API работает по модели очереди: повторные попытки polling-а получают `{"action": "reconnect"}` без штрафа; нужно соблюдать собственные ограничения Turbotext по частоте опроса (не указаны в брифе) и обрабатывать `limits` в ответе для мониторинга квот.【F:Docs/brief.md†L328-L346】

## Обработка ошибок и SLA
- Интеграция подчиняется общему дедлайну `T_sync_response` ≤ 48 с: по его наступлении ingest завершает запрос 504, воркер отправляет отмену в очередь и очищает временные файлы.【F:Docs/brief.md†L31-L48】【F:Docs/brief.md†L102-L115】
- Если Turbotext возвращает `success=false` или не предоставляет результат до дедлайна, задача фиксирует `failure_reason = 'provider_error'` либо `'timeout'`; повторные попытки не планируются — для новой обработки оператор отправляет новый POST.【F:Docs/brief.md†L45-L59】【F:Docs/brief.md†L300-L350】
- Истечение публичной ссылки (HTTP 410) трактуется как ошибка подготовки данных; при повторном запуске воркер обязан заново зарегистрировать `media_object` перед обращением к провайдеру.【F:Docs/brief.md†L102-L115】【F:Docs/brief.md†L250-L262】

## Примечания по данным
- `Slot.settings_json` хранит идентификаторы `template_media` и `media_object`; воркер преобразует их в публичные URL перед вызовом API Turbotext и не продлевает TTL автоматически.【F:Docs/brief.md†L865-L900】【F:Docs/brief.md†L102-L115】
- После завершения задачи результат скачивается по `uploaded_image` и сохраняется в полях `Job.result_*`; временные исходные файлы удаляются по окончании задачи или истечению TTL.【F:Docs/brief.md†L17-L20】【F:Docs/brief.md†L333-L350】
