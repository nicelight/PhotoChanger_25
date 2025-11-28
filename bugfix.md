# Промпт для фикса багов "Test Run" и "Save Slot"

Ты выступаешь в роли Senior Fullstack Engineer. Твоя задача — комплексно исправить проблему потери конфигурации слота (в частности поля `role`) при сохранении и тестировании слота из админ-панели.

## 1. Суть проблемы

1.  **Frontend:** Админ-панель при отправке данных (для теста или сохранения) отправляет только `media_kind` и `media_object_id`, но не отправляет `role`.
2.  **Backend (API):** Валидатор `_sanitize_template_media` принудительно удаляет все поля кроме kind и id.
3.  **Backend (Logic):** Сервисы перезаписывают существующую конфигурацию слота (`settings_json`) неполными данными от фронтенда, удаляя существующие роли и настройки.

Это приводит к тому, что провайдеры (Gemini) перестают видеть шаблонные изображения, так как резолвер требует наличия поля `role`.

## 2. Задача

Реализовать надежный механизм сохранения и тестирования, который:
1.  Обеспечивает наличие роли `template` для новых слотов.
2.  Сохраняет существующие сложные роли (например, `background`, `style`) для старых слотов.

---

## 3. Шаги по реализации

### Шаг 1: Frontend (`src/app/frontend/slots/assets/slot-api.js`)
В функции `ensureTemplateMediaBinding` добавь отправку поля `role`.
Так как в текущем UI поддерживается только один слот шаблона, используй фиксированное значение `"template"`.

```javascript
// Было:
return [{ media_kind: templateState.kind, media_object_id: templateState.mediaId }];

// Стало:
return [{ 
    media_kind: templateState.kind, 
    media_object_id: templateState.mediaId, 
    role: "template" // Добавляем дефолтную роль
}];
```

### Шаг 2: Backend API (`src/app/slots/slots_api.py`)
В функции `_sanitize_template_media` разреши прохождение поля `role`.

```python
# Добавь обработку role:
role = item.get("role")
# ...
prepared.append({
    "media_kind": str(media_kind),
    "media_object_id": str(media_object_id),
    "role": str(role) if role else None # Разрешаем role
})
```

### Шаг 3: Backend Logic — Save (`src/app/slots/slots_repository.py`)
Измени метод `update_slot`. Реализуй логику **Merge (Слияния)** настроек.

**Алгоритм:**
1.  Загрузи текущий `settings_json`.
2.  Обнови верхнеуровневые поля (`prompt`, `output`) из пришедшего `payload.settings`.
3.  Обработай `template_media`:
    *   Создай карту обновлений из payload: `updates = { item["media_kind"]: item for item in template_media }`.
    *   Пройдись по существующему списку `template_media` в настройках. Если `media_kind` совпадает — обнови `media_object_id`, **сохранив** старый `role` (и другие поля).
    *   Если в `updates` есть элементы, которых нет в существующих настройках (новые картинки) — добавь их в список (тут пригодится `role="template"`, который мы добавили на фронтенде).
4.  Сохрани результат обратно в `settings_json`.

### Шаг 4: Backend Logic — Test Run (`src/app/ingest/ingest_service.py`)
Измени метод `_apply_test_overrides`.
Используй ту же логику Merge, что и в репозитории: обновляй `job.slot_settings` точечно, сохраняя существующие поля, вместо полной замены списка.

---

## 4. Критерии приемки (Self-Check)

1.  **Test Run:** При нажатии "Тест" с загруженным шаблоном:
    *   Бэкенд получает `role="template"`.
    *   Если у слота уже была роль (напр. `style`), она должна сохраниться (приоритет базы).
    *   Если слот новый, должна использоваться роль `template`.
    *   `TemplateMediaResolver` не падает.
2.  **Save Slot:** При нажатии "Сохранить":
    *   В базе данных в `settings_json` сохраняется структура `template_media`.
    *   Поле `role` присутствует.
    *   Другие настройки (если были) не затираются.

Выполни эти изменения, следуя принципу KISS: минимум усложнений, максимальная надежность данных.
