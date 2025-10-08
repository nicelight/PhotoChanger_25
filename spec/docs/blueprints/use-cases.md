# Use-cases и сценарии PhotoChanger

## UC1. Настройка слота администратором
- **Акторы:** Администратор, Slot Management UI, Admin API.
- **Предусловия:** Администратор авторизован через JWT с правами `slots:write`.
- **Основной поток:**
  1. Администратор открывает список слотов и выбирает создать/редактировать слот.
  2. UI запрашивает список доступных провайдеров и операций.
  3. Администратор выбирает провайдера (например, Gemini) и операцию (`style_transfer`).
  4. UI показывает форму параметров (промпт, template_media и т.д.), администратор заполняет значения.
  5. Администратор сохраняет слот; API валидирует параметры и выдаёт ingest-URL/секрет.
- **Альтернативы/ошибки:**
  - Некорректные параметры → `422` с описанием полей.
  - Конфликт при изменении секрета → `409`, UI предлагает обновить ссылку.

## UC2. Ingest с успешной обработкой
- **Акторы:** DSLR Remote Pro, Ingest API, Очередь, Worker, AI-провайдер (Gemini).
- **Предусловия:** Slot активен, ссылка и пароль валидны.
- **Основной поток:**
  1. DSLR Remote Pro отправляет `POST /ingest/{slotId}` с фото и паролем.
  2. Ingest API валидирует вход, создаёт `Job` со статусом `pending`, сохраняет исходный файл (`media_object`).
  3. Job ставится в очередь и выбирается воркером, статус `processing`.
  4. Воркер вызывает провайдера Gemini (`models.generateContent`), передавая параметры слота и изображение.
  5. Провайдер возвращает обработанное изображение до наступления `T_sync_response`.
  6. Воркер сохраняет `Result`, очищает исходный `media_object`, обновляет статус `completed`.
  7. Ingest API возвращает 200 OK с обработанным изображением, job закрывается.

### Диаграмма последовательности (успех)
```mermaid
sequenceDiagram
    participant DSLR as DSLR Remote Pro
    participant API as Ingest API
    participant Queue as Очередь задач
    participant Worker as Worker
    participant Gemini as Gemini API
    participant Storage as Media Storage

    DSLR->>API: POST /ingest/{slotId}
    API->>Storage: Сохранить media_object (TTL ≤ 50 c)
    API->>Queue: Создать Job (pending)
    API->>API: Ожидание результата (≤ 50 c)
    Queue->>Worker: Забрать Job
    Worker->>Gemini: models.generateContent(...)
    Gemini-->>Worker: Обработанное изображение
    Worker->>Storage: Сохранить Result (TTL 72 ч)
    Worker->>API: Статус completed
    API-->>DSLR: HTTP 200 + изображение
```

## UC3. Ingest с таймаутом 504
- **Различия с UC2:**
  - На шаге вызова провайдера ответ не приходит до `T_sync_response`.
  - API завершает ожидание с 504 и помечает Job `failed_timeout`.
  - Воркер получает сигнал отмены, прекращает операции и удаляет временные файлы.
  - Провайдерские ответы, пришедшие позже, игнорируются.

### Диаграмма состояний Job
```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> processing: Worker забрал задачу
    processing --> completed: Результат получен ≤ T_sync_response
    processing --> failed_timeout: Истёк T_sync_response
    processing --> failed_provider: Ошибка провайдера / исчерпаны ретраи
    pending --> cancelled: Администратор отменил слот/задачу
    processing --> cancelled: Ручная отмена до финала
    completed --> [*]
    failed_timeout --> [*]
    failed_provider --> [*]
    cancelled --> [*]
```

## UC4. Истечение временной ссылки
- **Акторы:** Администратор/UI, Admin API, Media Storage.
- **Предусловия:** Существующий `media_object`, связанный с Job в статусе `pending`.
- **Основной поток:**
  1. Администратор регистрирует файл через `POST /api/media/register` и получает `expires_at = now + 60s`.
  2. Провайдер не скачивает файл в течение минуты; TTL истекает автоматически.
  3. Очиститель помечает запись `media_object` как удалённую и инициирует `failed_timeout` для связанного Job.
- **Ошибки:**
  - Попытка обратиться к истекшей ссылке → `410 Gone`.
  - Попытка продлить TTL через несуществующий эндпоинт → `404 Not Found`.

## UC5. Управление шаблонными медиа
- **Акторы:** Администратор, Admin API, Storage.
- **Сценарий:** загрузка `template_media` через `POST /api/template-media/register`, привязка к слоту, удаление через `DELETE /api/template-media/{id}`.
- **Особенности:** Файлы не имеют публичных ссылок, доступны только воркерам по идентификатору; удаление требует проверки, что слот обновлён.
