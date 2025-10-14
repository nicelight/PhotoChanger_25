

## Роль и общие правила
- Ты — gpt-5-codex, ведущий разработчик, который реализует **Фазу 2 "Генерация стабов и scaffolding"** для проекта PhotoChanger.
- Работай в репозитории `PhotoChanger_25`, строго соблюдая принцип **Spec Driven Development**: код и шаблоны должны следовать контрактам `spec/contracts` и скоупу из SDD (`spec/docs/blueprints`, `Docs/brief.md`).【F:spec/docs/blueprints/context.md†L1-L49】【F:Docs/brief.md†L1-L72】
- Пиши на Python 3.12, придерживайся `ruff format`/`ruff check`, добавляй type hints, docstring-и и `NotImplementedError` там, где бизнес-логики ещё нет.
- Ни один эндпоинт/сервис не должен реализовывать реальную бизнес-логику: только проверяемые заглушки, покрывающие структуру данных и места интеграции.
- Не меняй `spec/contracts` и `spec/docs`; на этой фазе код подгоняется под существующие спецификации.

## Контекст платформы (для понимания структуры кода)
- Платформа обслуживает ingest от DSLR Remote Pro, очередь на PostgreSQL, воркеры и админ/UI, соблюдая дедлайн `T_sync_response` (45–60 с) и TTL файлов (`T_public_link_ttl = T_sync_response`, `T_result_retention = 72h`).【F:spec/docs/blueprints/domain-model.md†L1-L109】【F:Docs/brief.md†L5-L64】
- Основные сущности и ответственность слоёв описаны в `domain-model.md`, `context.md`, `use-cases.md`; кодовые каркасы должны отражать эти разделы, но без реальной бизнес-логики.
- Ключевые сервисы: `JobService`, `SlotService`, `SettingsService`, `MediaService`, `StatsService`, очередь/воркер, адаптеры провайдеров (`Gemini`, `Turbotext`), публичный API для результатов и UI-страницы слотов/статистики.【F:spec/docs/blueprints/use-cases.md†L1-L169】【F:Docs/implementation_roadmap.md†L19-L72】

## Технические ожидания по Фазе 2
Реализуй  подпункт 2.2 `.memory/TASKS.md`:

### 2.2 Доменные сервисы и репозитории
1. Создай пакет `src/app/domain/models/` с dataclass/TypedDict, повторяющими доменные сущности (`Slot`, `Job`, `MediaObject`, `TemplateMedia`, `ProcessingLog`, `Settings`). Эти модели должны включать поля TTL и статусы из `domain-model.md`.
2. Определи интерфейсы сервисов в `src/app/services/`:
   - `job_service.py`, `slot_service.py`, `settings_service.py`, `media_service.py`, `stats_service.py`. В каждом файле — класс с методами, описывающими основной API слоя (например, `create_job`, `finalize_job`, `list_slots`, `update_slot`, `rotate_ingest_password`, `register_media`, `collect_global_stats`). Методы должны принимать/возвращать доменные модели, но содержать `raise NotImplementedError()`.
3. Создай репозитории/адаптеры инфраструктуры в `src/app/infrastructure/`:
   - `job_repository.py` с интерфейсом очереди PostgreSQL (`enqueue`, `acquire_for_processing`, `mark_finalized`, `release_expired`). Добавь docstring о `SELECT … FOR UPDATE SKIP LOCKED` и дедлайне `T_sync_response`.
   - `slot_repository.py`, `settings_repository.py`, `media_storage.py`, `template_storage.py`, `stats_repository.py`.
   - Добавь базовый `unit_of_work.py` или `transaction.py`, фиксирующий контракт для атомарных операций (можно как Protocol).
4. В `src/app/workers/queue_worker.py` создай класс `QueueWorker` с методами `run_once`, `process_job`, `handle_timeout`, `dispatch_to_provider`. Всё снабди docstring-ами с отсылками к TTL/дедлайнам.
5. Обнови `ServiceRegistry`, чтобы он содержал имена ключей (константы) и методы регистрации для новых сервисов/адаптеров. Подготовь `src/app/services/container.py`, который собирает реестр (пока возвращает `NotImplementedError`, но описывает зависимости).
6. В `Docs/backlog/phase2-service-gaps.md` опиши выявленные зависимости и места, где нужна реализация на следующих фазах (минимум: требуемые таблицы БД, конфигурация очереди, внешние адаптеры, фоновые задачи очистки).

## Ограничения и что не делать
- Не реализовывай бизнес-логику (никаких реальных SQL, вызовов провайдеров, TTL-таймеров, шифрования) — только интерфейсы и docstring-и с ожиданиями.
- Не добавляй внешние зависимости без отдельного согласования (используй стандартную библиотеку и уже доступные пакеты FastAPI/Pydantic/HTTPX, которые появятся в будущем фазах).
- Не изменяй спецификации (`spec/contracts`, `spec/docs`).














### 2.2 Доменные сервисы и репозитории
1. Создай пакет `src/app/domain/models/` с dataclass/TypedDict, повторяющими доменные сущности (`Slot`, `Job`, `MediaObject`, `TemplateMedia`, `ProcessingLog`, `Settings`). Эти модели должны включать поля TTL и статусы из `domain-model.md`.
2. Определи интерфейсы сервисов в `src/app/services/`:
   - `job_service.py`, `slot_service.py`, `settings_service.py`, `media_service.py`, `stats_service.py`. В каждом файле — класс с методами, описывающими основной API слоя (например, `create_job`, `finalize_job`, `list_slots`, `update_slot`, `rotate_ingest_password`, `register_media`, `collect_global_stats`). Методы должны принимать/возвращать доменные модели, но содержать `raise NotImplementedError()`.
3. Создай репозитории/адаптеры инфраструктуры в `src/app/infrastructure/`:
   - `job_repository.py` с интерфейсом очереди PostgreSQL (`enqueue`, `acquire_for_processing`, `mark_finalized`, `release_expired`). Добавь docstring о `SELECT … FOR UPDATE SKIP LOCKED` и дедлайне `T_sync_response`.
   - `slot_repository.py`, `settings_repository.py`, `media_storage.py`, `template_storage.py`, `stats_repository.py`.
   - Добавь базовый `unit_of_work.py` или `transaction.py`, фиксирующий контракт для атомарных операций (можно как Protocol).
4. В `src/app/workers/queue_worker.py` создай класс `QueueWorker` с методами `run_once`, `process_job`, `handle_timeout`, `dispatch_to_provider`. Всё снабди docstring-ами с отсылками к TTL/дедлайнам.
5. Обнови `ServiceRegistry`, чтобы он содержал имена ключей (константы) и методы регистрации для новых сервисов/адаптеров. Подготовь `src/app/services/container.py`, который собирает реестр (пока возвращает `NotImplementedError`, но описывает зависимости).
6. В `Docs/backlog/phase2-service-gaps.md` опиши выявленные зависимости и места, где нужна реализация на следующих фазах (минимум: требуемые таблицы БД, конфигурация очереди, внешние адаптеры, фоновые задачи очистки).

### 2.3 Инфраструктурные заглушки
1. Добавь `src/app/providers/base.py` с абстрактным `ProviderAdapter` (методы `prepare_payload`, `submit_job`, `poll_status`, `cancel`). Создай отдельные файлы `providers/gemini.py` и `providers/turbotext.py` с классами, которые реализуют интерфейс, но выбрасывают `NotImplementedError`; опиши лимиты из брифа в docstring-ах.【F:Docs/brief.md†L73-L125】
2. Реализуй каркас конфигурации в `src/app/core/config.py`: Pydantic `BaseSettings` с полями `database_url`, `media_root`, `t_sync_response_seconds`, `jwt_secret`, `provider_keys`. Значения по умолчанию возьми из брифа/SDD (например, `T_sync_response` = 48). Добавь метод `build_default()`.
3. Создай `src/app/core/app.py`, который инициализирует FastAPI приложение, подключает `ApiFacade`, подготавливает DI-контейнер и возвращает `FastAPI`. Внутри оставь TODO/NotImplemented на фактическую регистрацию зависимостей.
4. Подготовь `scripts/gen_stubs.py`, который читает `spec/contracts/openapi.yaml` и `spec/contracts/schemas` и регенерирует API/DTO файлы. Скрипт должен быть идемпотентным и использовать Jinja2/минимальный шаблон. Задокументируй использование в docstring + README секции "Development".
5. Добавь `scripts/check_scaffolding.sh` (bash) для запуска `ruff check`, `ruff format --check`, `mypy`, `pytest -q` (тесты пока могут быть пустыми, но команда должна завершаться успешно).

### 2.4 UI scaffolding без бизнес-логики
1. Создай пакет `src/app/ui/`:
   - `templates/` с базовыми HTML (Jinja2 или HTMX) для страниц: `slots/index.html`, `slots/detail.html`, `stats/index.html`, `results/gallery.html`, `auth/login.html`. Используй структуры из `Docs/frontend-examples/*.html`, но переведи в Jinja2-шаблоны с плейсхолдерами (`{{ slot.name }}`, `{{ result.download_url }}`) и комментариями, что данные пока моковые.【F:Docs/frontend-examples/slot-page.html†L1-L200】
   - `views.py` с FastAPI `APIRouter`, который отдаёт эти шаблоны (используй `Jinja2Templates`), возвращая заглушечные модели/контекст.
   - `mock_data.py` с функциями, генерирующими фиктивные сущности (`SlotViewModel`, `ResultCard`, `GlobalStatsSummary`) на основе Pydantic моделей.
2. Обнови `ApiFacade` (или добавь `UiFacade`) так, чтобы UI-маршруты могли быть подключены отдельно.
3. Подготовь `Docs/ui/README.md` с описанием страниц, состояния данных и TODO для реальной интеграции на следующих фазах.

## Качество и проверки
- Обнови/создай минимальные тесты (`tests/test_imports.py`) гарантируя, что основные модули импортируются без ошибок. Сами тесты могут ограничиваться smoke-проверками (`assert hasattr(...)`).
- После генерации запусти `ruff check .`, `ruff format .`, `mypy src/`, `pytest -q`. Все команды должны проходить (если нужна заглушка — исправь код, а не отключай проверку).
- Убедись, что `scripts/gen_stubs.py` и `scripts/check_scaffolding.sh` имеют shebang и права на выполнение.
- Обнови корневой `README.md` разделом "Development" с инструкциями по генерации стабов и запуску проверок.

## Deliverables
1. Обновлённые пакеты `src/app/api`, `src/app/domain`, `src/app/services`, `src/app/infrastructure`, `src/app/providers`, `src/app/workers`, `src/app/core`, `src/app/ui` с описанным scaffolding.
2. Скрипты `scripts/gen_stubs.py`, `scripts/check_scaffolding.sh`.
3. Документация: `Docs/backlog/phase2-service-gaps.md`, `Docs/ui/README.md`, README обновления.
4. Минимальные smoke-тесты и настройки (можно в `tests/`).
5. Все новые файлы должны быть добавлены в `__all__`/`__init__` по мере необходимости.


