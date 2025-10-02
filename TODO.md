Исправь бриф  @/Docs/brief.md , чтобы перейти на PostgreSQL и обойтись без Redis. Вот формулировки «что и где править».

1) Переименовать и обновить раздел БД

Было: «Модели Данных (SQLite)»
Стало: «Модели данных (PostgreSQL + Alembic)»

В первом абзаце заменить:
«будет использоваться база данных SQLite» → «используется PostgreSQL; схемы версионируются через Alembic (миграции)».

Добавить абзац:
«Все временные метки храним как TIMESTAMP WITH TIME ZONE (UTC). Для полей со схемами и настройками допускается JSONB.»

2) Обновить типы полей и таблицы

В таблицах User/Slot/ProcessingLog:

DATETIME → TIMESTAMP WITH TIME ZONE

Для settings_json можно уточнить: JSONB (вместо TEXT)

Для первичных ключей: оставить как есть (INTEGER/TEXT) или указать:
«PK — BIGSERIAL/UUID (по проектному выбору); внешние ключи — соответствующие типы».

Добавить новые таблицы (для работы без Redis):

Job:
id (UUID PK), slot_id (FK), status (ENUM: queued|processing|done|failed|timeout), provider_async_id (TEXT? NULL), created_at (timestamptz), updated_at (timestamptz), retries (int), request_bytes (int), request_sha256 (text).

Result:
id (UUID PK), job_id (FK), mime (text), bytes (int), path_or_blob (text|bytea), created_at (timestamptz), expires_at (timestamptz), sha256 (text).

В ProcessingLog добавить поля:
job_id (FK), provider_error_code (text), result_id (FK NULL).

3) Заменить стек

В разделе Стек:

«База данных: SQLite» → «База данных: PostgreSQL»

«Очередь задач: Redis» →
«Очередь задач: MVP — in-process asyncio.Queue; при росте — очередь на PostgreSQL через таблицу Job и SELECT … FOR UPDATE SKIP LOCKED (воркеры).»

4) Обновить «Механизм работы платформы»

В подпунктах:

П.2 «Постановка в очередь: … Redis» заменить на:
«Постановка в очередь: in-process asyncio.Queue (MVP) или Job-очередь в PostgreSQL (INSERT INTO job …), выбор включается конфигом.»

П.4 «Отдельный сервис (Worker) забирает задачу из очереди…» уточнить:
«Worker(ы) читают из asyncio.Queue или по PG-паттерну SELECT … FOR UPDATE SKIP LOCKED из таблицы job.»

Добавить подпункт «Ретраи/бэк-прешер»:
«Лимит параллелизма на провайдера/слот; экспоненциальные ретраи при сетевых ошибках; max попыток N; статус в Job.retries.»

Уточнить поведение при таймауте (сохранение результата):
«Если AI > T_sync (≤50с): API возвращает 504; Worker при прохождении завершает job → сохраняет Result на 3 дня (expires_at) — доступно из UI/логов.»

5) Обновить Mermaid-диаграмму (только подписи)

participant Queue as Очередь задач →
participant Queue as Очередь задач (asyncio | PG Job)

API->>Queue: Поставить задачу в очередь — без упоминания Redis.

(Опционально) добавить ветку Worker->>PG: UPDATE job SET status='done' … и API/UI->>PG: GET /result/{id} — как текстовые комментарии на полях диаграммы.

6) В разделе «API Спецификация»

Ничего про Redis не упоминать.

Добавить эндпоинт (если выбираешь модель с «поздним результатом»):

GET /api/results/{job_id} — вернуть метаданные/URL результата, 404 пока нет.

В описании Ingest (DSLR Remote Pro) дописать:
«Сервер возвращает 200 с изображением, если обработка успела ≤ T_sync; иначе — 504. Результат может появиться позже в системе и быть доступным в UI/по GET /api/results/{job_id} (если включено хранение результатов).»

7) В разделе «Frontend → Страница статистики»

Добавить колонки (или описать поля статистики):
последние job_id, последний provider_error_code, сколько задач в очереди, ретраи, ссылка на результат (если сохранён).

Убрать упоминания глобального пароля в явном виде (это про безопасность, но не про PG/Redis — рекомендую хотя бы пометить как «секрет слота», см. ниже).

8) Конфигурация и эксплуатация (добавить маленький подпункт)

«Подключение к БД: postgresql+asyncpg:// …; пул соединений; Alembic миграции.»

«Очередь: режим inprocess или pg (через переменную окружения).»

«Крон-очистка: удаление Result по expires_at; вакуум-обслуживание PG по умолчанию.»

9) Мини-правки по безопасности (к месту)

(Не про Redis напрямую, но лучше зафиксировать одновременно с PG)

В «Ingest» заменить «Глобальный пароль» на «секрет слота + HMAC подпись в query/headers; nonce + TTL для защиты от повторов».

В моделях данных слота добавить поля: secret_hash, rate_limit, on_timeout (drop|store|poll).

10) Чёткие «find→replace» фрагменты

Найти: «будет использоваться база данных SQLite»
Заменить: «используется PostgreSQL; управление схемой — Alembic (миграции).»

Найти: «Очередь задач: Redis»
Заменить: «Очередь задач: in-process asyncio.Queue (MVP); опционально — очередь на PostgreSQL (таблица job, SELECT … FOR UPDATE SKIP LOCKED).»

Найти: все упоминания DATETIME
Заменить: TIMESTAMP WITH TIME ZONE

Найти в таблице Slot: settings_json: TEXT
Заменить: settings_json: JSONB

Добавить раздел: «Миграции: Alembic — init, autogenerate, upgrade head; переменные окружения для DSN PostgreSQL.»

11) Что появится в «Открытые вопросы»

Добавить 2 пункта:

«Какой режим очереди включаем на старте: inprocess или pg?»

«Храним ли тело результата в PG (BYTEA) или только путь на диск (path_or_blob)? Для больших файлов — рекомендуется путь + контрольные суммы.»