---
id: provider_driver_checklist
updated: 2026-01-09
---

# Driver checklist (KISS)

Документ задаёт минимальные правила для новых драйверов провайдеров.

## Входы
- ingest‑изображение (inline‑image)
- prompt (обязателен)
- template_media (опционально)

## Порядок частей
1. ingest‑image
2. template_media (если есть)
3. prompt

## Выход
- вернуть `ProviderResult(payload, content_type)`
- `output.mime_type` строго соблюдается; если провайдер не поддерживает — `provider_error`

## Ошибки
- только `ProviderTimeoutError` или `ProviderExecutionError`

## Ретраи (как в GeminiDriver)
- `retry_policy.max_attempts` (≤ 3), `backoff_seconds` (default 2s) для transient ошибок
- `NO_IMAGE`: до 5 попыток с паузой 3s, только если остаётся время до дедлайна

## Логирование
- драйвер пишет подробные логи провайдера
- ingest пишет итоговый статус (success/timeout/provider_error)
- не логировать payload/большие response body

## Псевдокод сборки частей
```python
parts = [inline_image(ingest_image)]
for item in template_media:
    parts.append(inline_image(item))
parts.append(text(prompt))

response = provider_call(parts, output_mime=output.mime_type)
return ProviderResult(payload=response.bytes, content_type=response.mime_type)
```
