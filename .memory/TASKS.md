---
id: tasks
updated: 2026-01-21
---

# Tasks (канбан)
> Политика: вместе с имплементационными пунктами обязательно веди задачи для размышлений и консультаций с тимлидом.  Формулируй их с префиксом `CONSULT` или `REFLECT`, следуя разделу «Практика CONSULT/REFLECT» в `agents.md`. 

> Формат Kanban с иерархией:  
> `[ ]` — не начато, `[~]` — в работе, `[x]` — выполнено.  
> Уровни: **EP → FEAT → US → T**.  
---
## 📘 Формат
**Уровни задач:**
- `EP` — Epic (цель, объединяет фичи)  
- `FEAT` — Feature (функциональная часть)  
- `US` — User Story (поведение пользователя)  
- `T` — Task (конкретное действие)


## TODO
- [x] EP PHC-11 — KISS-расширяемость провайдеров
  [ ] US PHC-11.GOV — Governance & Discovery
    [x] T PHC-11.GOV.1 — CONSULT — подтвердить минимальные правила (driver checklist, порядок частей, output mime strict, error context)
    [x] T PHC-11.GOV.2 — REFLECT — зафиксировать текущую логику ретраев (Gemini/ingest) и ответственность за ретраи
    [x] T PHC-11.GOV.3 — CONSULT — подтвердить изменение template_media (только media_kind) vs текущий обязательный role (breaking)
  [x] FEAT PHC-11.1 — Внутренний стандарт драйвера и settings-схемы
    [x] T PHC-11.1.1 — Внутренний чек‑лист драйвера (input: ingest+prompt, template_media опционально; order: ingest→templates→prompt; output mime strict)
    [x] T PHC-11.1.1a — Подготовить пример (псевдокод) сборки parts: ingest → templates → prompt
    [x] T PHC-11.1.2 — Добавить JSON‑схемы `slot.settings` для Gemini 3.0 Flash и GPT‑5 (минимальный набор полей)
    [x] T PHC-11.1.2b — Схема Gemini 3.0 Flash: model/prompt/output/template_media (минимум)
    [x] T PHC-11.1.2c — Схема GPT‑5: model/prompt/output/template_media (минимум)
    [x] T PHC-11.1.2a — Проверить совместимость со слотами без output/template (минимум model/prompt)
    [x] T PHC-11.1.3 — Зафиксировать в схемах template_media с обязательным `role` (без breaking)
    [x] T PHC-11.1.4 — Зафиксировать в спеках единое требование по ретраям (как в GeminiDriver)
    [x] T PHC-11.1.4b — Обновить spec/docs/providers: единый раздел “Retries” для всех драйверов
    [x] T PHC-11.1.4a — Описать текущие пределы Gemini: retry_policy max_attempts<=3/backoff default 2s + NO_IMAGE 5x/3s с учётом дедлайна
  [x] FEAT PHC-11.2 — Логирование (KISS, без проброса контекста)
    [x] T PHC-11.2.1 — Зафиксировать в спеках распределение логов: драйверы — подробности, ingest — итоговый статус
    [x] T PHC-11.2.2 — Обновить provider docs: минимальные поля логов и запрет payload/body
    [x] T PHC-11.2.3 — Проверить, что текущие логи ingest не дублируют драйверские детали
  [x] FEAT PHC-11.3 — Тесты драйверов
    [x] T PHC-11.3.1 — Unit‑тесты: success/timeout/provider_error/invalid_response
    [x] T PHC-11.3.1b — Unit‑тесты GeminiDriver: базовые сценарии
    [x] T PHC-11.3.1c — Unit‑тесты TurbotextDriver: базовые сценарии (пока драйвер не удалён)
    [x] T PHC-11.3.1a — Добавить фикстуры ответов провайдера (минимальные JSON)
    [x] T PHC-11.3.2 — Unit‑тесты: NO_IMAGE ретраи и итоговый timeout
    [x] T PHC-11.3.2a — Негативный тест: отсутствует image → ретрай/timeout (по правилу Gemini)

## TODO
- [x] EP PHC-12 — V2: драйверы gemini-3-pro-image-preview и gpt-image-1.5-2025-12-16 [M]
  [x] FEAT PHC-12.0 — Контекст и спецификации [M]
    [x] T PHC-12.0.1 — Собрать/проверить документацию по base64 inline_data (input/output) для Gemini 3 Pro [L]
      [x] T PHC-12.0.1a — Выделить обязательные поля запроса (model, contents, inline_data) и ответ (parts.inline_data) [L]
      [x] T PHC-12.0.1b — Зафиксировать responseModalities и пример extract base64 [L]
    [x] T PHC-12.0.2 — Собрать/проверить документацию по base64 для GPT Image 1.5 (Image API) [L]
      [x] T PHC-12.0.2a — Зафиксировать параметры Image API (prompt, image, output_format) и ответ b64_json [L]
      [x] T PHC-12.0.2b — Ограничения на форматы/размеры изображений для edits [L]
    [x] T PHC-12.0.3 — Зафиксировать таблицу aspect_ratio/resolution для Gemini 3 Pro (imageConfig) и правила UI-маппинга [M]
      [x] T PHC-12.0.3a — Вынести значения aspect_ratio и imageSize (1K/2K/4K) [L]
      [x] T PHC-12.0.3b — Подготовить UI-маппинг: aspect_ratio+resolution -> imageConfig [M]
    [x] T PHC-12.0.4 — Зафиксировать лимиты (размеры, MIME, RPM/TPM при наличии) и auth заголовки для обоих провайдеров [M]
      [x] T PHC-12.0.4a — Gemini 3 Pro: лимиты/форматы/ключи [M]
      [x] T PHC-12.0.4b — GPT Image 1.5: лимиты/форматы/ключи [M]
    [x] T PHC-12.0.5 — Подготовить минимальные примеры: success + error response (JSON/parts) для каждого провайдера [M]
      [x] T PHC-12.0.5a — Gemini 3 Pro: success/ошибка [M]
      [x] T PHC-12.0.5b — GPT Image 1.5: success/ошибка [M]
  [x] FEAT PHC-12.1 — Схемы slot.settings [M]
    [x] T PHC-12.1.1 — Обновить/добавить JSON-схемы slot.settings под `gemini-3-pro-image-preview` [M]
      [x] T PHC-12.1.1a — Минимальные поля (model, prompt, output) [L]
      [x] T PHC-12.1.1b — Опциональные поля imageConfig (aspect_ratio, image_size) [M]
    [x] T PHC-12.1.2 — Обновить/добавить JSON-схемы slot.settings под `gpt-image-1.5-2025-12-16` [M]
      [x] T PHC-12.1.2a — Минимальные поля (model, prompt, output) [L]
      [x] T PHC-12.1.2b — Опциональные поля output_format/output_compression/size [M]
    [x] T PHC-12.1.3 — Добавить в схемы поддержку aspect_ratio/resolution (если нужна на уровне settings) [M]
      [x] T PHC-12.1.3a — Решить: хранить как UI-поля или приводить к provider-specific settings [M]
  [x] FEAT PHC-12.2 — Драйверы провайдеров [H]
    [x] T PHC-12.2.1 — Реализовать `Gemini3ProDriver` (inline_data input/output, responseModalities, imageConfig) [H]
      [x] T PHC-12.2.1a — Сборка parts (ingest → templates → prompt) [M]
      [x] T PHC-12.2.1b — Применение imageConfig (aspect_ratio/imageSize) [M]
      [x] T PHC-12.2.1c — Обработка ответа: inline_data base64 -> bytes [M]
    [x] T PHC-12.2.2 — Реализовать `GptImage15Driver` (Image API, base64 output) [H]
      [x] T PHC-12.2.2a — Формирование запроса (model, prompt, image[], output_format) [M]
      [x] T PHC-12.2.2b — Обработка ответа: data[0].b64_json -> bytes [M]
    [x] T PHC-12.2.3 — Пробросить error context (provider/model/http_status/provider_error_message) в логи драйверов [M]
      [x] T PHC-12.2.3a — Унифицировать mapping ошибок в ProviderResult/исключения [M]
    [x] T PHC-12.2.4 — Встроить ретраи по правилам GeminiDriver (retry_policy + NO_IMAGE), если применимо [M]
      [x] T PHC-12.2.4a — Проверить NO_IMAGE аналог у Gemini 3 Pro (если есть) [M]
  [x] FEAT PHC-12.3 — Документация и тесты [M]
    [x] T PHC-12.3.1 — Обновить provider docs (параметры, лимиты, ретраи, логирование) [M]
      [x] T PHC-12.3.1a — Gemini 3 Pro doc [M]
      [x] T PHC-12.3.1b — GPT Image 1.5 doc [M]
    [x] T PHC-12.3.2 — Добавить unit‑тесты драйверов (success/timeout/error/invalid_response) [H]
      [x] T PHC-12.3.2a — Gemini 3 Pro unit tests [H]
      [x] T PHC-12.3.2b — GPT Image 1.5 unit tests [H]
    [x] T PHC-12.3.3 — Обновить контрактные примеры/доки (при необходимости SemVer bump) [M]
      [x] T PHC-12.3.3a — VERSION.json + INDEX.yaml синхронизация [L]
  [x] FEAT PHC-12.4 — UI поддержка размера [M]
    [x] T PHC-12.4.1 — Добавить в UI поля aspect_ratio/resolution (если провайдер поддерживает) [M]
      [x] T PHC-12.4.1a — UI элементы (selects) и сохранение в slot settings [M]
    [x] T PHC-12.4.2 — Маппинг UI → provider settings и валидация на клиенте [M]
      [x] T PHC-12.4.2a — Gemini 3 Pro: aspect_ratio + imageSize [M]
      [x] T PHC-12.4.2b — GPT Image 1.5: size (если используем) [M]

## TODO
- [~] EP PHC-13 — Gemini 2.5: поддержка aspect_ratio/resolution [M]
  [~] FEAT PHC-13.0 — Контекст и спеки [M]
    [x] T PHC-13.0.1 — CONSULT — подтвердить точный model_id Gemini 2.5 и поддержку aspect_ratio/resolution в API [M]
    [x] T PHC-13.0.2 — Зафиксировать официальные лимиты и список допустимых aspect_ratio/resolution [M]
    [ ] T PHC-13.0.3 — Подготовить минимальные примеры success/error для Gemini 2.5 (base64 inline_data) [M]
  [x] FEAT PHC-13.1 — Настройки и драйвер [H]
    [x] T PHC-13.1.1 — Обновить/добавить schema slot.settings для Gemini 2.5 (image_config) [M]
    [x] T PHC-13.1.2 — Встроить поддержку imageConfig в драйвер Gemini 2.5 (aspect_ratio/imageSize) [H]
    [x] T PHC-13.1.3 — Обновить логи драйвера (provider/model/http_status/provider_error_message) [M]
  [x] FEAT PHC-13.2 — UI и тесты [M]
    [x] T PHC-13.2.1 — UI: поддержать aspect_ratio/resolution для Gemini 2.5 (маппинг в settings) [M]
    [x] T PHC-13.2.2 — Unit‑тесты Gemini 2.5 (aspect_ratio/resolution + base64) [H]
    [x] T PHC-13.2.3 — Обновить provider docs и VERSION/INDEX при необходимости [M]



## TODO
- [x] EP PHC-14 — Рефакторинг UI слотов
  [x] US PHC-14.GOV — Governance & Discovery
    [x] T PHC-14.GOV.1 — CONSULT — подтвердить разбиение UI модулей (slot-state/slot-ui/slot-mapping/slot-events/slot-index)
    [x] T PHC-14.GOV.2 — REFLECT — проверить риски регрессий UI (Gemini/Turbotext, image_config, операции)
  [x] FEAT PHC-14.1 — Модульная нарезка slot UI
    [x] T PHC-14.1.1 — Разнести код по файлам и обновить HTML подключения
    [x] T PHC-14.1.2 — Обновить spec/docs ui пример

## GOV Template (reference)
- [ ] EP XXX — Название эпика  
  [ ] US XXX.GOV — Governance & Discovery  
    [ ] T XXX.GOV.1 — CONSULT — ключевой вопрос к тимлиду  
    [ ] T XXX.GOV.2 — REFLECT — анализ рисков/альтернатив  
  [ ] FEAT XXX.Y — Функциональный блок (открывать после закрытия GOV)

