# План багфикса: "Сохранение и Тестирование Слотов" (v3.0 - Final)

Этот документ содержит детальные инструкции для исправления критической ошибки потери конфигурации слотов.
План составлен с учетом требований KISS, Strict API Contract и системного подхода к управлению данными.

## TSKS (Tasks Breakdown)

[ ] US PHC-2.1.4 — Merge сохранения template_media и test-run overrides
    [ ] T PHC-2.1.4.GOV — Governance & Discovery
      [ ] T PHC-2.1.4.GOV.1 — CONSULT — подтвердить обязательность поля `role` и стратегию merge (без удаления) для template_media
      [ ] T PHC-2.1.4.GOV.2 — REFLECT — учесть миграцию существующих слотов (добавить роли по умолчанию) и синхронизацию settings_json с таблицей
    [ ] T PHC-2.1.4.1 — Обновить схемы/контракты (OpenAPI, Pydantic) для `template_media` с обязательным `role`; SemVer bump
    [ ] T PHC-2.1.4.2 — Вынести общий helper merge для template_media и применить в `slots_repository.update_slot` и `IngestService._apply_test_overrides`
    [ ] T PHC-2.1.4.3 — Синхронизировать `slot_template_media` таблицу с итоговым `template_media` из settings_json (перезапись по media_kind без удаления ролей) и **обновить маппер `_to_domain` для чтения ролей из JSON**.
    [ ] T PHC-2.1.4.4 — Обновить фронтенд (`slot-api.js`) чтобы всегда слать `role` (`template`/`photo`) для сохранения и test-run
    [ ] T PHC-2.1.4.5 — Добавить тесты: unit на merge helper, контракт/интеграцию test-run и сохранения слота, smoke миграции ролей

---

## Детальные Инструкции по реализации

### 1. Создание Shared Helper (T PHC-2.1.4.2)
**Файл:** `src/app/slots/slots_utils.py`
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
    existing_map = {item["media_kind"]: item.copy() for item in current_config}
    
    for update in updates:
        kind = update["media_kind"]
        if kind in existing_map:
            existing_map[kind]["media_object_id"] = update["media_object_id"]
        else:
            existing_map[kind] = update

    return list(existing_map.values())
```

### 2. Модификация Schema (T PHC-2.1.4.1)
**Файл:** `src/app/slots/slots_schemas.py`
**Задача:** Сделать `role` обязательным полем.

```python
class SlotTemplateMediaPayload(BaseModel):
    media_kind: str = Field(..., min_length=1)
    media_object_id: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)  # Required!
    preview_url: str | None = None
```

### 3. Модификация Frontend (T PHC-2.1.4.4)
**Файл:** `src/app/frontend/slots/assets/slot-api.js`
**Задача:** Всегда отправлять роль.

```javascript
return [{ 
    media_kind: templateState.kind, 
    media_object_id: templateState.mediaId, 
    role: "template" // Always send default role
}];
```

### 4. Модификация Backend API (Sanitizer)
**Файл:** `src/app/slots/slots_api.py`
**Задача:** Валидация роли в `_sanitize_template_media`.

```python
role = item.get("role")
if not role:
    raise _bad_request(f"template_media[{index}] requires 'role'")
prepared.append({ ..., "role": str(role) })
```

### 5. Модификация Repository (Save Logic & Mapper) (T PHC-2.1.4.3)
**Файл:** `src/app/slots/slots_repository.py`

**А. Update Logic (`update_slot`):**
1.  Загрузи `current_settings`.
2.  Выполни `merge_template_media_config`.
3.  Сохрани обновленный JSON.
4.  Перезапиши таблицу `SlotTemplateMediaModel` данными из **merged list**.

**Б. Mapper Logic (`_to_domain`):**
**Критично:** При чтении слота (`GET`) мы должны отдавать роли. Таблица их не хранит.
Нужно изменить логику сборки `Slot` домена:
1.  Читать `template_media` не из `model.template_media` (SQL relation), а из `settings_json` (или мержить их).
2.  *Рекомендация:* Если `settings_json` теперь источник правды, то `_to_domain` должен парсить JSON и формировать список `template_media` на его основе. Реляционную таблицу использовать только если JSON пуст (fallback) или для оптимизации SQL-запросов (фильтрации), но не для маппинга полей.

### 6. Модификация Ingest Service (Test Run Logic) (T PHC-2.1.4.2)
**Файл:** `src/app/ingest/ingest_service.py`
**Задача:** Использовать `merge_template_media_config` в `_apply_test_overrides`.

---

## Verification
1.  **Save:** Изменить картинку в UI -> Сохранить -> Проверить БД (JSON должен содержать role, Таблица должна содержать новую запись).
2.  **Test:** Запустить тест -> Проверить, что `TemplateMediaResolver` не падает.
3.  **Consistency:** Проверить `GET /api/slots/{id}` — должен возвращать список с ролями.
