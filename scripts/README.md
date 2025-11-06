# Scripts

## `cleanup_media.py`

Удаляет просроченные медиа (итоговые результаты и временные файлы провайдеров).

### Использование

```bash
python scripts/cleanup_media.py
```

- Печатает `cleanup done, results_removed=X, temp_removed=Y`.
- Возвращает `0` при успехе, `2` при ошибке окружения (БД, файловая система).

### Dry-run

```bash
python scripts/cleanup_media.py --dry-run
```

- Ничего не удаляет, выводит только количество кандидатов.

### Среда

- Требуются переменные `MEDIA_ROOT`, `DATABASE_URL`, `RESULT_TTL_HOURS`, `TEMP_TTL_SECONDS`.
- Скрипт использует ту же конфигурацию, что и основное FastAPI-приложение.

### Подробнее

Runbook с операционными инструкциями: `docs/runbooks/cron_cleanup.md`.
