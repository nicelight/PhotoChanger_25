# Общее описание функционала веб сервера
Сервер представляет из себя Платформу для AI обработки фотографий. 
## Пользовательский workflow
 
 Пользователь авторизуется в веб интерфейсе платформы и попадает на Главную страницу выбора слота настроек. Выбирая соответствующий слот, пользователь попадает в Страницу-вкладку настроек обработки фотографии. 

**Процесс настройки слота:**
1.  **Выбор Провайдера:** Пользователь выбирает из списка, какую AI-платформу использовать (например, `Gemini`, `Turbotext`).
2.  **Выбор Операции:** В зависимости от выбранного провайдера, появляется второй список с доступными операциями (например, для `Gemini` это будут `Style Transfer`, `Identity Transfer`, `Image Edit`).
3.  **Настройка Параметров:** Интерфейс автоматически отображает поля, необходимые именно для этой операции (например, текстовый промпт, поле для загрузки стилевого изображения и т.д.).

После настройки пользователь сохраняет слот. На главной странице в списке слотов теперь отображается имя этого слота и рядом отображена ingest-ссылка. Рядом с сылкой присутствует кнопка "Копировать" для копирования ссылки. Пользователь копирует ingest-ссылку слота и вставляет ее в DSLR Remote Pro. Теперь программа отправляет `POST` c файлом на этот адрес. В теле `POST` находится обрабатываемая фотография, пароль и некоторые другие поля.

> **Важно:** со стороны DSLR Remote Pro нам известна только фактическая форма запроса (см. пример ниже). Из обязательных полей подтверждены `password` и данные, описывающие отправляемую фотографию (сама фотография и её метаданные). Остальные поля обрабатываются как опциональные, пока не появится официальная документация.


## Цель платформы
Ожидать ingest-POST на разных эндпоинтах и, согласно слоту, вызывать соответствующую AI-модель.
По получению запроса, в зависимости от того на какой входящий эндпоинт он пришел, платформа формирует исходящий запрос к соответствующей AI модели для обработки фотографии. Запрос формируется на основании данных из слота, к которому привязан входящий эндпоинт. Платформа получает тем или иным методом обработанную фотографию от AI модели. Платформа отправляет обработанную фотографию в теле ответа на пользовательский POST запрос. По истечении 60 секунд с момента получения пользовательского запроса, исходная фотография и  удаляется из временной папки сервера. Обработанные фотографии, отправленные пользователю в ответе на входящий POT запрос, удаляются спустя 3 дня с момента их сохранения во временной папке.

### Провайдер Gemini (image generation & editing)

- Поддерживаемые сценарии — генерация изображений, редактирование «edit-with-prompt», multi-image fusion и стилизация на модели `gemini-2.5-flash-image`.
- Все запросы выполняются методом `models.generateContent` с передачей текста и изображений через `contents.parts` (`text`, `inline_data`, `file_data`). Для крупных файлов используется Files API (`file_uri`), который хранит до 2 ГБ на файл и 20 ГБ на проект в течение 48 часов.
- Лимиты Gemini, обязательные к соблюдению: Files API принимает изображения только `image/png`, `image/jpeg`, `image/webp`, `image/heic`, `image/heif`; каждый файл ≤ 2 ГБ, суммарное хранилище проекта ≤ 20 ГБ, файлы удаляются спустя 48 ч; базовые квоты модели `gemini-2.5-flash-image` — 500 запросов в минуту, 2 000 запросов в день и 500 000 токенов в минуту (Tier 2). UI и валидация должны учитывать эти ограничения.

# Механизм работы платформы

Платформа использует архитектуру "Асинхронного моста" для обработки запросов от DSLR Remote Pro в рамках 50‑секундного таймаута, даже если AI‑модель работает дольше. Значение таймаута (T_sync_response, по умолчанию ≤ 50 c) настраивается на странице статистики.

1. Приём запроса: Ingest API получает POST и валидирует вход (MIME/размер/EXIF и т.п.).
2. Постановка в очередь: запрос помещается в очередь без Redis:
   - MVP: in‑process asyncio.Queue (ограниченная, с back‑pressure).
   - При росте: очередь в PostgreSQL (таблица job, выборка задач через SELECT … FOR UPDATE SKIP LOCKED). Режим выбирается конфигурацией.
3. Ожидание с таймаутом: обработчик API ждёт результат не дольше ~48 c (внутреннее ожидание < T_sync_response).
4. Фоновая обработка: worker(ы) забирают задачу из asyncio.Queue или из таблицы job (PG), вызывают внешнего AI‑провайдера. Если провайдер возвращает async_id, ожидание переносится на webhook/поллинг.
5. Завершение задачи:
   - Успех (AI < 48 c): worker получает результат, сохраняет `Result` во временном хранилище с TTL 3 дня, фиксирует `Job.status = 'completed'`
     и передаёт обработанное изображение в API → API возвращает его клиенту (200 OK).
   - Таймаут (AI > 48 c): API возвращает 504 Gateway Timeout, закрывает соединение, помечает задачу как `failed_timeout` и
     инициирует отмену воркеру.
     Worker прекращает дальнейшие действия по задаче, отменяет обращение к провайдеру (если это поддерживается) и очищает
     временные данные без сохранения `Result`. Ретраи прекращаются, как только зафиксирован `failed_timeout`, а DSLR Remote Pro
     должен отправить новый ingest-запрос с исходной фотографией. Для таймаутов сервер ведёт агрегированную статистику
     (счётчик, время, слот).

6. Ретраи и back‑pressure: ограничение параллелизма на провайдера/слот; экспоненциальные ретраи при сетевых сбоях (до N попыток);
   статус и счётчик попыток фиксируются в job/логах. Ретраи выполняются только внутри 48‑секундного окна с момента исходного POST,
   пока задача не получила финальный статус (`completed`, `failed_timeout`, `failed_provider`, `cancelled`). После наступления
   любого финального состояния воркер прекращает обработку и освобождает ресурсы. Если провайдер не вернул успешный ответ за
   допустимое число попыток, задача получает `failed_provider`; внешняя отмена (например, ручное снятие слота из очереди) переводит
   задачу в `cancelled`.
Если результат от провайдера не пришёл в течение T_sync_response, ingest завершается 504 с фиксацией `failed_timeout` и без сохранения `Result`. 
```mermaid
sequenceDiagram
    participant DSLR as DSLR Remote Pro
    participant API as Ingest API
    participant Queue as Очередь задач (asyncio | PG Job)
    participant Worker as AI Worker
    participant AI_Provider as AI Провайдер
    participant Storage as Хранилище результатов

    DSLR->>API: POST /ingest/{slotId} с фото
    activate API
    API->>Queue: Поставить задачу в очередь
    API->>API: Начать ожидание результата (~48с)
    Queue->>Worker: Отправить задачу на обработку
    activate Worker
    Worker->>AI_Provider: Запрос на обработку фото
    activate AI_Provider
    AI_Provider-->>Worker: Готовое изображение (или async_id)
    deactivate AI_Provider
    Worker->>Storage: Сохранить Result (TTL 3 дня)
    Worker->>API: Уведомить о результате (при sync)
    API-->>DSLR: Отправить обработанное фото (HTTP 200 OK)
    deactivate API
    deactivate Worker

    alt Таймаут
        API->>API: Ожидание превысило ~48с
        API-->>DSLR: Вернуть ошибку 504
        API-->>Worker: Отменить задачу (failed_timeout)
        Worker->>Storage: Очистить временные данные
        note over API,Worker: После 48с задача завершается окончательно; для повторной обработки нужен новый POST
    end
```

## Временное публичное медиа-хранилище (для Turbotext)
Назначение: выдавать временные публичные ссылки на изображения, чтобы передавать их в поля url_image_target и url Turbotext.

### Краткие требования
- TTL ссылки: по умолчанию 10–15 минут (настраиваемо).
- Форматы: JPEG/PNG/WEBP (минимальный набор можно расширять).
- Размеры: лимит по размеру файла и по пикселям (конфиг).
- Хранение: локальная папка MEDIA_ROOT; автоматическая очистка просроченных файлов.
### Конфигурация (параметры)

* MEDIA_ROOT — путь для временных файлов (например, /var/app/media/tmp)
* PUBLIC_BASE_URL — базовый URL для раздачи (например, https://api.example.com/public/media)
* MEDIA_PUBLIC_LINK_DEFAULT_TTL_SEC — время жизни ссылок (например, 900)
* MEDIA_ALLOWED_MIME — список допустимых MIME
* MEDIA_MAX_FILE_SIZE_MB — лимит размера

### Эндпоинты (минимальный набор)

- POST /api/media/register — принять файл, сохранить, вернуть id, public_url, expires_at (используется только для временных
  объектов, не для шаблонов).
- POST /api/template-media/register — загрузить постоянный шаблон, вернуть `template_media_id`, относительный путь и метаданные;
  обновляет привязки слота.
- DELETE /api/template-media/{id} — удалить шаблон и очистить привязки; используется кнопкой «Убрать» на странице слота.
- GET /public/media/{id} — отдать файл, если не истёк expires_at.
- POST /api/media/extend (опционально) — продлить expires_at для активной задачи.

> **Аутентификация:** для публичного медиа-хранилища отдельная схема авторизации не требуется. Доступ к POST-эндпоинтам контролируется общей авторизацией платформы; GET /public/media/{id} остаётся публичным до истечения срока жизни ссылки.

### Жизненный цикл
- Ingest принял фото → зарегистрировал в медиа-хранилище → получил public_url.
- Воркер передал public_url в запрос к Turbotext.
- Turbotext скачал файл по ссылке и выполнил операцию.
- По завершении задачи файл остаётся доступным до expires_at.
- Плановая очистка регулярно удаляет просроченные файлы и записи.

### Постоянное хранилище шаблонов (`template_media`)
- **Назначение:** хранить многоразовые эталонные изображения (стили, лица, фоны), которые администраторы загружают один раз и
  привязывают к слотам. Эти файлы не удаляются автоматически и используются при каждом запуске соответствующего слота.
- **Каталог:** `MEDIA_ROOT/templates` (иерархия по префиксу UUID или checksum). Файлы выкладываются только из бек-офиса; публичных
  прямых ссылок нет — доступ к содержимому выдаётся воркеру через файловую систему.
- **Таблица `template_media`:**
  * `id` (`UUID`, PK) — идентификатор, который сохраняется в `Slot.settings_json`.
  * `path` (`TEXT`) — относительный путь в `MEDIA_ROOT/templates`.
  * `mime` (`TEXT`), `size_bytes` (`INTEGER`), `checksum` (`TEXT`) — метаданные для контроля целостности.
  * `uploaded_by` (`INTEGER`, FK → `User`), `created_at` (`TIMESTAMPTZ`).
  * `label` (`TEXT`, nullable) — человекочитаемое имя шаблона для UI.
- **Таблица связей `slot_template_binding`:** (`slot_id` `TEXT` FK → `Slot`, `setting_key` `TEXT`, `template_media_id` `UUID` FK →
  `template_media`, `created_at` `TIMESTAMPTZ`). Используется для аудита и повторной синхронизации, когда слот обновляет набор
  шаблонов. При изменении `settings_json` привязки пересоздаются.
- **Отсутствие авто-GC:** очистители `media_object`/TTL не затрагивают `template_media`; удаление выполняется только по явному
  запросу администратора через API или UI.
- **Права доступа:** загрузка/удаление доступны пользователям с `slots:write`. Чтение выполняется опосредованно — воркеры и UI
  используют ID шаблона из настроек слота, прямых GET-эндпоинтов без авторизации нет.

## Turbotext: очередь, polling и webhook

**Создание задачи**

```http
POST /api_ai/<method> HTTP/1.1
Host: turbotext.ru
Authorization: Bearer {APIKEY}
Content-Type: application/x-www-form-urlencoded

do=create_queue
webhook=https://example.com/hook (опционально)
<поля метода>
```

- Ответ без webhook: `{"success": true, "queueid": <ID>}`. Это значение должно сохраняться в `Job.external_ref` для последующего опроса.
- Ответ с webhook: `{"success": true, "asyncid": <ID>}` — идентификатор совпадает с очередью, worker больше не опрашивает Turbotext и ждёт POST от провайдера.

**Опрос результата**

```http
POST /api_ai/<method> HTTP/1.1
Authorization: Bearer {APIKEY}
Content-Type: application/x-www-form-urlencoded

do=get_result
queueid:<ID>
```

- Пока задача в работе, Turbotext возвращает `{"action": "reconnect"}` и не увеличивает счётчик попыток.
- После завершения приходит JSON с полями `success`, `error`, `data`, `uploaded_image` и (иногда) `limits`.

**Финальный JSON (для polling и webhook одинаковый):**

```json
{
  "success": true,
  "error": "",
  "data": {
    "image": ["image/<method>_id12_0.png"],
    "prompt": "...",
    "width": 768,
    "height": 768,
    "face_restore": "False"
  },
  "uploaded_image": "https://www.turbotext.ru/download.php?f=....png",
  "limits": { "foto_limit": 123, "text_limit": 123 }
}
```

- Параметр `uploaded_image` содержит прямую ссылку на результат — её нужно скачать и сохранить во временное хранилище результатов.
- Turbotext присылает webhook в формате идентичном успешному ответу `do=get_result`; сервис обязан вернуть HTTP 200.

# Архитектура и стек приложения
## Архитектура
**1. Архитектура проекта ориентирована на безопасность изменений кода** при генерации кода LLM моделью: тонкие фасады + pure domain + контракт-first + Spec Driven Dev
**2. Архитектура проекта должна обладать Низкой связанностью (low coupling):**
 * Каждый модуль/фасад имеет отдельную ответственность.
 * Сервисы и домен не знают про инфраструктуру напрямую — используют фасады и интерфейсы.
 * Любой слой зависит только от более внутреннего слоя.
**3. Архитектура проекта должна обладать Высокой когезией (high cohesion):**
 * Каждый класс или модуль отвечает за один аспект.
 * DTO и типы фиксируют контракты между слоями, уменьшая «размазанность» логики.

### Модели данных (PostgreSQL + Alembic)
Для хранения состояния приложения, настроек слотов и сбора статистики будет использоваться база данных PostgreSQL; схемы версионируются через Alembic (миграции)
Все временные метки храним как `TIMESTAMP WITH TIME ZONE` (UTC). Для полей со схемами и настройками допускается `JSONB`.

**Таблица `User`**

*   `id`: `INTEGER` (Primary Key)
*   `username`: `TEXT` (уникальный; в боевой конфигурации допустимы только два предустановленных значения — `serg` и `igor`)
*   `hashed_password`: `TEXT` (хэш статически сгенерированного случайного пароля)
*   `permissions`: `TEXT[]` (набор строковых прав доступа вида `<область>:<действие>`)

> Управление пользователями выполняется только на этапе деплоя. В приложении отсутствуют эндпоинты и UI для создания, удаления или
> изменения учётных записей. Единственный способ заменить пароль — перегенерировать секреты и перезапустить сервис.


#### Права доступа и роли

`User.permissions` хранит массив строковых прав, который наполняется первоначальной миграцией и редактируется только вручную (через деплой/миграцию). При входе в систему сервис читает этот массив, добавляет его в JWT как claim `permissions`, и дальнейшие эндпоинты используют guard `RequirePermission` (FastAPI `Depends`) для проверки наличия требуемого права.

Допустимые права MVP:

| Право            | Назначение                                                                 | Используется в проверках |
|------------------|-----------------------------------------------------------------------------|---------------------------|
| `slots:read`     | Просмотр списка провайдеров, чтение конфигурации слотов                    | `GET /api/providers`, `GET /api/slots`, `GET /api/slots/{slot_id}` |
| `slots:write`    | Изменение конфигурации слотов и сброс статистики                           | `PUT /api/slots/{slot_id}`, `POST /api/slots/{slot_id}/reset_stats` |
| `stats:read`     | Просмотр статистики по слотам и глобальной статистики                      | `GET /api/stats/{slot_id}`, `GET /api/stats/global` |
| `settings:read`  | Просмотр глобальных настроек и статуса секретов                            | `GET /api/settings` |
| `settings:write` | Обновление глобальных настроек, вращение ingest-пароля, очистка медиа-кеша | `PUT /api/settings`, `POST /api/media/cache/purge` |

Предустановленные пользователи получают фиксированные наборы прав (редактируются только миграцией):

* `serg` — полный административный доступ: `slots:read`, `slots:write`, `stats:read`, `settings:read`, `settings:write`.
* `igor` — операционный доступ без изменения глобальных секретов: `slots:read`, `slots:write`, `stats:read`, `settings:read`.

Пользователи с правом `settings:write` автоматически удовлетворяют сценариям вращения ingest-пароля и очистки кеша; остальные эндпоинты отклоняют запросы с кодом `403` при отсутствии нужного права.



**Таблица `Slot`**
*   `id`: `TEXT` (Primary Key, одна из 15 предустановленных статических ingest-ссылок `slot-001` … `slot-015`)
*   `name`: `TEXT` (Имя, которое задает пользователь)
*   `user_id`: `INTEGER` (Foreign Key -> User)
*   `provider_id`: `TEXT` (ID провайдера из конфигурационного файла)
*   `operation_id`: `TEXT` (ID операции из конфигурационного файла)
*   `settings_json`: `TEXT` (JSON-строка с параметрами для AI-операции)
*   `last_reset_at`: `TIMESTAMP WITH TIME ZONE` (Дата последнего сброса статистики для этого слота)
*   `created_at`: `TIMESTAMP WITH TIME ZONE` (Момент первичного создания записи миграцией)
*   `updated_at`: `TIMESTAMP WITH TIME ZONE` (Момент последнего изменения настроек слота через API/UI)

> Для MVP доступно строго 15 ingest-слотов с фиксированными идентификаторами (`slot-001` … `slot-015`). Первая миграция базы данных
> создаёт эти записи один раз на всю платформу и формирует глобальный пул ingest-URL. Новые пользователи используют те же 15
> записей — `id` не дублируются и не пересоздаются. Поле `user_id` указывает, за кем закреплён слот; если слот свободен, значение
> `NULL`. Повторная настройка выполняется поверх существующей записи: `id` остаётся неизменным, а привязанная ingest-ссылка
> сохраняется на всём сроке жизни платформы.


**Таблица `Job`**
*   `id`: `UUID` (Primary Key)
*   `slot_id`: `TEXT` (Foreign Key -> Slot)
*   `status`: `TEXT` (enum: `pending`, `processing`, `completed`, `failed_timeout`, `failed_provider`, `cancelled`)
*   `attempt`: `INTEGER` (номер текущей попытки, начинается с 1)
*   `max_attempts`: `INTEGER` (лимит ретраев, вычисляется по политике провайдера/слота)
*   `priority`: `INTEGER` (используется при выборке из очереди, чем меньше число — тем выше приоритет)
*   `payload_path`: `TEXT` (путь к временно сохранённому ingest-файлу/метаданным)
*   `external_queue_id`: `TEXT` (значение `queueid` для Turbotext и аналогов; nullable)
*   `external_async_id`: `TEXT` (идентификатор async/webhook-потока провайдера; nullable)
*   `external_metadata`: `JSONB` (дополнительные атрибуты ответа провайдера — лимиты, diagnostic codes)
*   `locked_by`: `TEXT` (идентификатор воркера, удерживающего задачу)
*   `locked_at`: `TIMESTAMP WITH TIME ZONE` (момент захвата задачи воркером)
*   `last_attempt_at`: `TIMESTAMP WITH TIME ZONE` (время запуска текущей попытки)
*   `next_retry_at`: `TIMESTAMP WITH TIME ZONE` (момент, после которого задача снова доступна для обработки)
*   `created_at`: `TIMESTAMP WITH TIME ZONE`
*   `updated_at`: `TIMESTAMP WITH TIME ZONE`

`Job.status` фиксирует жизненный цикл задачи с учётом таймаутов и повторных попыток. При 504 от API статус переводится в
`failed_timeout`, `locked_by` очищается, после чего задача считается финализированной и дополнительные попытки не планируются.
Воркеры, работающие через
PostgreSQL, выбирают задачи запросом `SELECT … FOR UPDATE SKIP LOCKED`, обновляют `locked_by`/`locked_at`, увеличивают `attempt`
и записывают `last_attempt_at`. Для in-process `asyncio.Queue` таблица используется для журналирования и восстановления после
рестарта — запись создаётся синхронно с постановкой в очередь.

**Таблица/реестр `Result`**
*   `id`: `UUID` (Primary Key)
*   `job_id`: `UUID` (Foreign Key -> Job, UNIQUE)
*   `storage_path`: `TEXT` (путь к файлу в MEDIA_ROOT или S3-бакинге)
*   `mime_type`: `TEXT` (MIME результирующего изображения)
*   `size_bytes`: `INTEGER`
*   `checksum`: `TEXT` (SHA-256 для дедупликации/проверки целостности)
*   `expires_at`: `TIMESTAMP WITH TIME ZONE` (момент автоматического удаления)
*   `created_at`: `TIMESTAMP WITH TIME ZONE`
*   `metadata`: `JSONB` (дополнительные поля провайдера: prompt, applied_settings)

`Result.expires_at` заполняется воркером исходя из глобальной настройки `media.processed_ttl_hours`. При успешном завершении
обработки воркер атомарно обновляет `Job.status = 'completed'`, создаёт запись в `Result` и кладёт обработанный файл в
`MEDIA_ROOT`. Реестр `Result` используется для учёта сохранённых файлов и контроля срока их жизни: внутренние сервисы платформы
сверяются с `expires_at`, чтобы определить доступность результата. Плановая очистка (GC) удаляет просроченные записи и
освобождает связанные файлы, опираясь на `Result.expires_at`.

`Job` и `Result` также связаны с `media_object`: если провайдер требует публичные ссылки, воркер регистрирует файлы через
`media_object`, а поле `payload_path`/`storage_path` хранит относительный путь до итогового изображения. При таймауте API (шаг
5 архитектуры) задача переводится в `failed_timeout`, воркер при получении такого статуса должен отменить активный запрос и
удалить временные файлы (`payload_path`, записи в `media_object` без `Result`). Ретраи (`attempt < max_attempts`) планируются через
`next_retry_at` только пока не истекло 48‑секундное окно с момента исходного POST и не зафиксирован финальный статус; если
лимит попыток исчерпан до истечения окна, статус становится `failed_provider`, что отображается в статистике слота и в ответах API.



**Таблица `ProcessingLog`**
*   `id`: `INTEGER` (Primary Key)
*   `slot_id`: `TEXT` (Foreign Key -> Slot)
*   `created_at`: `TIMESTAMP WITH TIME ZONE` (Время получения ingest-запроса)
*   `status`: `TEXT` (`SUCCESS`, `ERROR`, `TIMEOUT`)
*   `response_time_ms`: `INTEGER` (Время ответа в миллисекундах)
*   `cost`: `REAL` (Стоимость операции, если применимо)
*   `error_message`: `TEXT` (Сообщение об ошибке)


**Таблица `media_object`**
* id (UUID, PK)
* path (TEXT) — путь к файлу в MEDIA_ROOT
* mime (TEXT)
* size_bytes (INTEGER)
* created_at (TIMESTAMPTZ)
* expires_at (TIMESTAMPTZ)
* job_id (UUID, опционально) — связь с задачей обработки

Поле `expires_at` задаёт срок жизни временной ссылки на медиа-файл: оно заполняется при вызове `POST /api/media/register`,
используется проверкой доступа в `GET /public/media/{id}`, может продлеваться эндпоинтом `POST /api/media/extend`, а также
определяет, когда воркер и плановая очистка должны удалить просроченные файлы.

Продление TTL выполняется управляемо и в двух случаях:

* **UI/бекенд при сохранении слота.** Когда администратор сохраняет настройки или запускает тестовую загрузку, фронтенд
  передаёт текущие `media_object.id` в теле запроса, а бекенд, прежде чем записать `source_media_id` в `Slot.settings_json`,
  вызывает `POST /api/media/extend` (повторную регистрацию файла) для каждого временного вложения. Запрос ограничивает новое значение `expires_at`
  настройкой `media.max_manual_ttl_sec`, чтобы ручные продления не превышали безопасный предел.
* **Воркер перед постановкой задачи в очередь.** Перед тем как добавить ingest в очередь провайдера Turbotext, воркер повторно
  продлевает связанные `media_object` (например, исходный `source_media_id`) тем же эндпоинтом и той же границей по
  `max_manual_ttl_sec`, гарантируя, что ссылка останется валидной на всё время асинхронной обработки.

Если попытка продлить TTL превышает лимит `max_manual_ttl_sec`, бекенд возвращает ошибку, а UI сигнализирует пользователю, что
временную ссылку нужно перезагрузить (повторно вызвать `POST /api/media/register`).

## API глобальных настроек и управление секретами

### GET /api/settings

Возвращает текущие глобальные настройки платформы. Требует авторизованного пользователя с правом `settings:read` (см. раздел «Права доступа и роли» и UI «Страница настроек»). Ответ 200 OK содержит JSON следующей структуры:

```json
{
  "dslr_password": {
    "is_set": true,
    "updated_at": "2024-05-14T12:30:00Z",
    "updated_by": "serg"
  },
  "provider_keys": {
    "gemini": {
      "is_configured": true,
      "updated_at": "2024-05-10T08:00:00Z",
      "updated_by": "serg"
    },
    "turbotext": {
      "is_configured": false,
      "updated_at": null,
      "updated_by": null
    }
  },
  "media_cache": {
    "processed_media_ttl_hours": 72,
    "public_link_default_ttl_sec": 900,
    "max_manual_ttl_sec": 86400
  }
}
```

Если отдельные значения не заданы, соответствующие поля возвращаются со значением `null` или булевым `false`. API никогда не возвращает открытые секреты — UI отображает только факт наличия значения и метаданные об обновлении. Для провайдера, который требует дополнительных не секретных параметров (например, `project_id`), ответ может дополнительно содержать их в явном виде.

### PUT /api/settings

Обновляет глобальные настройки. Требуется право `settings:write` (см. раздел «Права доступа и роли»). Запрос принимает JSON, в котором поля совпадают по структуре с ответом `GET /api/settings`, но для секретов передаётся вложенный объект `value`:

```json
{
  "dslr_password": { "value": "new-password" },
  "provider_keys": {
    "gemini": { "api_key": "AIza...", "project_id": "photochanger-prod" }
  },
  "media_cache": {
    "processed_media_ttl_hours": 72
  }
}
```

Необязательные поля можно опускать — сервер обновляет только переданные значения. Успешный ответ `200 OK` возвращает структуру, идентичную `GET /api/settings` (без раскрытия секретов). Валидация: `processed_media_ttl_hours` ∈ [1, 168], `public_link_default_ttl_sec` ∈ [60, 86400], `max_manual_ttl_sec` ≥ `public_link_default_ttl_sec`.

### Кнопка «Очистить мультимедиа кеш»

Кнопка на странице настроек вызывает `POST /api/media/cache/purge`. Эндпоинт требует права `settings:write` (см. раздел «Права доступа и роли»), выполняет фоновое удаление всех записей `media_object`, у которых `expires_at` не наступил, но которые относятся к «обработанным фотографиям», сохраняемым до 3 суток, и удаляет связанные файлы в `MEDIA_ROOT`. Шаблонные файлы (`template_media`) и их привязки очистка не затрагивает. Ответ: `202 Accepted` с телом

```json
{
  "status": "scheduled",
  "started_at": "2024-05-14T12:31:00Z"
}
```

После завершения фонового задания статистика очистки (количество удалённых файлов, объём) логируется и доступна через системные метрики.

### Требования к хранению и шифрованию глобальных настроек

* DSLR-пароль хранится только в виде хэша `Argon2id` с индивидуальной солью. Таблица `app_settings` дополнена колонками `dslr_password_hash` (BYTEA), `dslr_password_salt` (BYTEA), `dslr_password_updated_at` (TIMESTAMPTZ) и `dslr_password_updated_by` (INTEGER, FK → User). При сохранении нового пароля в `PUT /api/settings` сервер перехеширует значение и удалит исходный plaintext сразу после применения. Эти поля используются для формирования ответа `GET /api/settings` (`is_set = dslr_password_hash IS NOT NULL`).
* API-ключи провайдеров сохраняются в таблице `provider_secret` и шифруются алгоритмом AES-256-GCM; мастер-ключ шифрования берётся из переменной окружения `SETTINGS_MASTER_KEY`. Структура таблицы:
  * `id` (SERIAL, PK)
  * `provider_id` (TEXT, уникальный)
  * `encrypted_payload` (BYTEA)
  * `nonce` (BYTEA)
  * `version` (INTEGER, default 1)
  * `updated_at` (TIMESTAMPTZ)
  * `updated_by` (INTEGER, FK → User)
  * `has_secret` (BOOLEAN, default false) — признак наличия расшифровываемого ключа (используется в `GET /api/settings`)
* Значения TTL (`processed_media_ttl_hours`, `public_link_default_ttl_sec`, `max_manual_ttl_sec`) и другие не чувствительные параметры хранятся в таблице `app_settings` (`key` TEXT PK, `value_json` JSONB, `updated_at` TIMESTAMPTZ, `updated_by` FK → User). Эти настройки распространяются только на `media_object`; `template_media` хранится без TTL и очищается вручную. Миграции должны создавать уникальные ключи `media.processed_ttl_hours`, `media.public_link_default_ttl_sec`, `media.max_manual_ttl_sec` и обеспечить их начальные значения (72, 900 и 86400 соответственно). Если для удобства UI требуется отображать метаданные провайдеров без расшифровки (`project_id`, `region` и т. п.), миграции должны добавить отдельные строки `provider.<id>.<field>` в `app_settings`.
* Доступ к чтению и расшифровке секретов предоставляется только слоям с правами `settings:read`/`settings:write`. Логирование секретов запрещено, в логах допускается только информация о наличии/отсутствии значения и времени обновления.

**Конфигурационные файлы**
Данные о Провайдерах (`Providers`) и их Операциях (`Operations`) будут храниться в статических конфигурационных файлах (например, `providers.json`), чтобы избежать усложнения схемы БД.

### Схема конфигурации провайдеров и параметров слота

Конфигурация разделена на два слоя:

1. **`configs/providers.json`** — статический каталог провайдеров и поддерживаемых операций. Файл публикуется веб-сервером как статический ресурс (например, `/static/providers.json`), поэтому UI загружает именно его для построения форм выбора и валидации параметров. Бэкенд использует тот же локальный файл при проверке запросов и формировании исходящих обращений к провайдерам.
2. **`Slot.settings_json`** — сериализованное представление параметров операции, которые пользователь выбрал при настройке слота.

#### Формат `configs/providers.json`

```json
{
  "providers": [
    {
      "id": "gemini",
      "title": "Gemini",
      "ingest": {
        "max_parallel_jobs": 4,
        "timeout_sec": 48,
        "allowed_mime": ["image/jpeg", "image/png"],
        "max_file_size_mb": 20
      },
      "operations": [
        "style_transfer",
        "image_edit",
        "identity_transfer"
      ]
    },
    {
      "id": "turbotext",
      "title": "TurboText",
      "ingest": {
        "max_parallel_jobs": 2,
        "timeout_sec": 48,
        "allowed_mime": ["image/jpeg", "image/png"],
        "max_file_size_mb": 15,
        "requires_public_media": true
      },
      "operations": [
        "style_transfer",
        "image_edit",
        "identity_transfer"
      ]
    }
  ],
  "operations": {
    "style_transfer": {
      "title": "Style Transfer",
      "description": "Перенос художественного стиля между изображениями: Gemini использует эталонное фото, Turbotext — целевое + стилевое.",
      "required_settings": {
        "common": ["prompt"],
        "per_provider": {
          "gemini": ["reference_media_id"],
          "turbotext": ["target_media_id", "style_media_id"]
        }
      },
      "provider_overrides": {
        "gemini": { "endpoint": "/v1beta/models/gemini-image:transferStyle" },
        "turbotext": {
          "endpoint": "/api_ai/mix_images",
          "field_map": {
            "url_image_target": { "from": "template_media", "setting": "target_media_id" },
            "url": { "from": "template_media", "setting": "style_media_id" },
            "content": { "from": "settings", "setting": "prompt" }
          },
          "queue_based": true,
          "webhook_supported": true
        }
      },
      "settings_schema": {
        "type": "object",
        "properties": {
          "prompt": { "type": "string", "maxLength": 2000 },
          "reference_media_id": { "type": "string", "format": "uuid" },
          "style_strength": { "type": "number", "minimum": 0, "maximum": 1, "default": 0.65 },
          "target_media_id": { "type": "string", "format": "uuid" },
          "style_media_id": { "type": "string", "format": "uuid" },
          "output": {
            "type": "object",
            "properties": {
              "format": { "type": "string", "enum": ["jpeg", "png", "webp"], "default": "jpeg" },
              "max_side_px": { "type": "integer", "minimum": 256, "maximum": 4096, "default": 2048 }
            }
          }
        },
        "required": ["prompt"],
        "oneOf": [
          { "required": ["reference_media_id"] },
          { "required": ["target_media_id", "style_media_id"] }
        ],
        "additionalProperties": false
      }
    },
    "image_edit": {
      "title": "Image Edit",
      "description": "Локальное редактирование исходного изображения по текстовому описанию с поддержкой image-to-image.",
      "required_settings": {
        "common": ["prompt"],
        "per_provider": {
          "turbotext": ["source_media_id"]
        }
      },
      "provider_overrides": {
        "gemini": {
          "endpoint": "/v1beta/models/gemini-image:edit",
          "media_parts": [
            { "id": "ingest_media", "from": "ingest_request" }
          ]
        },
        "turbotext": {
          "endpoint": "/api_ai/generate_image2image",
          "field_map": {
            "url": { "from": "media_object", "setting": "source_media_id" },
            "content": { "from": "settings", "setting": "prompt" },
            "strength": { "from": "settings", "setting": "strength" },
            "seed": { "from": "settings", "setting": "seed" },
            "scale": { "from": "settings", "setting": "scale" },
            "negative_prompt": { "from": "settings", "setting": "negative_prompt" },
            "original_language": { "from": "settings", "setting": "original_language" }
          },
          "queue_based": true,
          "webhook_supported": true
        }
      },
      "settings_schema": {
        "type": "object",
        "properties": {
          "prompt": { "type": "string", "maxLength": 2000 },
          "guidance_scale": { "type": "number", "minimum": 0, "maximum": 20, "default": 7.5 },
          "source_media_id": { "type": "string", "format": "uuid" },
          "strength": { "type": "integer", "minimum": 0, "maximum": 80, "default": 40 },
          "seed": { "type": "integer", "minimum": 1, "maximum": 10000000000 },
          "scale": { "type": "number", "minimum": 0.1, "maximum": 20, "default": 7.5 },
          "negative_prompt": { "type": "string", "maxLength": 1000 },
          "original_language": { "type": "string", "default": "ru" },
          "output": {
            "type": "object",
            "properties": {
              "format": { "type": "string", "enum": ["jpeg", "png", "webp"], "default": "png" },
              "quality": { "type": "integer", "minimum": 1, "maximum": 100, "default": 100 }
            }
          }
        },
        "required": ["prompt"],
        "additionalProperties": false
      }
    },
    "identity_transfer": {
      "title": "Identity Transfer",
      "description": "Замена или совмещение лица между изображениями: Gemini работает через compose, Turbotext — через deepfake_photo.",
      "required_settings": {
        "per_provider": {
          "gemini": ["base_media_id", "overlay_media_id"],
          "turbotext": ["subject_media_id", "face_media_id"]
        }
      },
      "provider_overrides": {
        "gemini": {
          "endpoint": "/v1beta/models/gemini-image:compose"
        },
        "turbotext": {
          "endpoint": "/api_ai/deepfake_photo",
          "field_map": {
            "url": { "from": "template_media", "setting": "subject_media_id" },
            "url_image_target": { "from": "template_media", "setting": "face_media_id" },
            "face_restore": { "from": "settings", "setting": "face_restore" }
          },
          "queue_based": true,
          "webhook_supported": true
        }
      },
      "settings_schema": {
        "type": "object",
        "properties": {
          "prompt": { "type": "string", "maxLength": 2000 },
          "base_media_id": { "type": "string", "format": "uuid" },
          "overlay_media_id": { "type": "string", "format": "uuid" },
          "blend_mode": { "type": "string", "enum": ["alpha", "seamless", "face_swap"], "default": "face_swap" },
          "alignment": {
            "type": "object",
            "properties": {
              "face_landmarks": { "type": "boolean", "default": true },
              "scale": { "type": "number", "minimum": 0.1, "maximum": 4, "default": 1 }
            }
          },
          "subject_media_id": { "type": "string", "format": "uuid" },
          "face_media_id": { "type": "string", "format": "uuid" },
          "face_restore": { "type": "boolean", "default": false },
          "output": {
            "type": "object",
            "properties": {
              "format": { "type": "string", "enum": ["jpeg", "png"], "default": "jpeg" },
              "quality": { "type": "integer", "minimum": 1, "maximum": 100, "default": 92 }
            }
          }
        },
        "oneOf": [
          { "required": ["base_media_id", "overlay_media_id"] },
          { "required": ["subject_media_id", "face_media_id"] }
        ],
        "additionalProperties": false
      }
    }
  }
}
```

Ключи `provider_overrides` фиксируют различия в интеграции: URL конечной точки, допустимые параметры, ограничения таймаута. Для операций,
требующих передачи локальных файлов, `media_parts` описывает, какие бинарные данные подставляются в запрос провайдера (например,
`image_edit` для Gemini получает `ingest_media` прямо из входящего запроса). Источник бинарных данных/URL теперь явный: `from: "media_object"`
используется для временных ссылок с TTL, а `from: "template_media"` — для постоянных шаблонов. При необходимости воркер временно регистрирует
шаблон в публичном хранилище, но исходный файл остаётся в каталоге `template_media`. Для Turbotext `field_map` указывает соответствие полей
формы (`url`, `url_image_target`, `content`, `face_restore` и т. д.) значениям из настроек слота и выбранному источнику медиа. Поле
`source_media_id` хранит идентификатор временной записи в `media_object`; при каждом сохранении слота или запуске тестовой загрузки бекенд
продлевает её через `POST /api/media/extend` (повторную регистрацию файла), чтобы `expires_at` гарантированно покрывал момент запуска ingest. Общие свойства
`settings_schema` описывают обязательные поля, которые должны быть валидированы на бэкенде при сохранении слота, а `required_settings`
фиксирует как общие требования, так и провайдер-специфичные обязательные поля и источник медиа.

#### Маппинг `Slot`

* `provider_id` — значение поля `providers[].id`.
* `operation_id` — одно из значений `operations` (на уровне провайдера).
* `settings_json` — JSON-объект, удовлетворяющий `settings_schema` соответствующей операции. На бэкенде хранится сериализованный JSON,
  где ссылки на долговечные шаблоны сохраняются как идентификаторы `template_media.id`, а краткоживущие файлы и предпросмотры продолжают
  ссылаться на `media_object.id`. Операции явно указывают требуемый источник в `provider_overrides`/`media_parts`.

Пример значения `settings_json` для слота Gemini c операцией `identity_transfer`:

```json
{
  "prompt": "Сменить фон на корпоративный стиль",
  "base_media_id": "b7a09f84-7560-4a7b-9303-2b41a6d359f3",
  "overlay_media_id": "3ad89908-0df1-4f1e-b3e9-586eea730d21",
  "blend_mode": "face_swap",
  "alignment": { "face_landmarks": true, "scale": 1.1 },
  "output": { "format": "jpeg", "quality": 90 }
}
```

Пример значения `settings_json` для слота Gemini c операцией `image_edit` (исходное фото приходит во входящем ingest‑POST, в конфигурации остаются только параметры генерации):

```json
{
  "prompt": "Осветлить лицо и пригладить фон",
  "guidance_scale": 6.5,
  "output": { "format": "png", "quality": 95 }
}
```

На UI параметры собираются на основании `needs` (промпт, первое/второе изображение) и валидируются против схемы операции. При сохранении:

1. Шаблонные изображения (стили, лица и т. д.) уходят в `POST /api/template-media/register`; ответ содержит `template_media_id`,
   который сохраняется в `slot_template_binding` и затем подставляется в `settings_json`.
2. Временные файлы (тестовое фото, предпросмотр, любые `source_media_id`) загружаются через `POST /api/media/register`; UI
   получает `media_object.id` и использует его только как временный идентификатор.
3. Перед сохранением слота бекенд вызывает `POST /api/media/extend` (повторную регистрацию файла) для каждого `media_object.id`, чтобы продлить `expires_at`
   в пределах `media.max_manual_ttl_sec`, затем формирует объект по схеме и сериализует JSON в `Slot.settings_json`.
4. При старте ingest воркер ещё раз продлевает временные `media_object` (включая `source_media_id`), чтобы гарантировать
   доступность файла на время обработки и до получения результата.

## Стек
*   **Бэкенд:** FastAPI
*   **База данных:** PostgreSQL
*  **Очередь задач:** MVP — in-process asyncio.Queue; при росте — очередь на PostgreSQL через таблицу Job и SELECT … FOR UPDATE SKIP LOCKED (воркеры)
*   **Фронтенд:** HTMX, VanillaJS

# API Спецификация
## Внутренний API (для Frontend)
API для взаимодействия с веб-интерфейсом построен на принципах REST. Все защищённые эндпоинты требуют передачи заголовка `Authorization: Bearer <JWT>`; токен действует 60 минут с момента выдачи и должен быть обновлён повторным вызовом `/api/login` после истечения срока. Ответы об ошибках имеют единый формат:

```json
{
  "error": {
    "code": "<machine_readable_code>",
    "message": "Человекочитаемое описание проблемы",
    "details": { "field": "optional context" }
  }
}
```

Общие коды состояния: `400` — ошибка валидации, `401` — неавторизовано/истёкший токен, `403` — недостаточно прав, `404` — ресурс не найден, `409` — конфликт (например, слот уже существует), `422` — семантическая ошибка тела запроса, `500` — внутренняя ошибка сервера.

### Аутентификация
JWT, выдаваемый платформой, содержит claim `permissions` с массивом прав из `User.permissions`. Каждый защищённый эндпоинт подключает зависимость `RequirePermission` и сравнивает требуемое право с этим массивом, возвращая `403`, если право отсутствует.
**`POST /api/login`**

* **Назначение:** Вход пользователя и получение JWT.
* **Аутентификация:** не требуется.
* **Тело запроса:**
  ```json
  {
    "username": "admin",
    "password": "secret"
  }
  ```
* **Успешный ответ (`200 OK`):**
  ```json
  {
    "access_token": "<jwt>",
    "token_type": "bearer",
    "expires_in_sec": 3600
  }
  ```
* **Ошибки:** `400` (некорректное тело), `401` (неверные учётные данные), `429` (слишком частые попытки).

#### Статические пользователи и секреты
- В веб-интерфейсе доступны только две учётные записи: `serg` и `igor`. Их случайные пароли генерируются в процессе деплоя и
  сохраняются в файле `secrets/runtime_credentials.json`, который добавлен в `.gitignore` и не версионируется.
- Наборы прав для этих пользователей задаются в `User.permissions` (см. раздел «Права доступа и роли»), попадают в JWT claim `permissions` и проверяются зависимостью `RequirePermission` для каждого защищённого эндпоинта.
- JWT выдаётся только для указанных предустановленных пользователей; сценарии регистрации, восстановления доступа и смены пароля
  намеренно отсутствуют.
- Ingest-эндпоинты дополнительно защищены отдельным случайным паролем, который хранится в базе (таблица `app_settings`, поля `dslr_password_hash`/`dslr_password_salt`) и передаётся в теле POST-запроса вместе с фотографией. Plaintext хранится только на стороне клиента DSLR.
- Ротация ingest-пароля выполняется через интерфейс «Настройки» (`PUT /api/settings`), который перехеширует значение и обновляет метаданные (`updated_at`, `updated_by`); перезапуск сервиса или ручное редактирование файлов не требуется.

### Провайдеры
**`GET /api/providers`**

* **Назначение:** Получить короткий справочник провайдеров (идентификатор и отображаемое имя) для заполнения выпадающих списков UI; расширенные данные о провайдерах и операциях UI читает из `configs/providers.json`, опубликованного как статический ресурс.
* **Аутентификация:** требуется `Authorization: Bearer <JWT>`; необходимо право `slots:read` (см. раздел «Права доступа и роли»).
* **Параметры запроса:** отсутствуют; пагинация не применяется из-за ограниченного числа записей.
* **Успешный ответ (`200 OK`):**
  ```json
  {
    "providers": [
      { "id": "gemini", "name": "Gemini" },
      { "id": "turbotext", "name": "TurboText" }
    ]
  }
  ```
* **Ошибки:** стандартные (`401`, `403`, `500`).

### Слоты
**`GET /api/slots`**

* **Назначение:** Получить список всех 15 преднастроенных слотов платформы (глобальный пул) и их актуальные настройки.
* **Аутентификация:** требуется `Authorization: Bearer <JWT>`; необходимо право `slots:read`.
* **Пагинация:** не применяется (возвращается ровно 15 записей); фронтенд может выполнять клиентскую пагинацию/фильтрацию.
* **Фильтрация:** query-параметры `provider_id`, `operation_id`, `search` опциональны и используются для сокращения набора возвращаемых слотов.
* **Успешный ответ (`200 OK`):**
  ```json
  {
    "data": [
      {
        "id": "slot-001",
        "name": "Fashion Studio",
        "provider_id": "gemini",
        "operation_id": "style_transfer",
        "settings_json": {
          "prompt": "Передай стиль глянцевого журнала",
          "reference_media_id": "0a403f97-312f-4fc5-9f01-7de121c9a9d7",
          "output": {
            "format": "jpeg",
            "max_side_px": 2048
          }
        },
        "last_reset_at": "2024-04-22T09:15:00Z",
        "created_at": "2024-03-10T08:00:00Z",
        "updated_at": "2024-04-22T11:30:00Z"
      }
    ],
    "meta": {
      "total": 15
    }
  }
  ```
* **Ошибки:** `400` (некорректные параметры фильтрации), стандартные ошибки авторизации/доступа.
* **Примечание:** создание и удаление слотов недоступны — пользователь редактирует только предзагруженные идентификаторы. Ингест-ссылка вычисляется по шаблону `<BASE_URL>/ingest/{slot_id}` и не хранится как отдельное поле таблицы. Поля `*_media_id`, возвращаемые в `settings_json`, для шаблонов содержат идентификаторы `template_media`; временные вложения продолжают использовать `media_object.id`.

**`GET /api/slots/{slot_id}`**

* **Назначение:** Получить данные конкретного слота.
* **Аутентификация:** требуется `Authorization: Bearer <JWT>`; необходимо право `slots:read`.
* **Параметры:** `slot_id` (path).
* **Успешный ответ (`200 OK`):**
  ```json
  {
    "id": "slot-001",
    "name": "Fashion Studio",
    "provider_id": "gemini",
    "operation_id": "style_transfer",
    "settings_json": {
      "prompt": "Передай стиль глянцевого журнала",
      "reference_media_id": "0a403f97-312f-4fc5-9f01-7de121c9a9d7",
      "output": {
        "format": "jpeg",
        "max_side_px": 2048
      }
    },
    "last_reset_at": "2024-04-22T09:15:00Z",
    "created_at": "2024-03-10T08:00:00Z",
    "updated_at": "2024-04-22T11:30:00Z"
  }
  ```
* **Ошибки:** `404` (слот не найден), стандартные ошибки авторизации.

**`PUT /api/slots/{slot_id}`**

* **Назначение:** Обновить настройки одного из статических слотов.
* **Аутентификация:** требуется `Authorization: Bearer <JWT>`; необходимо право `slots:write`.
* **Тело запроса:** должно содержать актуальную метку версии слота — либо полем `updated_at` (скопированным из последнего `GET`), либо сервер принимает аналогичное значение в заголовке `If-Match`. При использовании заголовка `If-Match` поле `updated_at` в теле можно опустить. При отсутствии метки запрос отклоняется с `400`.
  ```json
  {
    "name": "Fashion Studio",
    "provider_id": "gemini",
    "operation_id": "identity_transfer",
    "settings_json": {
      "prompt": "Скомбинировать исходник со стилевым",
      "base_media_id": "b7a09f84-7560-4a7b-9303-2b41a6d359f3",
      "overlay_media_id": "3ad89908-0df1-4f1e-b3e9-586eea730d21",
      "alignment": {"face_landmarks": true},
      "output": {"format": "jpeg", "quality": 92}
    },
    "updated_at": "2024-04-22T11:30:00Z"
  }
  ```
* **Успешный ответ (`200 OK`):**
  ```json
  {
    "id": "slot-001",
    "updated_at": "2024-04-22T11:45:12Z"
  }
  ```
* **Ошибки:** `400`/`422` (ошибка валидации), `404` (слот не найден), `409` (слот занят фоновой операцией или версия не совпала), стандартные ошибки авторизации. Для конфликта версий сервер сравнивает переданную метку (`updated_at` из тела или заголовок `If-Match`) с текущей сохранённой и, если они различаются, возвращает `409` с телом `{"error": "conflict", "message": "Slot slot-001 has newer version"}`.
* **Пример конфликта версий (`409 Conflict`):**
  ```http
  PUT /api/slots/slot-001 HTTP/1.1
  Authorization: Bearer <JWT>
  Content-Type: application/json
  If-Match: "2024-04-22T11:30:00Z"

  {
    "name": "Fashion Studio",
    "provider_id": "gemini",
    "operation_id": "identity_transfer",
    "settings_json": {
      "prompt": "Скомбинировать исходник со стилевым",
      "base_media_id": "b7a09f84-7560-4a7b-9303-2b41a6d359f3",
      "overlay_media_id": "3ad89908-0df1-4f1e-b3e9-586eea730d21",
      "alignment": {"face_landmarks": true},
      "output": {"format": "jpeg", "quality": 92}
    }
  }
  ```
  ```json
  {
    "error": "conflict",
    "message": "Slot slot-001 has newer version",
    "current_updated_at": "2024-04-22T11:45:12Z"
  }
  ```

**`POST /api/slots/{slot_id}/reset_stats`**

* **Назначение:** Обнулить статистику выбранного слота.
* **Аутентификация:** требуется `Authorization: Bearer <JWT>`; необходимо право `slots:write`.
* **Тело запроса:** отсутствует (передавайте пустой JSON `{}` для совместимости).
* **Успешный ответ:** `204 No Content`.
* **Ошибки:** `404` (слот не найден), `409` (выполняется сброс), стандартные ошибки авторизации.

### Шаблонные медиа

**`POST /api/template-media/register`**

* **Назначение:** Загрузить файл-шаблон и привязать его к конкретному слоту/полю.
* **Аутентификация:** требуется `Authorization: Bearer <JWT>`; необходимо право `slots:write`.
* **Тело запроса:** `multipart/form-data` с полями `file` (бинарный файл JPEG/PNG/WEBP/HEIC/HEIF), `slot_id` (TEXT), `setting_key`
  (TEXT, имя поля в `settings_json`) и опциональным `label` (TEXT). Чтобы заменить существующий шаблон, добавьте флаг `replace=true` —
  сервер удалит предыдущую привязку.
* **Успешный ответ (`201 Created`):**
  ```json
  {
    "id": "4d4b522f-ec60-4d61-902c-3a0c5c6dc1f3",
    "slot_id": "slot-001",
    "setting_key": "style_media_id",
    "label": "Glamour reference",
    "mime": "image/jpeg",
    "size_bytes": 523891,
    "created_at": "2024-05-20T10:12:44Z"
  }
  ```
  Эндпоинт создаёт запись в `template_media`, обновляет `slot_template_binding` и возвращает идентификатор, который UI подставляет
  в `Slot.settings_json`.
* **Ошибки:** `400` (некорректный формат/размер файла), `401`/`403` (авторизация), `404` (слот не найден), `409` (конфликт привязок
  без `replace=true`).

**`DELETE /api/template-media/{id}`**

* **Назначение:** Удалить шаблон и отвязать его от слота по инициативе пользователя (кнопка «Убрать»).
* **Аутентификация:** требуется `Authorization: Bearer <JWT>`; необходимо право `slots:write`.
* **Параметры:** Path `id`; Query `slot_id` и `setting_key` — подтверждают, что удаляется верная привязка. Опционально `force=true`
  — удаляет файл даже если он закреплён за несколькими слотами.
* **Успешный ответ:** `204 No Content` (если файл больше не используется — запись и файл из `MEDIA_ROOT/templates` удаляются; при
  других привязках он остаётся, но связь с указанным слотом стирается).
* **Ошибки:** `404` (шаблон или привязка не найдены), `409` (попытка удалить используемый несколькими слотами без `force`).

### Статистика
**`GET /api/stats/{slot_id}`**

* **Назначение:** Получить детальную статистику по слоту.
* **Аутентификация:** требуется `Authorization: Bearer <JWT>`; необходимо право `stats:read`.
* **Параметры:**
  * Path: `slot_id`.
  * Query: `from` и `to` (ISO8601, ограничение диапазона — не более 31 дня), `group_by` (`hour`, `day`, `week`, дефолт `day`).
* **Сортировка:** группировки возвращаются в хронологическом порядке по возрастанию.
* **Пагинация:** не применяется (результат ограничен диапазоном дат).
* **Успешный ответ (`200 OK`):**
  ```json
  {
    "slot_id": "slot-001",
    "range": { "from": "2024-04-01", "to": "2024-04-07", "group_by": "day" },
    "metrics": [
      { "period_start": "2024-04-01", "success": 12, "errors": 1, "avg_response_ms": 2100, "cost": 4.35 }
    ]
  }
  ```
* **Ошибки:** `400` (некорректный диапазон), `404` (слот не найден), стандартные ошибки авторизации.

**`GET /api/stats/global`**

* **Назначение:** Получить агрегированную статистику по всем слотам пользователя.
* **Аутентификация:** требуется `Authorization: Bearer <JWT>`; необходимо право `stats:read`.
* **Параметры:**
  * Query: `from`/`to` (ISO8601, максимум 90 дней), `group_by` (`day`, `week`, `month`, дефолт `week`).
  * Пагинация списка записей: `page` (>=1, дефолт 1), `page_size` (1–50, дефолт 10).
  * Сортировка: `sort_by` (`period_start`, `success`, `errors`, `cost`) и `sort_order` (`asc`/`desc`, дефолт `desc`).
  * Фильтры: `provider_id`, `slot_id` (опционально ограничивают агрегаты).
* **Успешный ответ (`200 OK`):**
  ```json
  {
    "data": [
      {
        "period_start": "2024-04-01",
        "period_end": "2024-04-07",
        "success": 84,
        "errors": 6,
        "avg_response_ms": 1980,
        "cost": 31.8
      }
    ],
    "meta": {
      "page": 1,
      "page_size": 10,
      "total": 12
    }
  }
  ```
* **Ошибки:** `400` (некорректные параметры фильтров/пагинации), стандартные ошибки авторизации.


## Внешний API: Ingest (DSLR Remote Pro)
Этот эндпоинт предназначен для приёма `POST` запросов от программы DSLR Remote Pro. Будет сгенерировано 15 статических коротких ingest-ссылок, которые можно привязывать к слотам.

### POST /ingest/{slotId}
- **Метод и путь:** `POST /ingest/{slotId}`.
- **Назначение:** принять фотографию и метаданные от DSLR Remote Pro для дальнейшей обработки в соответствии с конфигурацией слота.
- **Авторизация:** глобальный пароль, передаваемый в теле (поле `password`). Сравнивается с хешем, сохранённым в `app_settings` (`dslr_password_hash`). Одно и то же значение используется для всех ingest-слотов.
- **slotId:** статический идентификатор ingest-слота (предзаданные значения `slot-001` … `slot-015`).

#### Тело запроса
- **Тип:** `multipart/form-data`.
- **Обязательные поля:**
  - `password` — строка. Проверяется на совпадение с глобальным Argon2-хешем из `app_settings`; требуется непустое значение.
  - `fileToUpload` — бинарный файл изображения. Поддерживаемые форматы: JPEG, PNG, WEBP, HEIC, HEIF. Лимит размера конфигурируемый (значение по умолчанию ≤ 25 МБ). Дополнительные EXIF/метаданные не изменяются и сохраняются в исходном виде.
- **Опциональные текстовые поля:** `time`, `user_id`, `id`, `profile`, `status`, `hash`, `name`, `model`, `version` и другие возможные поля DSLR Remote Pro. Все они обрабатываются как best-effort метаданные: не валидируются, сохраняются как есть (например, в metadata задачи или логах) и не влияют на принятие решения.
- **Неизвестные поля:** любые дополнительные ключи допустимы, система не ограничивает их список и не пытается валидировать содержимое.
- **Несколько файлов:** если в форме передано несколько файлов, сервер выбирает первый файл с поддерживаемым MIME-типом; остальные игнорируются, но факт их наличия фиксируется в логах для диагностики.

#### Ответы
- **200 OK** — успешная обработка. Тело содержит бинарное изображение (формат зависит от результата провайдера: JPEG/PNG/WEBP/…); заголовки: `Content-Type` (соответствует формату ответа), `Content-Length`, `Cache-Control: no-store`. Ответ возвращается синхронно, время ожидания ≤ 48–50 с. При превышении лимита ожидания клиент получит 504.
- **Ошибки:**
  - `400 Bad Request` — отсутствует обязательное поле (`password` или `fileToUpload`), передан неподдерживаемый тип данных в поле формы или нарушен формат `multipart/form-data`.
  - `401 Unauthorized` — пароль не совпал с глобальным ingest-паролем.
  - `413 Payload Too Large` — размер файла превысил установленный лимит.
  - `415 Unsupported Media Type` — MIME-тип файла вне списка поддерживаемых.
  - `429 Too Many Requests` — очередь задач для данного слота достигла лимита параллельных обработок.
  - `500 Internal Server Error` — внутренняя ошибка платформы.
  - `503 Service Unavailable` — адаптер провайдера недоступен или вернул временную ошибку.
  - `504 Gateway Timeout` — обработка не завершена в пределах синхронного окна ожидания.

**Структура ошибки:**
```json
{
  "error": {
    "code": "<snake_case>",
    "message": "<читаемое описание>",
    "details": { }
  }
}
```
`Content-Type: application/json`. Поле `code` стабильно и может использоваться клиентом для обработки ошибок; объект `details` опционален и при необходимости содержит дополнительную диагностику.

#### Ограничения и валидация
- Лимит размера файла конфигурируется (по умолчанию ≤ 25 МБ). Превышение приводит к 413.
- Поддерживаемые MIME: `image/jpeg`, `image/png`, `image/webp`, `image/heic`, `image/heif`. Остальные значения вызывают 415.
- Синхронное ожидание результата ограничено ~48–50 с; превышение приводит к 504 и остановке дальнейшей выдачи результата по текущему запросу.
- На слот действует ограничение числа одновременно обрабатываемых задач; переполнение очереди возвращает 429.
- Неизвестные текстовые поля и дополнительные файлы сохраняются/логируются без модификаций и не влияют на валидацию.

#### Пример сырых полей от DSLR Remote Pro (для справки)
В пользовательском запросе должна быть передана исходная фотография, глобальный пароль и, опционально, некоторые другие поля. Пример пользовательского POST запроса для DSLR программы:

```json
{
  "timestamp": "2025-09-18T17:45:12.439171+00:00",
  "client": {
    "host": "127.0.0.1",
    "port": 1417
  },
  "method": "POST",
  "url": "http://localhost:8000/echo?session=42",
  "path": "/echo",
  "query_params": {
    "session": "42"
  },
  "headers": {
    "host": "localhost:8000",
    "content-type": "multipart/form-data; boundary=------------090306000104030805010400",
    "content-length": "53205",
    "expect": "100-continue"
  },
  "cookies": {},
  "content_type": "multipart/form-data; boundary=------------090306000104030805010400",
  "is_multipart": true,
  "form_text_fields": {
    "time": "1758217512",
    "user_id": "Acer",
    "id": "CY04N068111304S2L_00000001.",
    "profile": "C:\\Users\\Acer\\Documents\\PhotoboothImages\\setup_Serg.xml",
    "status": "C:\\Users\\Acer\\Documents\\PhotoboothImages\\screenSerg\\preview.jpg",
    "hash": "7b6c683e1d3fd29c8701791c54e3c12a236f5a5b",
    "name": "DESKTOP-K968T3F",
    "model": "Windows",
    "version": "3.30.2",
    "password": "123456"
  },
  "form_files": [
    {
      "field": "fileToUpload",
      "original_filename": "IMG_0003.JPG",
      "saved_as": "\\tmp\\fastapi_echo\\uploads\\20250918T174512Z_e6bf1d6c98c843d6aa4948d07f251c17.JPG",
      "content_type": "image/jpeg",
      "size_bytes": 51977,
      "is_image_jpeg": true
    }
  ]
}
```
Ответ при успехе: бинарный image/jpeg|png (синхронно, short-poll ≤ 50 c).
В ответе на этот запрос наш сервер должен отправить фотографию, обработанную AI моделью.

## API Turbotext
для работы с моделью Турботекст будут использоваться следующие методы:
- Микс-фото
- Замена объекта
- Замена лица
Описание api находится тут https://www.turbotext.ru/photo_ai/docs/info#section-2
Все запросы отправляются на url: https://www.turbotext.ru/api_ai

### Авторизация
Идентификацию пользователя организуйте посредством Bearer Token,
Пример CURL, данные с Headers запроса:
```http
Authorization: Bearer {APIKEY}
Content-Type: application/x-www-form-urlencoded
```

### Webhook

Если вы хотите запустить серию генераций вам необходимо использовать асинхронный метод генерации, для этого создаем webhook который сможет принимать и обрабатывать результаты генераций.

При обычном методе генерации, вы создаете очередь, затем с помощью номера очереди получаете результат генерации,

в асинхронном методе геннерации, вы создаете очередь добавив в пост данные:

`webhook=https://mysite.com/webhook_example.php`

Ответ на запрос будет такой:

`{"success":true,"asyncid":N} `, где N номер очереди, при получении ответа вы получите параметр asyncid с таким же значением.

Нейро-сервер после обработки вашего запроса, отправит вам на адрес который вы указали в параметре webhook POST данные с результатом генерации,
Формат данных точно такой же как и при получении вторым запросом.

Вы получите результат генерации на ваш WEBHOOK URL в формате JSON

пример получения результата на php:
```php
$result=file_get_contents('php://input');//входящий JSON результат`
$result_array=json_decode($result,1);//Результаты в массиве
```

### Метод Микс фото
Запрос на создании очереди
```http
/api_ai/mix_images HTTP/1.1
Host: turbotext.ru
Authorization: Bearer {APIKEY}
Content-Type: application/x-www-form-urlencoded
Content-Length: 0
```
do:create_queue
content - описание для усиления эффекта
url_image_target - фото на урл которое нужно обработать
url - фото на урл откуда используем стиль 

Ответ с данными очереди в формате JSON:
`{"success":true,"queueid":{QUEUEID}}`
Здесь `{QUEUEID}` - Номер нашей очереди, далее обращаемся за получением результата использую этот массив данных.
Теперь делаем запрос на получение результата:
```http
/api_ai/mix_images HTTP/1.1
Host: turbotext.ru
Authorization: Bearer {APIKEY}
Content-Type: application/x-www-form-urlencoded
Content-Length: 0
do:get_result
queueid:{QUEUEID} 
```

## API Gemini
### Ссылки на документацию 
Image generation: https://ai.google.dev/gemini-api/docs/image-generation#image_generation_text-to-image
Image understanding: https://ai.google.dev/gemini-api/docs/image-understanding
Files API guide: https://ai.google.dev/gemini-api/docs/files
File prompting strategies: https://ai.google.dev/gemini-api/docs/files#prompt-guide
### Описание API 
Image generation with Gemini (aka Nano Banana)
Multi-Image to Image (Composition & Style Transfer): Use multiple input images to compose a new scene or transfer the style from one image to another.

#### Passing images to Gemini
You can provide images as input to Gemini using two methods:
 1.   Passing inline image data: Ideal for smaller files (total request size less than 20MB, including prompts). 
 2.   Uploading images using the File API: Recommended for larger files or for reusing images across multiple requests. 

##### Passing inline image data
You can pass inline image data in the request to `generateContent`. You can provide image data as Base64 encoded strings or by reading local files directly (depending on the language). The following example shows how to read an image from a local file and pass it to `generateContent` API for processing.
Passing inline image data example:
```python
  from google.genai import types

  with open('path/to/small-sample.jpg', 'rb') as f:
      image_bytes = f.read()

  response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
      types.Part.from_bytes(
        data=image_bytes,
        mime_type='image/jpeg',
      ),
      'Caption this image.'
    ]
  )

  print(response.text)
```
You can also fetch an image from a URL, convert it to bytes, and pass it to `generateContent` as shown in the following examples:
```python
from google import genai
from google.genai import types

import requests

image_path = "https://goo.gle/instrument-img"
image_bytes = requests.get(image_path).content
image = types.Part.from_bytes(
  data=image_bytes, mime_type="image/jpeg"
)

client = genai.Client()

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=["What is this image?", image],
)

print(response.text)
```

##### Uploading images using the File API
For large files or **to be able to use the same image file repeatedly, use the Files API**. 
The Gemini family of artificial intelligence (AI) models is built to handle various types of input data, including text, images, and audio. Since these models can handle more than one type or mode of data, the Gemini models are called multimodal models or explained as having multimodal capabilities.
This guide shows you how to work with media files using the Files API. The basic operations are the same for audio files, images, videos, documents, and other supported file types.

###### Upload a file
 Always use the Files API when the total request size (including the files, text prompt, system instructions, etc.) is larger than 20 MB.
The following code uploads a file and then uses the file in a call to `generateContent`.

```python 
from google import genai
client = genai.Client()
myfile = client.files.upload(file="path/to/sample.mp3")
response = client.models.generate_content(
    model="gemini-2.5-flash", contents=["Describe this audio clip", myfile]
)
print(response.text)
```
###### Get metadata for a file
You can verify that the API successfully stored the uploaded file and get its metadata by calling `files.get`.
```python
myfile = client.files.upload(file='path/to/sample.mp3')
file_name = myfile.name
myfile = client.files.get(name=file_name)
print(myfile)

```
###### List uploaded files
You can upload multiple files using the Files API. The following code gets a list of all the files uploaded:
```python
print('My files:')
for f in client.files.list():
    print(' ', f.name)
```
###### Delete uploaded files
Files are automatically deleted after 48 hours. You can also manually delete an uploaded file:
```python
myfile = client.files.upload(file='path/to/sample.mp3')
client.files.delete(name=myfile.name)
```

###### Usage info
You can use the Files API to upload and interact with media files. The Files API lets you store up to 20 GB of files per project, with a per-file maximum size of 2 GB. Files are stored for 48 hours. During that time, you can use the API to get metadata about the files, but you can't download the files. The Files API is available at no cost in all regions where the Gemini API is available.

#### Prompting with multiple images. 

You can provide multiple images in a single prompt by including multiple image Part objects in the contents array. These can be a mix of inline data (local files or URLs) and File API references.
```python
from google import genai
from google.genai import types

client = genai.Client()

# Upload the first image
image1_path = "path/to/image1.jpg"
uploaded_file = client.files.upload(file=image1_path)

# Prepare the second image as inline data
image2_path = "path/to/image2.png"
with open(image2_path, 'rb') as f:
    img2_bytes = f.read()

# Create the prompt with text and multiple images
response = client.models.generate_content(

    model="gemini-2.5-flash",
    contents=[
        "What is different between these two images?",
        uploaded_file,  # Use the uploaded file reference
        types.Part.from_bytes(
            data=img2_bytes,
            mime_type='image/png'
        )
    ]
)
print(response.text)
```
##### Style transfer
Example of Prompt template
```
Transform the provided photograph of [subject] into the artistic style of [artist/art style]. Preserve the original composition but render it with [description of stylistic elements].
```
Example of code 
```python
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

client = genai.Client()

# Base image prompt: "A photorealistic, high-resolution photograph of a busy city street in New York at night, with bright neon signs, yellow taxis, and tall skyscrapers."
city_image = Image.open('/path/to/your/city.png')
text_input = """Transform the provided photograph of a modern city street at night into the artistic style of Vincent van Gogh's 'Starry Night'. Preserve the original composition of buildings and cars, but render all elements with swirling, impasto brushstrokes and a dramatic palette of deep blues and bright yellows."""

# Generate an image from a text prompt
response = client.models.generate_content(
    model="gemini-2.5-flash-image-preview",
    contents=[city_image, text_input],
)

image_parts = [
    part.inline_data.data
    for part in response.candidates[0].content.parts
    if part.inline_data
]

if image_parts:
    image = Image.open(BytesIO(image_parts[0]))
    image.save('city_style_transfer.png')
    image.show()
```

##### Combining multiple images
Provide multiple images as context to create a new, composite scene. This is perfect for product mockups or creative collages.
Example of prompt:
```prompt
"Create a professional e-commerce fashion photo. Take the blue floral dress
from the first image and let the woman from the second image wear it.
Generate a realistic, full-body shot of the woman wearing the dress, with
the lighting and shadows adjusted to match the outdoor environment.
Ensure the persons's face and features remain completely unchanged. "
```
Example of code:
```python
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

client = genai.Client()

# Base image prompts:
# 1. Dress: "A professionally shot photo of a blue floral summer dress on a plain white background, ghost mannequin style."
# 2. Model: "Full-body shot of a woman with her hair in a bun, smiling, standing against a neutral grey studio background."
dress_image = Image.open('/path/to/your/dress.png')
model_image = Image.open('/path/to/your/model.png')

text_input = """Create a professional e-commerce fashion photo. Take the blue floral dress from the first image and let the woman from the second image wear it. Generate a realistic, full-body shot of the woman wearing the dress, with the lighting and shadows adjusted to match the outdoor environment. Ensure the persons's face and features remain completely unchanged. """

# Generate an image from a text prompt
response = client.models.generate_content(
    model="gemini-2.5-flash-image-preview",
    contents=[dress_image, model_image, text_input],
)

image_parts = [
    part.inline_data.data
    for part in response.candidates[0].content.parts
    if part.inline_data
]

if image_parts:
    image = Image.open(BytesIO(image_parts[0]))
    image.save('fashion_ecommerce_shot.png')
    image.show()
```
###### High-fidelity detail preservation
To ensure critical details (like a face or logo) are preserved during an edit, describe them in great detail along with your edit request.
Example prompt:
```template
Using the provided images, place [element from image 2] onto [element from
image 1]. Ensure that the features of [element from image 1] remain
completely unchanged. The added element should [description of how the
element should integrate].
```

#### Best Practices
To elevate your results from good to great, incorporate these professional strategies into your workflow.

   * **Be Hyper-Specific:** The more detail you provide, the more control you have. Instead of "fantasy armor," describe it: "ornate elven plate armor, etched with silver leaf patterns, with a high collar and pauldrons shaped like falcon wings."
    * **Provide Context and Intent:** Explain the purpose of the image. The model's understanding of context will influence the final output. For example, "Create a logo for a high-end, minimalist skincare brand" will yield better results than just "Create a logo."
    * **Use Step-by-Step Instructions:** For complex scenes with many elements, break your prompt into steps. "First, create a background of a serene, misty forest at dawn. Then, in the foreground, add a moss-covered ancient stone altar. Finally, place a single, glowing sword on top of the altar."
    * **Use "Semantic Negative Prompts":** Instead of saying "no cars," describe the desired scene positively: "an empty, deserted street with no signs of traffic."
    * **Control the Camera:** Use photographic and cinematic language to control the composition. Terms like wide-angle shot, macro shot,

#### Supportet image formats
Gemini supports the following image format MIME types:

 *    PNG - image/png
 *    JPEG - image/jpeg
 *    WEBP - image/webp
 *    HEIC - image/heic
 *    HEIF - image/heif

#### Limitations and key technical information
##### File limit 
Gemini 2.5 Pro/Flash, 2.0 Flash, 1.5 Pro, and 1.5 Flash support a maximum of 3,600 image files per request.

##### Token calculation
Gemini 2.5 Flash/Pro: 258 tokens if both dimensions <= 384 pixels. Larger images are tiled into 768x768 pixel tiles, each costing 258 tokens.
A rough formula for calculating the number of tiles is as follows:
 *   Calculate the crop unit size which is roughly: floor(min(width, height) / 1.5).
 *   Divide each dimension by the crop unit size and multiply together to get the number of tiles.

For example, for an image of dimensions 960x540 would have a crop unit size of 360. Divide each dimension by 360 and the number of tile is 3 * 2 = 6.
##### Tips and best practices
When using a single image with text, place the text prompt after the image part in the `contents` array.


# Frontend 
Фронтэнд состоит из:
1. Страница авторизации. 
2. Главная страница.
3. Страницы-вкладки (слоты).
4. Страница статистики.
5. Страница настроек.
## Описание web страниц фронтэнда 

### Страница авторизации
Страница авторизации на сайт выполнена согласно образцу: 
Полный шаблон см. в файле [`frontend-examples/login-page.html`](./frontend-examples/login-page.html).

### Главная страница 
 Главная страница содержит список слотов для AI обработки фото. 
  Под слотом подразумевается Страница-вкладка, дающая возможность сохранить в БД набор пользовательских настроек, касающихся AI обработки фотографий. 
 Визуально слот из себя представляет  кликабельный текст с пользовательским названием, взятым из соответствующей Стрианицы-вкладки. Клик по слоту ведет на соответствующую Страницу-вкладку. В одной строке рядом со слотом есть поле, в котором указана ingest-ссылка и кнопка "Копировать", чтобы скопировать ссылку. Все ingest-ссылки статичные, содержат окончание с коротким именем модели и номером слота.  Каждому слоту соответствует уникальная ingest-ссылка (входящий URL) для загрузки фото на обработку. ingest-ссылка предоставляется клиенту для загрузки фотографии в соответствующий слот для последующей обработки. ingest-ссылка описана в разделе [API DSLR Remote Pro](#dslr-post). Та же самая ingest-ссылка дублируется в интерфейсе слота - на его Странице-вкладке перед кнопкой "Сохранить1".  
 Справа вверху на главной странице есть кнопки в виде иконок:  "Статистика", "Настройки", "Выйти".

### Страница статистики
Содержит список по каждому слоту:
 Имя слота | маленькая иконка Шаблонного изображения №2 (если такое есть в слоте) | сколько  AI обработок совершено через этот слот с момента последнего сброса | количество ingest-запросов | p95-время ответа | процент ошибок | цена последней AI обработки | общая потраченная сумма с момента последнего сброса | дата последнего сброса статистики | кнопка "Сброс статисики" | сколько глобально обработок совершено за все время.
Визуально рамки таблицы рисовать не надо.

### Страница настроек
Содержит:
1. Поле для ввода пароля, который будет передаваться приложению от DSLR Remote Pro в теле запроса. 
2. Поля для ввода API ключей от AI моделей.
3. Кнопка "Очистить мультимедиа кеш" по нажатию удаляет только временные объекты (`media_object`, результаты с TTL 3 дня); файлы
   из `template_media` и их привязки не затрагиваются.
4. Кнопка "Сохранить".

### Страницы-вкладки
Каждая страница-вкладка представляет интерфейс управления конкретным слотом и работает с тем же набором полей, что и запись в таблице `Slot`. Для MVP необходимо поддержать 15 страниц-вкладок — по одной на каждый слот из глобального пула, созданного миграцией и сопоставленного фиксированной ingest-ссылке (`slot-001` … `slot-015`). Дополнительные страницы не появляются и не удаляются: как и слоты в БД, они переиспользуются при повторной настройке.
На странице-вкладке сверху отображается название AI-модели для выбранного слота и поле ввода «Название». Значение этого поля становится кликабельным именем слота на главной странице и ведёт обратно на соответствующую страницу-вкладку.
Форма на странице-вкладке собирает данные для AI-обработки: название задачи, текстовый промпт, опциональный шаблон (изображение №2) и опционально тестовое фото для локальной проверки. Все пользовательские данные, кроме тестового фото, сохраняются в слоте в базе данных. Интерфейс и внешний вид всех страниц-вкладок идентичны, отличаются только содержимым полей.
Перед кнопкой «Сохранить» отображается привязанная ingest-ссылка — та же, что создаётся миграциями и видна на главной странице для пользовательского [POST-запроса](#dslr-post).
#### Спецификация Страницы владки
Эта спецификация не обязательна, а лишь отображает примерный сценарий страницы.  Больше внимания следует уделить [Примеру оформления Страницы-вкладки](#slot-exmpl)
##### Что происходит на странице
1. Пользователь вводит Название и Промпт к ИИ.
2. Тумблерами включает загрузку:
 * второго изображения (шаблон стиля/замены лица/фона),
 * тестового фото (для локальной проверки).
3. Для шаблонного изображения (№2) — drag&drop/клик по зоне с валидацией JPG/PNG: успешная загрузка вызывает `POST /api/template-media/register`,
   сохраняет `template_media_id` и обновляет превью; кнопка «Убрать» триггерит `DELETE /api/template-media/{id}` и очищает привязку.
4. Для тестового фото и прочих временных вложений — загрузка через `POST /api/media/register`, хранение `media_object.id`, превью и очистка по TTL.
5. Скрытые поля `*_status` помечают, загружен ли файл (`present/removed`).
6. **Тест1**: если загружено тест-фото — вспышка-анимация формы и тост «успех», иначе тост-ошибка.
7. **Сохранить1**: визуальный «блик» формы; реального POST нет (submit отключён).

##### Модули и логика (верхний уровень) 

* Форма `#upload-form`
Хранит все поля. Submit заблокирован (`onsubmit="return false"`), кнопка «Сохранить1» — `type="button"`. 
* Переключатели (тумблеры) 
`toggle-second` и `toggle-first` показывают/скрывают секции загрузки, меняют только отображение. 
* Загрузка изображений (два слота)
Обработчик `bindSlot(prefix)` настраивает input + drop-зону, валидацию MIME/расширения, превью через `URL.createObjectURL`, управление `*_status`. 
* Подсказки/валидации
Серые хинты, текст ошибки под слотом, тосты (успех/ошибка сети/ошибка сервера — задел на будущее). 
* Анимация формы
Один кейфрейм `@keyframes pulseForm` (opacity 1 → 0.08 → 1, 0.4s) и один класс `-pulse`; хелпер `pulse(el)` перезапускает анимацию. Привязано к «Тест1» (только при наличии фото) и «Сохранить1». 
* Доступность
role="button", aria-label, sr-only, фокус-обводки, большие зоны клика; превью и кнопка «Убрать» доступны с клавиатуры. 
* Self-tests (консольные)
Лёгкие проверки наличия узлов/атрибутов для ранней диагностики в DevTools.

##### Технологии и инструменты
* HTML + CSS (кастомные свойства, gradients, blur)
UI-оформление, фон «дышит», стекло-эффект у формы, адаптивные размеры. 
* Vanilla JS
Тумблеры, drop-зоны, превью, тосты, хелпер анимации pulse. 
* HTMX (подключён)
Сейчас не используется для POST (оставлен на будущее); есть обработчики событий HTMX и контейнер для ответа сервера. 

##### TODO на будущее (интеграция)
Включить отправку multipart/form-data через HTMX (`hx-post="/api/save"` + `hx-target` уже готовы).
Серверная валидация размеров/типов, сохранение и возврат статуса/ID.
Доп. кнопки тестов могут дергать `/api/test` и стримить прогресс.
Если нужно описание в README-формате или краткую тех-спеку для задачи/тикета — сгенерирую.

#### Пример оформления Страницы-вкладки {id="slot-exmpl"}
В данном примере отсутствует Отображение названия AI модели и отображение ingest-ссылки, однако их нужно добавить в Страницы-вкладки.
Cтраницы-вкладки с настройками слота AI редактированием изображений должны быть оформлены по следующему примеру:
Полный пример интерфейса приведён в файле [`frontend-examples/slot-page.html`](./frontend-examples/slot-page.html).

