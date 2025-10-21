# Ingest Runbook

## Purpose
Эта инструкция описывает запуск и эксплуатацию синхронного ingest-потока DSLR Remote Pro.
Маршрут `POST /ingest/{slotId}` принимает multipart запросы, ставит задачи в очередь,
ожидает финализации пула из четырёх асинхронных воркеров (фоновые задачи FastAPI) в пределах `T_sync_response` и возвращает либо инлайн-результат,
либо канонические ошибки (401/404/413/415/429/503/504).

## Environment
Перед запуском убедитесь, что заданы переменные окружения:

| Variable | Description |
| --- | --- |
| `PHOTOCHANGER_MEDIA_ROOT` | Каталог для временных payload и результатов. Должен быть доступен для API и воркеров. |
| `PHOTOCHANGER_DATABASE_URL` | DSN PostgreSQL-очереди. В локальном режиме можно использовать `postgresql://localhost:5432/photochanger`. |
| `PHOTOCHANGER_QUEUE_STATEMENT_TIMEOUT_MS` | Таймаут SQL-запросов очереди в миллисекундах (по умолчанию 5000). Должен быть меньше `T_sync_response`. |
| `PHOTOCHANGER_QUEUE_MAX_IN_FLIGHT_JOBS` | Верхняя граница активных задач очереди. По умолчанию 12, после превышения ingest возвращает 429 (`queue_busy`). |
| `PHOTOCHANGER_T_SYNC_RESPONSE_SECONDS` | Значение `T_sync_response` (45–60 секунд). Используется для расчёта дедлайна job, TTL inline-результатов и лимита хранения payload. |
| `PHOTOCHANGER_JWT_SECRET` | Секрет для административных JWT (используется для остальных API). |

Инициализация требует заранее записанного хэша ingest-пароля (см. `SettingsDslrPasswordStatus`). В
локальных сборках хэш создаётся через `bootstrap_settings`, но в staging/prod пароль должен быть
передан через Admin API (`/api/settings`).

## Startup Steps
1. Поднимите PostgreSQL (минимум 14+) и создайте базу очереди.
2. Создайте структуру `MEDIA_ROOT` (по умолчанию `./var/media`) и подпапки `payloads/` и `results/`.
3. Экспортируйте переменные окружения выше или создайте `.env` для `pydantic-settings`.
4. Запустите API: `uvicorn src.app.main:app --reload`.
5. Убедитесь по логам, что после старта FastAPI созданы четыре фоновые задачи воркера: они делят тот же event loop, поэтому отдельный процесс запускать не нужно. Если воркеры не поднялись, проверьте конфигурацию DI (`QUEUE_MAX_IN_FLIGHT_JOBS`, подключения к БД) и перезапустите сервис.

## Curl Example
```
curl -i -X POST "http://localhost:8000/ingest/slot-001" \
  -F "password=<dslr-password>" \
  -F "fileToUpload=@sample.jpg;type=image/jpeg"
```
Успешный ответ содержит бинарный поток (`Content-Type` совпадает с результатом провайдера) и
заголовки:

```
HTTP/1.1 200 OK
Cache-Control: no-store
Content-Type: image/jpeg
X-Job-Id: <uuid>
Content-Length: <bytes>
```

При таймауте клиент получит JSON-ошибку со статусом 504 и полями `error.details.job_id` и
`error.details.expires_at`, которые позволяют сопоставить запрос с записью очереди и понять,
когда истечёт TTL задачи:

```
HTTP/1.1 504 Gateway Timeout
Cache-Control: no-store
Content-Type: application/json

{
  "error": {
    "code": "sync_timeout",
    "message": "Ingest processing exceeded the synchronous response window",
    "details": {
      "job_id": "...",
      "expires_at": "2025-10-27T12:00:00Z"
    }
  }
}
```

## TTL & Cleanup
- Payload сохраняются в `MEDIA_ROOT/payloads/{job_id}` и регистрируются через `MediaService` с TTL
  `min(job.expires_at, now + T_sync_response)` (при этом имя файла очищается от небезопасных символов
  и приводится к безопасному виду). После завершения ответа API вызывает
  `MediaService.revoke_media`, чтобы удалить файлы и запись `MediaObject`.
- Inline-результаты хранятся в поле `Job.result_inline_base64` и очищаются сразу после отдачи
  ответа (`JobService.clear_inline_preview`).
- При истечении `T_sync_response` API помечает задачу как `failure_reason = timeout`, воркеры больше
  не будут опрашивать провайдера, а клиент получает 504; при рестарте приложения фоновые задачи не возобновляют работу над такой Job.
- Все синхронные ответы (успех/ошибка) выставляют `Cache-Control: no-store`, чтобы предотвратить
  кеширование временных артефактов промежуточными прокси и клиентами.
- Итоговые файлы с retention 72 часа сохраняются согласно финальным решениям **Issue 2–4**: воркер записывает артефакт в `MEDIA_ROOT/results/<job_id>.<ext>` (расширение выводится из MIME), вычисляет контрольную сумму и `result_expires_at = finalized_at + 72h`. Фоновая задача `photochanger-media-cleanup` запускается каждые 15 минут, вызывает `MediaService.purge_expired_media` и `JobService.purge_expired_results`, удаляет просроченные файлы и обнуляет публичные ссылки, чтобы `GET /public/results/{job_id}` возвращал `410 Gone` после истечения TTL.

## Back-pressure & Errors
- Если очередь не принимает задачи, API возвращает 429 (`queue_busy`). Мониторинг должен
  отслеживать долю 429 и при необходимости менять конфигурацию (`QUEUE_MAX_IN_FLIGHT_JOBS`) либо готовить масштабирование базы; пул из четырёх воркеров увеличивать не следует без пересмотра требований.
  очищаются сразу после ответа.
- При недоступности базы очереди возвращается 503 (`queue_unavailable`). Проверьте состояние
  PostgreSQL и сетевые соединения.
- Неверный пароль → 401; неизвестный слот → 404; неподдерживаемый MIME → 415;
  превышение лимита (2 ГБ) → 413.
- Любые неожиданные ошибки логируются с `correlation_id` и возвращают 500 (`internal_error`).

## Operational Notes
- Для детерминированных тестов `PHOTOCHANGER_T_SYNC_RESPONSE_SECONDS` можно временно снизить,
  но в продуктивных средах используйте значения из SDD (45–60 секунд).
- Следите за заполнением `MEDIA_ROOT`. Очистка payload выполняется синхронно, но результаты и
  публичные ссылки требуют фоновой очистки (см. фазу 4.4 и ADR-0002).
- При увеличении числа таймаутов проверяйте провайдеров (Gemini/Turbotext) и network latency;
  ingest не выполняет повторных запросов после истечения окна.
