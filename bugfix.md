# План багфикса: "Сохранение и Тестирование Слотов" (v2.0)

Этот документ содержит детальные инструкции для исправления критической ошибки потери конфигурации слотов.
План составлен с учетом требований KISS и Strict API Contract.

## Контекст проблемы
1.  При сохранении слота UI перезаписывает настройки, стирая конфигурацию ролей (`role`).
2.  `settings_json` содержит роли, но реляционная таблица `slot_template_media` их не содержит.
3.  Драйверы требуют наличия ролей.

**Цель:** Реализовать строгий контракт (API требует роль) и логику слияния (Backend сохраняет существующие роли).

---

## Часть 1: Инструкции по реализации

### 1. Создание Shared Helper (Backend)
**Файл:** `src/app/slots/slots_utils.py` (Создать новый файл)
**Задача:** Реализовать чистую функцию для слияния конфигурации.

```python
from typing import Any

def merge_template_media_config(
    current_config: list[dict[str, Any]], 
    updates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Merges updates into current configuration.
    - Matches items by 'media_kind'.
    - Updates 'media_object_id'.
    - Preserves existing 'role' from current_config (Database priority).
    - Adds new items from updates (UI priority for new items).
    """
    # 1. Index existing config by media_kind
    existing_map = {item["media_kind"]: item.copy() for item in current_config}
    
    # 2. Process updates
    for update in updates:
        kind = update["media_kind"]
        if kind in existing_map:
            # Update ID only, preserve Role from DB
            existing_map[kind]["media_object_id"] = update["media_object_id"]
        else:
            # New item - take full object (including role from UI)
            existing_map[kind] = update

    return list(existing_map.values())
```

### 2. Модификация Schema (Backend)
**Файл:** `src/app/slots/slots_schemas.py`
**Задача:** Сделать `role` обязательным полем.

1.  В классе `SlotTemplateMediaPayload`:
    ```python
    class SlotTemplateMediaPayload(BaseModel):
        media_kind: str = Field(..., min_length=1)
        media_object_id: str = Field(..., min_length=1)
        role: str = Field(..., min_length=1)  # Required!
        preview_url: str | None = None
    ```

### 3. Модификация Frontend
**Файл:** `src/app/frontend/slots/assets/slot-api.js`
**Задача:** Всегда отправлять роль.

1.  В функции `ensureTemplateMediaBinding`:
    ```javascript
    return [{ 
        media_kind: templateState.kind, 
        media_object_id: templateState.mediaId, 
        role: "template" // Always send default role
    }];
    ```

### 4. Модификация Backend API (Sanitizer)
**Файл:** `src/app/slots/slots_api.py`
**Задача:** Валидация роли.

1.  В функции `_sanitize_template_media`:
    ```python
    role = item.get("role")
    if not role:
        raise _bad_request(f"template_media[{index}] requires 'role'")
        
    prepared.append({
        "media_kind": str(media_kind),
        "media_object_id": str(media_object_id),
        "role": str(role)
    })
    ```

### 5. Модификация Repository (Save Logic)
**Файл:** `src/app/slots/slots_repository.py`
**Задача:** Мёрж JSON и синхронизация таблицы.

1.  Импортируй helper: `from .slots_utils import merge_template_media_config`.
2.  В методе `update_slot`:
    *   Загрузи `current_settings = json.loads(row.settings_json)`.
    *   Получи текущий список медиа: `current_media = current_settings.get("template_media", [])`.
    *   Выполни слияние: `merged_media = merge_template_media_config(current_media, template_media)`.
    *   Обнови настройки: `current_settings["template_media"] = merged_media`.
    *   Сохрани JSON: `row.settings_json = json.dumps(current_settings)`.
    *   **Синхронизация таблицы:**
        *   Удали старые записи из `SlotTemplateMediaModel`.
        *   Создай новые записи на основе **`merged_media`** (а не просто входящего списка!), чтобы таблица соответствовала JSON.

### 6. Модификация Ingest Service (Test Run Logic)
**Файл:** `src/app/ingest/ingest_service.py`
**Задача:** Использовать тот же helper.

1.  Импортируй helper.
2.  В `_apply_test_overrides`:
    *   `template_overrides = overrides.get("template_media")`
    *   `current_media = job.slot_settings.get("template_media", [])`
    *   `merged = merge_template_media_config(current_media, template_overrides)`
    *   `job.slot_settings["template_media"] = merged`
    *   (Не забудь обновить также `job.slot_template_media` map, если он используется).

---

## Часть 2: Проверка (Verification)

1.  **Создать новый слот (через скрипт или UI):** Убедиться, что он получает роль `template` и сохраняется в БД (и JSON, и Таблица).
2.  **Редактировать старый слот:** Изменить картинку через UI. Убедиться, что роль (например `background`) не изменилась на `template`.
3.  **Test Run:** Убедиться, что тест проходит успешно с теми же условиями.

---

## Часть 3: Риски и Bottlenecks (Self-Correction)

1.  **Рассинхрон JSON и Таблицы:**
    *   *Риск:* Если обновить только JSON, запросы `list_slots` (которые могут читать из таблицы) вернут старые данные.
    *   *Решение:* План четко требует перезаписи таблицы данными из `merged_media`.

2.  **Pydantic Stripping:**
    *   *Риск:* `SlotUpdateRequest` может вырезать поле `role` если оно не в схеме.
    *   *Решение:* Мы добавили `role` в `SlotTemplateMediaPayload` в шаге 2.

3.  **Турботекст:**
    *   *Риск:* Потеря `form_field` для новых слотов.
    *   *Решение:* Для новых слотов это ожидаемое поведение (требуется ручная настройка админом). Для старых — слияние сохранит `form_field`.

Этот план обеспечивает целостность данных и соответствие принципам KISS.
