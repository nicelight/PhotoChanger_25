# System Context — PhotoChanger

## 1. Границы системы
- **Внутри**: FastAPI-приложение (ingest, media, slots, settings, stats), внутрипроцессный Auth API `/api/login`, PostgreSQL 15, файловое хранилище `media/temp` и `media/results`, cron `scripts/cleanup_media.py`, Admin UI/REST, публичные ссылки `/public/results/{job_id}`.
- **Снаружи**: DSLR Remote Pro, AI-провайдеры Gemini/Turbotext, пользователи публичных ссылок, мониторинг/логирование, TLS-инфраструктура, секрет-хранилище.
- Архитектурные решения фиксированы ADR-0001: монолит без очередей, горизонтального масштабирования и внешнего rate limiting.

## 2. Внешние акторы и их взаимодействие
| Актор | Запросы к PhotoChanger | Ответы/зависимость |
|-------|-----------------------|--------------------|
| DSLR Remote Pro | `POST /api/ingest/{slot_id}` (multipart) | HTTP 200 + ссылка на результат или 504/ошибка |
| Администратор | `/api/login`, `/api/slots`, `/api/settings`, `/api/stats`, Admin UI | JWT, конфигурации слотов, статистика, отчёты |
| Провайдер AI | `GET` временных ссылок (`media_object`), обработка через драйверы | Путь к исходным медиа, доставка результата в пределах `T_sync_response` |
| Пользователь публичной ссылки | `GET /public/results/{job_id}` | Итоговый файл 72 ч, `410 Gone` после истечения TTL |
| Ops/Мониторинг | `/metrics`, `/healthz`, cron `cleanup_media.py`, системные логи | Метрики SLA, статусы компонент, отчёты об очистке |

## 3. Основные интерфейсы
- **Ingest API**: Multipart POST с полями `password`, `file`, optional metadata; проверяет ingest-пароль и слоты, создаёт `JobContext`.
- **Provider Drivers**: реализация интерфейса `ProviderDriver.process(job_ctx)` для Gemini/Turbotext; управляют сетевыми вызовами и форматами.
- **Admin API/UI**: JWT-аутентификация, CRUD слотов (15 штук), глобальные настройки, шаблонные медиа, статистика SLA.
- **Public API**: доступ к результатам (`GET /public/results/{job_id}`), галерея последних 10 результатов по слоту.
- **Observability**: `structlog`, Prometheus `/metrics`, health-check `/healthz`, cron-скрипт очистки.

## 4. Инфраструктурные зависимости
- Переменные окружения: `DATABASE_URL`, `MEDIA_ROOT`, `RESULT_TTL_HOURS`, `TEMP_TTL_SECONDS`, `JWT_SIGNING_KEY`, `GEMINI_API_KEY`, `TURBOTEXT_API_KEY`.
- Доступ к интернету для провайдеров, наличие TLS-сертификатов, дисковая квота для `media/`.
- Cron-планировщик (15 минут) и системный журнал для отчётов `cleanup_media.py`.
- CI/CD пайплайн, выполняющий `ruff`, `black`, `mypy`, pytest-наборы и smoke UI (см. `docs/PRD.md` §11).

## 5. Диаграммы
- C4 диаграммы контекста и контейнеров будут расположены в `spec/diagrams/c4-context.mmd` и `spec/diagrams/c4-container.mmd` (создание — US PHC-1.0.3).
- Последовательность ingest-флоу и жизненный цикл медиа будут представлены диаграммами последовательности/состояний в `spec/diagrams/` (см. `spec/docs/use-cases.md`).
