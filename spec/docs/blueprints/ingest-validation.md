# Blueprint — Ingest Payload Validation

## Цели
- Гарантировать, что входящие multipart-запросы соответствуют лимитам размера и типу (`image/jpeg|png|webp`) до запуска провайдера.
- Минимизировать использование памяти: чтение файла потоками, остановка при превышении лимита.
- Записать метаданные (`content_length`, `content_type`, `sha256`) в `JobContext`.
- Убедиться, что ошибки маппятся на контрактные коды `413 payload_too_large`, `415 unsupported_media_type` и `400 invalid_request` (включая проверку checksum).

## Основные сущности
- `SlotConfig`: включает `size_limit_mb` (пер-слот), `provider`, прочие настройки.
- `IngestLimits`: глобальные константы — `default_slot_limit_mb` (15), `absolute_cap_bytes` (50 * MiB), допустимые MIME.
- `UploadValidationResult`: DTO с полями `content_type`, `size_bytes`, `sha256`, `filename`.

## Поток
1. FastAPI контроллер получает `UploadFile` от `multipart/form-data`.
2. `validate_upload(upload, slot_config, limits)` выполняет:
   - Берёт `content_type = upload.content_type`.
   - Проверяет, что `content_type` входит в `ALLOWED_CONTENT_TYPES`.
     - При нарушении → `UnsupportedMediaError`.
   - Считает `bytes_limit = min(slot_limit_bytes, absolute_cap_bytes)`.
   - Читает файл чанками (`CHUNK_SIZE = 1_048_576`):
     - `total += len(chunk)`; если `total > bytes_limit` → `PayloadTooLargeError`.
     - Обновляет `sha256`.
     - Временно сохраняет в `SpooledTemporaryFile` (настройка FastAPI по умолчанию).
   - По окончании — возвращает `UploadValidationResult`, где `stored_path` = путь во временной директории FastAPI.
3. `JobContext` дополняется полями:
   - `content_type`, `content_length`, `payload_hash`, `temp_payload_path`.
   - `sync_deadline = now + T_sync_response` (уже зафиксировано в документации).
4. При успешной обработке результат переносится в `media/results/{slot_id}/{job_id}/payload.<ext>`; temp-файл удаляется вручную (иначе останется в `/tmp`).
5. При ошибке валидации:
   - Генерируется доменное исключение (`UnsupportedMediaError`/`PayloadTooLargeError`) или `ChecksumMismatchError`.
   - Контроллер фиксирует `job_history.status='failed'`, очищает temp/result каталоги и возвращает JSON-ошибку с кодом 413/415/400 и `failure_reason` из контракта.

## Исключения и маппинг
| Исключение | HTTP статус | `failure_reason` | Детали |
|------------|-------------|------------------|--------|
| `UnsupportedMediaError` | 415 | `unsupported_media_type` | `details = f"Allowed: {', '.join(ALLOWED)}"` |
| `PayloadTooLargeError` | 413 | `payload_too_large` | `details = f"Limit={bytes_limit} bytes"` |

## Псевдокод
```python
async def validate_upload(upload: UploadFile, slot: SlotConfig, limits: IngestLimits) -> UploadValidationResult:
    if upload.content_type not in limits.allowed_content_types:
        raise UnsupportedMediaError(upload.content_type)

    cap = min(slot.size_limit_mb * MB, limits.absolute_cap_bytes)

    hasher = hashlib.sha256()
    total = 0
    async for chunk in iter_upload_chunks(upload, limits.chunk_size):
        total += len(chunk)
        if total > cap:
            raise PayloadTooLargeError(total, cap)
        hasher.update(chunk)

    await upload.seek(0)

    return UploadValidationResult(
        content_type=upload.content_type,
        size_bytes=total,
        sha256=hasher.hexdigest(),
        filename=upload.filename or derive_filename(upload.content_type),
    )
```

## Интеграция в FastAPI
```python
@router.post("/api/ingest/{slot_id}")
async def ingest(slot_id: str,
                 password: str = Form(...),
                 hash_hex: str = Form(...),
                 file: UploadFile = File(...),
                 svc: IngestService = Depends(get_ingest_service)):
    job_ctx = svc.prepare_job(slot_id)
    job_ctx.metadata["ingest_password"] = password  # проверка пароля — отдельная задача
    try:
        await svc.validate_upload(job_ctx, file, hash_hex)
    except UnsupportedMediaError:
        svc.record_failure(job_ctx, FailureReason.UNSUPPORTED_MEDIA_TYPE)
        raise HTTPException(status_code=415, detail=build_error("unsupported_media_type"))
    except PayloadTooLargeError:
        svc.record_failure(job_ctx, FailureReason.PAYLOAD_TOO_LARGE)
        raise HTTPException(status_code=413, detail=build_error("payload_too_large"))
    except ChecksumMismatchError:
        svc.record_failure(job_ctx, FailureReason.INVALID_REQUEST)
        raise HTTPException(status_code=400, detail=build_error("invalid_request"))
    return await svc.process(job_ctx)
```

## Тестовый набор
- **Позитивные**:
  - JPEG < slot_limit, Content-Type `image/jpeg`.
  - PNG с точным размером = slot_limit.
- **Негативные**:
  - GIF → 415.
  - JPEG > slot_limit → 413.
  - JPEG > absolute cap (например 60 МБ) при большом `size_limit_mb` → 413.
  - Ошибка контроллера: `hash` из формы ≠ рассчитанному → 400 `invalid_request` (обрабатывается отдельно).
- **Интеграционные**:
  - Slot limit 12 МБ, глобальный cap 50 МБ; загружаем 20 МБ PNG → 413.
  - Два параллельных запроса: оба валидные, проверка семафора (отдельная задача).

## Операционные аспекты
- Поддержка прогресса в логах: `log.info("ingest.upload.validated", job_id=..., size=..., mime=...)`.
- При ошибке 413/415 логируем уровень `warning`.
- Размер chunk настраивается через конфиг (`UPLOAD_CHUNK_BYTES`).
- По завершении `IngestService` должен удалить временный файл: `await file.close()` + unlink temp path, чтобы не копить мусор в `/tmp`.
