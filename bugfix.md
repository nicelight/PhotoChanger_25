# Промпт для фикса бага "Частичное обновление template_media при тестовом запуске"

Ты выступаешь в роли Senior Backend Engineer. Твоя задача — исправить ошибку логики в сервисе обработки изображений (`IngestService`), из-за которой тестовый запуск слота из админки приводит к удалению конфигурации ролей (`role`) у шаблонных изображений.

## 1. Суть проблемы

В проекте есть функционал "Test Run" для слотов, где администратор может временно переопределить используемые изображения-шаблоны (например, заменить "фон" для текущего прогона).
Веб-интерфейс отправляет список переопределений (`overrides`), содержащий только пары `media_kind` и `media_object_id`.

**Текущее поведение:**
Метод `src/app/ingest/ingest_service.py: _apply_test_overrides` берет этот неполный список и **полностью заменяет** им настройки слота (`job.slot_settings["template_media"]`).
Из-за этого теряются поля `role`, `optional`, которые обязательны для работы `TemplateMediaResolver`. В результате возникает ошибка `TemplateMediaResolutionError: Template media entry requires 'role' field`.

**Требуемое поведение (Fix):**
Вместо полной замены списка настроек, необходимо реализовать логику **частичного обновления (Patch/Merge)**.
Нужно обновить `media_object_id` только для тех элементов списка `template_media`, у которых совпадает `media_kind`. Остальные поля (особенно `role`) должны остаться нетронутыми.

---

## 2. Шаги по реализации фикса

Пожалуйста, выполни следующие изменения в коде:

### Файл: `src/app/ingest/ingest_service.py`

Найди метод `_apply_test_overrides`.
Измени блок обработки `overrides.get("template_media")`.

**Алгоритм:**
1.  Получи список переопределений из `overrides["template_media"]`.
2.  Создай словарь (map) для быстрого поиска: `updates = { item["media_kind"]: item["media_object_id"] for item in overrides }`.
3.  Получи текущий список настроек из `job.slot_settings`. Если ключа `template_media` нет, создай пустой список.
4.  Пройдись по текущему списку настроек. Если `media_kind` элемента есть в словаре `updates`, обнови его `media_object_id` значением из словаря.
5.  **Важно:** НЕ заменяй `job.slot_settings["template_media"]` целиком на список из `overrides`. Обновляй существующий список in-place или создавай новый на основе старого с применением патчей.
6.  Убедись, что словарь `job.slot_template_media` (используемый для быстрого доступа по kind) также корректно обновляется.

**Пример ожидаемой логики (псевдокод):**

```python
template_overrides = overrides.get("template_media")
if isinstance(template_overrides, list):
    # 1. Map new IDs by Kind
    updates_map = {
        item.get("media_kind"): item.get("media_object_id")
        for item in template_overrides
        if item.get("media_kind") and item.get("media_object_id")
    }

    # 2. Update existing settings preserving 'role'
    current_media = job.slot_settings.get("template_media", [])
    for entry in current_media:
        kind = entry.get("media_kind")
        if kind in updates_map:
            entry["media_object_id"] = updates_map[kind]
    
    # 3. Update the quick-lookup map (existing logic needs to reflect updates)
    # Re-build slot_template_media based on the UPDATED current_media
    job.slot_template_media = {
        item["media_kind"]: item["media_object_id"]
        for item in current_media
        if item.get("media_kind") and item.get("media_object_id")
    }
```

### Правки спецификаций
В данном случае спецификации API менять не нужно, так как мы исправляем внутреннюю логику обработки данных, приводя её в соответствие с фактическим форматом данных (Partial Update).

---

## 3. Шаги самопроверки (Verification)

После внесения изменений проверь работоспособность следующим образом:

1.  **Создай скрипт воспроизведения (repro.py):**
    *   Создай `JobContext` с `slot_settings`, содержащим `template_media` с полем `role`.
        ```python
        job.slot_settings = {
            "template_media": [
                {"role": "background", "media_kind": "bg", "media_object_id": "old_id"}
            ]
        }
        ```
    *   Вызови `_apply_test_overrides` с overrides:
        ```python
        overrides = {
            "template_media": [{"media_kind": "bg", "media_object_id": "new_id"}]
        }
        ```
    *   **Проверка:** Убедись, что после вызова в `job.slot_settings["template_media"][0]` поле `media_object_id` стало `"new_id"`, а поле `role` осталось `"background"`.

2.  **Запусти существующие тесты:**
    Убедись, что не сломалась базовая функциональность.
    `pytest tests/unit/ingest/test_service.py`

3.  **Логическая проверка:**
    Проверь, что будет, если в overrides придет `media_kind`, которого нет в настройках слота. (Он должен быть проигнорирован, так как мы только обновляем существующие привязки).
