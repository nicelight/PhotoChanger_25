---
id: usecases
updated: 2025-01-14
---

# Ключевые сценарии

## UC0. Вход администратора и ротация ingest-пароля
- **Акторы:** Администратор (serg/igor), Auth API, Settings API.
- **Предусловия:** Статические аккаунты развёрнуты, токены провайдеров и ingest-пароль заданы; админ знает текущий пароль.【F:spec/docs/blueprints/use-cases.md】
- **Основной поток:** логин через `POST /api/login` → получение JWT с `permissions` → `PUT /api/settings` с новым ingest-паролем и (при необходимости) обновлением `ingest.sync_response_timeout_sec` в диапазоне 45–60 с → `GET /api/settings` показывает метаданные (без секрета).【F:spec/docs/blueprints/use-cases.md】【F:spec/docs/blueprints/acceptance-criteria.md】
- **Acceptance:** 401/429 при неверных данных; ротация фиксируется в журнале; ingest сразу принимает только новый пароль; TTL пересчитаны в ответе settings.【F:spec/docs/blueprints/acceptance-criteria.md】【F:spec/docs/blueprints/test-plan.md】

## UC1. Настройка слота администраторами
- **Акторы:** Администратор, Slot Management UI, Admin API.
- **Предусловия:** JWT с правом `slots:write`; один из 15 статических `slot-00x` выбран для редактирования.【F:spec/docs/blueprints/use-cases.md】
- **Основной поток:** UI загружает список провайдеров/операций → администратор задаёт провайдера (Gemini/Turbotext), параметры (промпты, `template_media`, ретраи) → `PUT /api/slots/{slot_id}` валидирует и сохраняет конфигурацию → UI обновляет ingest-URL `<BASE_URL>/ingest/{slot_id}` и галерею `recent_results`.【F:spec/docs/blueprints/use-cases.md】【F:/brief.md】
- **Acceptance:** 422 при неверных полях, 404 для неизвестного слота, существующие Job продолжают работать со старыми настройками.【F:spec/docs/blueprints/acceptance-criteria.md】

## UC2. Ingest с успешной обработкой
- **Акторы:** DSLR Remote Pro, Ingest API, PostgreSQL очередь, Worker, AI-провайдер (Gemini/Turbotext), Media Storage.【F:spec/docs/blueprints/use-cases.md】
- **Предусловия:** Slot активен, ingest-пароль валидный, временные лимиты `T_sync_response`, `T_ingest_ttl` рассчитаны; воркеры доступны.【F:/brief.md】【F:spec/docs/blueprints/domain-model.md】
- **Основной поток:** `POST /ingest/{slotId}` сохраняет Job со статусом `pending` → воркер берёт задачу (`processing`), вызывает провайдера → результат приходит до дедлайна → воркер сохраняет файл в `MEDIA_ROOT/results`, обновляет `Job.result_*`, очищает исходный payload → Ingest API, выполняя polling раз в ~1 с, обнаруживает `is_finalized = true` и отдаёт 200 с `result_inline_base64`; затем base64 обнуляется, файл доступен 72 ч по `GET /public/results/{job_id}`.【F:spec/docs/blueprints/use-cases.md】【F:spec/docs/blueprints/domain-model.md】
- **Acceptance:** Ответ ≤ актуального `T_sync_response`; исходные файлы очищены; `result_expires_at = finalized_at + 72h`; публичная ссылка возвращает 200 до истечения TTL и 410 после.【F:spec/docs/blueprints/acceptance-criteria.md】【F:spec/docs/blueprints/nfr.md】

## UC3. Ingest с таймаутом 504
- **Акторы:** Те же, что в UC2, плюс мониторинг (фиксирует 504).【F:spec/docs/blueprints/use-cases.md】
- **Предусловия:** Провайдер не успевает вернуть результат до `T_sync_response`; воркер всё ещё обрабатывает задачу.【F:spec/docs/blueprints/constraints-risks.md】
- **Основной поток:** Ingest API polling достигает дедлайна → ответ 504 и запись `failure_reason = 'timeout'`, `is_finalized = true` → воркер видит финализацию, останавливает вызов провайдера, очищает временные файлы и `result_inline_base64` → мониторинг фиксирует событие; повторный запуск возможен только новым ingest-запросом.【F:spec/docs/blueprints/use-cases.md】
- **Acceptance:** 504 строго в момент истечения `T_sync_response`; поздние ответы провайдера игнорируются; `Job` не перезаписывает `result_*`; алерты активируются при доле таймаутов > 5 %.【F:spec/docs/blueprints/acceptance-criteria.md】【F:spec/docs/blueprints/nfr.md】

## UC4. Истечение временной ссылки `media_object`
- **Акторы:** Администратор/UI, Media API, Worker/очиститель, внешние провайдеры (скачивают файл).【F:spec/docs/blueprints/use-cases.md】
- **Предусловия:** `media_object` зарегистрирован с TTL = `T_public_link_ttl = T_sync_response`; провайдер не скачал файл вовремя.【F:spec/docs/blueprints/domain-model.md】
- **Основной поток:** `POST /api/media/register` выдаёт публичный URL → провайдер не обращается к ссылке → по истечении TTL очиститель удаляет файл, Job получает `failure_reason = 'timeout'`, публичный endpoint возвращает 410 на повторные запросы.【F:spec/docs/blueprints/use-cases.md】
- **Acceptance:** Нет механизма продления; попытка продлить → 404/405; очистка происходит ≤ 1 мин после TTL; событие логируется.【F:spec/docs/blueprints/acceptance-criteria.md】【F:spec/docs/blueprints/nfr.md】

## UC5. Управление шаблонными медиа и галереей результатов
- **Акторы:** Администратор/UI, Admin API, Media Storage, Public API.【F:spec/docs/blueprints/use-cases.md】
- **Предусловия:** Слот сконфигурирован и имеет завершённые Job; шаблонные медиа доступны через `template_media` без публичных ссылок.【F:/brief.md】【F:spec/docs/blueprints/domain-model.md】
- **Основной поток:** Администратор загружает шаблон через `POST /api/template-media/register` → привязывает к слоту → UI отображает галерею `recent_results` (превью + `download_url` = `GET /public/results/{job_id}`) → при истечении `result_expires_at` UI обновляет карточку как недоступную (410). Удаление шаблонов требует подтверждения, если слот их использует.【F:spec/docs/blueprints/use-cases.md】【F:spec/docs/blueprints/acceptance-criteria.md】
- **Acceptance:** Проверка MIME/размера шаблонов (415/413 при нарушении); `recent_results` всегда ограничен свежими Job; скачивание результатов доступно 72 ч; после удаления шаблона слоты получают обновление и логируется операция.【F:spec/docs/blueprints/acceptance-criteria.md】【F:spec/docs/blueprints/nfr.md】
