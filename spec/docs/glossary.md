# Глоссарий PhotoChanger (SDD)

| Термин | Определение | Ссылки |
|--------|-------------|--------|
| Slot | Статическая конфигурация обработки (`slot-001`…`slot-015`), содержит выбранного провайдера, операцию, параметры, шаблонные медиа, признак активности. Используется для построения URL ingest. | `docs/PRD.md` §2, §4 |
| Ingest API | Публичный HTTP-эндпоинт `POST /api/ingest/{slot_id}` для приёма multipart-запросов от DSLR Remote Pro, проверки пароля и запуска обработки. SLA ограничен `T_sync_response`. | `docs/ARCHITECTURE.md` §3, `.memory/USECASES.md` UC2 |
| T_sync_response | Конфигурируемое окно синхронного ответа ingest (10–60 с, по умолчанию 48 с). По превышению возвращается 504 и статус `timeout`. | `.memory/MISSION.md`, `docs/PRD.md` §1 |
| MediaObject | Внутренний объект, представляющий временную ссылку (`media/temp`) с TTL = `T_sync_response`, используемую провайдерами для скачивания исходных файлов. | `spec/docs/providers/turbotext.md` |
| ResultStore | Подсистема хранения итоговых файлов (`media/results/{job_id}.{ext}`) с TTL 72 ч (`T_result_retention`). Публикует `GET /public/results/{job_id}`. | `docs/ARCHITECTURE.md` §4 |
| TempMediaStore | Подсистема хранения временных файлов (`media/temp/{slot_id}/{job_id}`) и `MediaObject` с TTL = `T_sync_response`; используется драйверами провайдеров для скачивания исходников. | `docs/ARCHITECTURE.md` §4 |
| ProviderDriver | Абстракция драйвера AI-провайдера с методом `process(job_ctx) -> ProviderResult`. Реализации: `GeminiDriver`, `TurbotextDriver`. | `docs/ARCHITECTURE.md` §5 |
| JobContext | Структура, собираемая `IngestService`: содержит `job_id`, сведения о слоте, пути к временным файлам, дедлайны и параметры провайдера. | `docs/ARCHITECTURE.md` §3 |
| ProviderResult | Унифицированный ответ драйвера (путь к файлу или байты), на основании которого Ingest формирует итоговый результат. | `docs/ARCHITECTURE.md` §5 |
| TemplateMedia | Статические шаблонные изображения, привязанные к слотам; хранятся долго, проходят валидацию MIME/размера при загрузке. | `docs/PRD.md` §5 |
| Ingest password | Глобальный секрет, проверяемый при каждом `POST /api/ingest/{slot_id}`; хранится в `app_settings` (`ingest.dslr_password`) в виде хэша и обновляется через `/api/settings`. | `docs/PRD.md` §4 |
| AppConfig | Центральная функция сборки FastAPI-приложения: подключает БД, подготавливает драйверы провайдеров, загружает настройки окружения, используется также в тестах. | `docs/ARCHITECTURE.md` §2 |
| Admin JWT | Статический JWT для администраторов (`serg`, `igor`), выдаётся `/api/login`, используется в Admin UI/API. | `docs/PRD.md` §3 |
| StatsService | Модуль статистики SLA; агрегирует p95 времени обработки, долю 504, загрузку диска, публикует `/api/stats`. | `docs/ARCHITECTURE.md` §6 |
| Cleanup cron | Сценарий `scripts/cleanup_media.py`, запускаемый каждые 15 мин для удаления просроченных медиа и обновления `media_object.cleaned_at`. | `docs/PRD.md` §10 |
| Public Result Link | Временный URL `/public/results/{job_id}` с TTL 72 ч; после истечения возвращает `410 Gone`. | `.memory/USECASES.md` UC4 |
