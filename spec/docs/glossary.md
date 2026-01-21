# Глоссарий PhotoChanger (SDD)

| Термин | Определение | Ссылки |
|--------|-------------|--------|
| Slot | Статическая конфигурация обработки (`slot-001`…`slot-015`): провайдер, операция, параметры, шаблонные медиа, признак активности. Используется для построения URL ingest. | `docs/PRD.md` §2, §4 |
| Slot ID | Строгое именование слотов `slot-XXX` (три цифры, с leading zero), фиксированный пул 001–015. | `spec/CODEMAP.md`, `spec/docs/domain-model.md` |
| Ingest API | Публичный HTTP-эндпоинт `POST /api/ingest/{slot_id}` для приёма multipart-запросов от DSLR Remote Pro, проверки пароля и запуска обработки. SLA ограничен `T_sync_response`. | `docs/ARCHITECTURE.md` §3, `.memory/USECASES.md` UC2 |
| T_sync_response | Конфигурируемое окно синхронного ответа ingest (10–60 с, по умолчанию 48 с); по превышению возвращается 504 и статус `timeout`. | `.memory/MISSION.md`, `docs/PRD.md` §1 |
| T_ingest_ttl | TTL исходных ingest-файлов во временном хранилище (`MEDIA_ROOT/temp`), совпадает с `T_sync_response`. | `docs/ARCHITECTURE.md` §4 |
| T_public_link_ttl | TTL временных публичных ссылок `media_object` для провайдеров; равен `T_sync_response`, по истечении возвращается `410 Gone`. | `.memory/USECASES.md` UC4 |
| T_result_retention | TTL итоговых файлов и публичных ссылок `/public/results/{job_id}` — 72 ч; по истечении файл удаляется, endpoint отвечает `410 Gone`. | `.memory/MISSION.md`, `docs/PRD.md` §5 |
| MediaObject | Запись о медиафайле с путём к результату (`media/results/{slot_id}/{job_id}/payload.{ext}`), ссылкой на превью и TTL; используется для публикации `/public/results/{job_id}`. | `spec/docs/domain-model.md`, `docs/ARCHITECTURE.md` §4 |
| TempMediaStore | Подсистема временного хранения ingest-файлов в `MEDIA_ROOT/temp` с TTL = `T_ingest_ttl`. | `docs/ARCHITECTURE.md` §4 |
| ResultStore | Подсистема хранения итоговых файлов (`media/results/{slot_id}/{job_id}/payload.{ext}`) и превью (`preview.webp`) с TTL 72 ч (`T_result_retention`). | `docs/ARCHITECTURE.md` §4 |
| TemplateMedia | Статические шаблонные изображения, привязанные к слотам; проходят валидацию MIME/размера, включают обязательное поле `role` в API. | `docs/PRD.md` §5, `spec/contracts/openapi.yaml` |
| ProviderDriver | Абстракция драйвера AI-провайдера с методом `process(job_ctx) -> ProviderResult`. Реализации: `GeminiDriver`, `Gemini3ProDriver`, `GptImage15Driver`, `TurbotextDriver`. | `docs/ARCHITECTURE.md` §5 |
| JobContext | Структура, собираемая `IngestService`: `job_id`, слот, дедлайн `sync_deadline = now + T_sync_response`, каталог результата, параметры провайдера. | `docs/ARCHITECTURE.md` §3 |
| ProviderResult | Унифицированный ответ драйвера (путь к файлу или байты), на основании которого Ingest формирует итоговый результат. | `docs/ARCHITECTURE.md` §5 |
| Ingest password | Глобальный секрет, проверяемый при каждом `POST /api/ingest/{slot_id}`; хранится открыто (`ingest_password`) и управляется через `/api/settings`. | `docs/PRD.md` §4 |
| AppConfig | Центральная функция сборки FastAPI-приложения: подключает БД, подготавливает драйверы провайдеров, загружает настройки окружения; используется также в тестах. | `docs/ARCHITECTURE.md` §2 |
| Admin JWT | Статический JWT для администраторов (`serg`, `igor`), выдаётся `/api/login`, используется в Admin UI/API. | `docs/PRD.md` §3 |
| Provider keys | Поставляемые админом ключи провайдеров (`provider_keys.*`) в `/api/settings`; применяются к runtime конфигурации драйверов. | `spec/contracts/openapi.yaml`, `docs/PRD.md` §4 |
| StatsService | Модуль статистики SLA; агрегирует counters (jobs, timeouts, provider_errors, storage) и публикует `/api/stats`. | `docs/ARCHITECTURE.md` §6 |
| Cleanup cron | Сценарий `scripts/cleanup_media.py`, запускаемый каждые 15 мин для удаления просроченных медиа и обновления `media_object.cleaned_at`. | `docs/PRD.md` §10 |
| Public Result Link | Временный URL `/public/results/{job_id}` с TTL 72 ч; после истечения возвращает `410 Gone`. | `.memory/USECASES.md` UC4 |

## Соглашения по именованию
- Slot IDs: `slot-001`…`slot-015`, три цифры с ведущими нулями; HTML страницам соответствуют те же суффиксы.
- Провайдеры: kebab-case (`gemini-2.5`, `gemini-3-pro-image-preview`, `gpt-image-1.5`, `turbotext`), совпадают с именами схем `spec/contracts/schemas/slot-settings-<provider>.schema.json`.
- Результаты: `media/results/{slot_id}/{job_id}/payload.{ext}` и `preview.webp`; временные файлы — `media/temp/{slot_id}/{job_id}/`; шаблоны — `media/templates/{template_id}`.
- JS модульность слотов: файлы `slot-*.js` в `frontend/slots/assets/` (config/state/api/ui/mapping/events/index/main); новые модули придерживаются префикса `slot-`.
- Документы в `spec/`: корневые стабильные точки — `CODEMAP.md`, `contracts/openapi.yaml`, `contracts/VERSION.json`, `adr/*`, `docs/*`.
