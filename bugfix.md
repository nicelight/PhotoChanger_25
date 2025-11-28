# План багфикса: "Сохранение и Тестирование Слотов"

Этот документ содержит детальные инструкции для исправления критической ошибки, при которой редактирование слота в Admin UI приводит к удалению конфигурации ролей (`role`) и поломке интеграции с провайдерами (Gemini).

## Контекст
В проекте существует ~15 статичных слотов с предустановленной конфигурацией (JSON `settings`).
UI при сохранении слота перезаписывает эту конфигурацию неполными данными (без поля `role`), что ломает работу слотов.
Наша задача — внедрить механизм **Partial Update (Merge)**, чтобы сохранять существующие настройки при редактировании.

---

## Часть 1: Инструкции по реализации

### 1. Модификация Schema (Backend)
**Файл:** `src/app/slots/slots_schemas.py`
**Задача:** Разрешить поле `role` в API, чтобы Pydantic не удалял его при валидации входящего JSON.

1.  Найди класс `SlotTemplateMediaPayload`.
2.  Добавь поле `role`:
    ```python
    class SlotTemplateMediaPayload(BaseModel):
        media_kind: str = Field(..., min_length=1)
        media_object_id: str = Field(..., min_length=1)
        role: str | None = None  # <--- Добавить это поле
        preview_url: str | None = None
    ```

### 2. Модификация Frontend
**Файл:** `src/app/frontend/slots/assets/slot-api.js`
**Задача:** Принудительно отправлять роль `"template"` для шаблонных изображений.

1.  Найди функцию `ensureTemplateMediaBinding`.
2.  Добавь поле `role: "template"` в возвращаемый объект.
    ```javascript
    // Было:
    return [{ media_kind: templateState.kind, media_object_id: templateState.mediaId }];
    
    // Стало:
    return [{ 
        media_kind: templateState.kind, 
        media_object_id: templateState.mediaId, 
        role: "template" 
    }];
    ```

### 3. Модификация Backend API (Sanitizer)
**Файл:** `src/app/slots/slots_api.py`
**Задача:** Пропустить поле `role` через ручной валидатор (используется для Test Run).

1.  Найди функцию `_sanitize_template_media`.
2.  В цикле обработки элементов извлеки и сохрани `role`.
    ```python
    # Измени формирование словаря prepared.append:
    role = item.get("role")
    prepared.append({
        "media_kind": str(media_kind),
        "media_object_id": str(media_object_id),
        "role": str(role) if role else None 
    })
    ```

### 4. Модификация Backend Logic (Repository - Save)
**Файл:** `src/app/slots/slots_repository.py`
**Задача:** Реализовать логику слияния (Merge) настроек при сохранении.

1.  В методе `update_slot`:
    *   Считай текущий `settings_json` из базы данных (`current_settings`).
    *   Обнови `current_settings` значениями из `settings` (аргумент функции), но НЕ перезаписывай целиком. (Например, `current_settings.update(settings)`).
    *   **Слияние Template Media:**
        *   Преобразуй входящий список `template_media` (из аргументов) в словарь: `updates = { item["media_kind"]: item for item in template_media }`.
        *   Пройдись по списку `current_settings["template_media"]`.
        *   Если `media_kind` элемента совпадает с `updates`: обнови его `media_object_id`. **Важно:** Поле `role` (и другие) оставь из `current_settings` (приоритет базы данных).
        *   Если в `updates` есть элементы, которых нет в `current_settings` (новые картинки): добавь их в список целиком. (Здесь сработает наша дефолтная роль `"template"` с фронтенда).
    *   Сохрани обновленный `current_settings` обратно в `row.settings_json`.

### 5. Модификация Backend Logic (Service - Test Run)
**Файл:** `src/app/ingest/ingest_service.py`
**Задача:** Аналогичная логика слияния для тестового запуска.

1.  В методе `_apply_test_overrides`:
    *   Вместо `job.slot_settings["template_media"] = template_overrides` реализуй алгоритм слияния, аналогичный описанному выше для репозитория.
    *   Цель: обновить ID картинок в `job.slot_settings`, не потеряв роли.

---

## Часть 2: Анализ рисков и Self-Critique

### Потенциальные проблемы (Bottlenecks)

1.  **Конфликт ролей:**
    *   *Риск:* Фронтенд шлет `role: "template"`. В базе у слота может быть роль `role: "background"`.
    *   *Решение в плане:* Логика Merge отдает приоритет базе данных. Если запись с таким `media_kind` уже есть, мы берем роль из базы, игнорируя присланную `"template"`. Это корректно.

2.  **Множественные шаблоны:**
    *   *Риск:* Слот требует 2 шаблона (фон и стиль). UI поддерживает загрузку только одного (Second Image).
    *   *Анализ:* Это ограничение текущего UI. Наш фикс не чинит UI, но он предотвращает удаление второго шаблона при сохранении первого. Merge-логика обновит только тот шаблон, который прислал UI, оставив второй нетронутым. Это улучшение по сравнению с текущим полным удалением.

3.  **Turbotext Form Fields:**
    *   *Риск:* Turbotext требует поле `form_field` в конфиге. UI его не шлет.
    *   *Решение:* Так как мы мержим настройки с существующим конфигом в БД (где `form_field` прописан), это поле сохранится. Для абсолютно новых слотов Turbotext работать не будет, пока администратор вручную (через БД) не пропишет конфиг, но для 15 статичных слотов это решение надежно.

4.  **Синхронизация Relational Table и JSON:**
    *   *Риск:* `update_slot` обновляет и JSON, и реляционную таблицу `SlotTemplateMediaModel`.
    *   *Решение:* Реляционная таблица обновляется "начисто" (delete + insert) в текущем коде. Это нормально, так как она содержит только связи (kind, id). Главное — чтобы JSON (содержащий метаданные role) был обновлен через Merge.

### Вывод
План надежен для поддержки существующих слотов (Primary Goal). Он минимизирует риски потери данных при редактировании через UI.
