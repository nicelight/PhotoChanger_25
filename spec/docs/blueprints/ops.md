# Ops и наблюдаемость (PHC-4)

## Секреты и окружения
- Prod/Staging: хранить переменные в `.env` или Docker secrets на хосте (вне git). Права: только сервисный пользователь приложения (600/400). Бэкап — за пределами репозитория, с шифрованием. Ротация: при смене ключей формируем новый `.env`, проверяем хэши/TTL, перезапускаем сервис.
- Локально: `.env.local` из репозитория примеров; реальные ключи не коммитим.
- Контроль: перед деплоем проверять отсутствие `.env*` в git (`git status`, `.gitignore`), сверять перечень переменных с `.env.example`.

## `/metrics` и мониторинг
- Экспонируем Prometheus endpoint `/metrics` (формат text/plain 0.0.4, scrape 15s).
- Список метрик и SLA — `spec/contracts/schemas/metrics.yaml`. Ключевые KPI: timeout_rate ≤5% за 5m, p95 ingest ≤ `T_sync_response`, использование диска media ≤80%.
- Health-check `/healthz` остаётся индикатором готовности (БД, FS, быстрый ping провайдеров).

## Алерты (минимальный набор)
- HighTimeoutRate: доля таймаутов >5% за 10м → пейдж on-call, проверка провайдера/нагрузки.
- SlowP95: p95 длительности > `T_sync_response` 10м → тикет, анализ провайдеров/ресурсов.
- MediaDiskHigh: использование тома media >80% 5м → тикет, запуск cleanup/расширение диска/снижение TTL.
- `/metrics` недоступен или пуст >5м → тикет, проверить приложение/сетевой доступ Prometheus.

## Мини-плейбук реакции
- Таймауты/медленные запросы: сверить нагрузку, логи драйверов, лимиты провайдеров; временно снизить параллелизм ingest или повысить `T_sync_response` (если SLA допускает), уведомить заказчика о деградации.
- Рост 5xx провайдера: перевести слот в maintenance (отключить), сообщить операторам, включить после стабилизации.
- Заполнение диска media: вручную запустить `python scripts/cleanup_media.py --dry-run`, затем без `--dry-run`; при нехватке — увеличить том или уменьшить `RESULT_TTL_HOURS`.

## Релиз и handoff checklist (контракты/ops)
- Перед релизом: обновить `spec/contracts/VERSION.json` (SemVer, дата, summary), убедиться в актуальности `spec/contracts/schemas/metrics.yaml` и `spec/docs/blueprints/ops.md`.
- Синхронизировать `.memory/INDEX.yaml` (version, updated) и `.memory/PROGRESS.md`.
- Проверить `.gitignore` на `.env*`, что в git нет секретов; удостовериться, что `.env`/Docker secrets на сервере созданы и права выставлены.
- Smoke: `/healthz`, `/metrics` (наличие ключевых метрик), `scripts/cleanup_media.py --dry-run`, быстрый ingest через тестовый слот.
