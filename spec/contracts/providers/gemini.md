# Gemini — контракт провайдера

## Общие сведения
- Провайдер поддерживает генерацию, редактирование, multi-image fusion и перенос стиля на модели `gemini-2.5-flash-image` через метод `models.generateContent` с передачей текста и изображений в `contents.parts` (`text`, `inline_data`, `file_data`).【F:Docs/brief.md†L21-L25】
- Все операции вызываются синхронно; при необходимости передачи крупных файлов используется Files API с `file_uri` (хранение 48 ч, до 2 ГБ на файл и 20 ГБ на проект).【F:Docs/brief.md†L23-L25】

## Ингест-ограничения
- Допустимые MIME: `image/jpeg`, `image/png`, `image/webp`, `image/heic`, `image/heif` (валидатор ingest и UI обязаны придерживаться списка).【F:Docs/brief.md†L653-L659】
- Максимальный размер входного файла — 20 МБ; более крупные файлы отклоняются до попытки обращения к провайдеру.【F:Docs/brief.md†L650-L661】
- Параллелизм для слотов Gemini ограничен четырьмя одновременными задачами; превышение должно ставить новые задачи в очередь.【F:Docs/brief.md†L650-L666】
- Синхронное ожидание ответа ограничено актуальным `T_sync_response`; по истечении дедлайна ingest прекращается кодом 504 и задача получает `failure_reason = 'timeout'`.【F:Docs/brief.md†L4-L28】【F:Docs/brief.md†L92-L95】

## Поддерживаемые операции
### `style_transfer`
- Назначение: перенос художественного стиля между изображениями; Gemini использует эталонное изображение как источник стиля и применяет его к входному фото.【F:Docs/brief.md†L692-L707】
- Endpoint: `/v1beta/models/gemini-image:transferStyle` (POST `models.generateContent`).【F:Docs/brief.md†L700-L707】
- Обязательные настройки: `prompt` (общая), `reference_media_id` (UUID шаблонного или временного медиа, доступного воркеру).【F:Docs/brief.md†L693-L733】
- Дополнительные параметры: `style_strength` (0–1, default 0.65) и блок `output` (`format`, `max_side_px`).【F:Docs/brief.md†L718-L726】
- Подготовка данных: воркер загружает `reference_media_id` в Files API (если не передан `file_uri`) и добавляет его в `contents.parts` как `file_data`; текстовый промпт передаётся в `text` части.【F:Docs/brief.md†L23-L25】【F:Docs/brief.md†L713-L727】

### `image_edit`
- Назначение: локальное редактирование входного изображения с поддержкой image-to-image и текстовых подсказок.【F:Docs/brief.md†L738-L789】
- Endpoint: `/v1beta/models/gemini-image:edit` (POST `models.generateContent`).【F:Docs/brief.md†L747-L752】
- Обязательные настройки: `prompt`; остальные параметры (`guidance_scale`, `output` и т. д.) опциональны и валидируются по схеме операции.【F:Docs/brief.md†L741-L788】
- Медиавложения: исходное изображение подставляется из входящего ingest (`media_parts` → `ingest_media`) как `inline_data` или загружается в Files API при превышении лимитов прямой передачи; дополнительные ссылки из настроек не требуются.【F:Docs/brief.md†L748-L752】【F:Docs/brief.md†L23-L25】

### `identity_transfer`
- Назначение: совмещение или замена лица между изображениями при помощи compose-операции Gemini.【F:Docs/brief.md†L791-L813】
- Endpoint: `/v1beta/models/gemini-image:compose`.【F:Docs/brief.md†L801-L803】
- Обязательные настройки: `base_media_id` и `overlay_media_id` (оба UUID), а также текстовый `prompt` при необходимости донастройки сцены; допускается дополнительный блок `alignment` и настройки `output`.【F:Docs/brief.md†L795-L845】
- Подготовка данных: воркер превращает оба изображения в `file_data`/`file_uri` части с соблюдением форматов Files API и прикладывает промпт в текстовую часть запроса.【F:Docs/brief.md†L23-L25】【F:Docs/brief.md†L815-L838】

## Лимиты и квоты провайдера
- Files API: ≤ 2 ГБ на файл, ≤ 20 ГБ на проект, хранение 48 ч; допустимые форматы — JPEG/PNG/WebP/HEIC/HEIF.【F:Docs/brief.md†L23-L25】
- Квоты модели Tier 2: 500 запросов в минуту, 2 000 запросов в день, 500 000 токенов в минуту — нужно учитывать при планировании ретраев и ограничении параллельности задач.【F:Docs/brief.md†L23-L25】

## Обработка ошибок и SLA
- Рабочий таймаут ingest равен текущему `T_sync_response`; если провайдер не ответил в пределах окна, задача отменяется с 504 и воркер прерывает обращение к Gemini.【F:Docs/brief.md†L4-L28】
- При возврате ошибок Gemini воркер помечает задачу как `failed_provider`, освобождает ресурсы и транслирует 502/504 на ingest-API (в зависимости от контекста ошибки).【F:Docs/brief.md†L45-L51】
- Повторные попытки в рамках одной задачи не выполняются: при ошибке или превышении лимитов Files API оператор отправляет новый POST; воркер фиксирует `failure_reason` и освобождает ресурсы.【F:Docs/brief.md†L54-L59】【F:Docs/brief.md†L23-L25】

## Примечания по данным
- `Slot.settings_json` должен соответствовать схеме операций; ссылки на шаблоны (`template_media`) и временные файлы (`media_object`) подставляются в поля настроек и конвертируются в `file_data`/`file_uri` перед вызовом API.【F:Docs/brief.md†L865-L900】
- Все преобразования выполняются в пределах ограничений `T_ingest_ttl`/`T_sync_response`; продление временных ссылок воркером запрещено, поэтому подготовка данных должна укладываться в TTL файлов.【F:Docs/brief.md†L17-L64】【F:Docs/brief.md†L102-L115】
