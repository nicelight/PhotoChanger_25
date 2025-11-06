---
title: Cron Runbook — cleanup_media.py
updated: 2025-11-06
owner: ops
---

# Назначение
`scripts/cleanup_media.py` удаляет просроченные результаты (`media/results`) и временные файлы провайдеров (`media/temp`). Скрипт должен запускаться каждые 15 минут (см. PRD §10) и гарантировать, что публичные ссылки `/public/results/{job_id}` перестают работать через 72 ч.

# Предусловия
- Доступ к окружению (local/staging/prod) с настроенными переменными `MEDIA_ROOT`, `DATABASE_URL`, `RESULT_TTL_HOURS`, `TEMP_TTL_SECONDS`.
- Убедитесь, что cron/systemd запускает Python ≥ 3.11 из виртуального окружения проекта.
- Логи stdout перенаправлены в системный журнал (например, `>> /var/log/cron.log`).

# Повседневный запуск
```bash
python scripts/cleanup_media.py
```
Вывод:
```
cleanup done, results_removed=3, temp_removed=1
```
- `results_removed` — сколько каталогов `media/results/<slot>/<job>` удалено.
- `temp_removed` — сколько временных объектов провайдеров очищено.
- Код возврата `0` означает успех. Любой `>0` сигнализирует об ошибке (см. ниже).

# Dry-run
Используйте перед релизами или при расследовании:
```bash
python scripts/cleanup_media.py --dry-run
```
Вывод:
```
cleanup dry-run, results_expired=5, temp_expired=2
```
Файлы не удаляются, но отображается количество кандидатов. Код возврата всегда `0`.

# Триггеры ручного запуска
- Рост числа 410/`result_expired` в `/public/results`.
- Заполнение диска `MEDIA_ROOT`.
- Тестирование после изменения TTL (`RESULT_TTL_HOURS`, `TEMP_TTL_SECONDS`).

# Диагностика и восстановление
| Симптом | Возможная причина | Действия |
| ------- | ----------------- | -------- |
| `cleanup failed: (OperationalError ...)` | База данных недоступна | Проверить PostgreSQL, повторить запуск после восстановления. |
| `results_removed=0`, но диска мало | TTL ещё не истёк, либо `RESULT_TTL_HOURS` ошибочно увеличен | Проверить конфиги, выполнить `--dry-run`, при необходимости уменьшить TTL. |
| `temp_removed` всегда 0 | Провайдеры не используют временные ссылки или `TEMP_TTL_SECONDS` слишком мал | Уточнить настройки, проверить `media/temp`. |
| Cron не пишет в лог | Неверный путь Python/проекта | Проверить cron entry `*/15 * * * * cd /opt/photochanger && .venv/Scripts/python scripts/cleanup_media.py`. |

# Мониторинг
- События `media.cleanup.removed` пишутся через `structlog` (результаты) и stdout cron.
- Метрики: используйте существующий мониторинг объёма `media/` (см. PRD §10 и UC6).
- Добавьте оповещение при отсутствии лога cron >30 мин или при повторяющихся кодах возврата `2`.

# Контрольный список после изменения скрипта
1. Запустить `py -m pytest tests/unit/scripts/test_cleanup_media.py`.
2. Выполнить `python scripts/cleanup_media.py --dry-run` на staging.
3. Проверить, что cron запись обновлена (если путь/опции изменились).
4. Обновить этот runbook и `scripts/README.md` при изменении флагов или поведения.
