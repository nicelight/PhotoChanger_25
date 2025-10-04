# Whats in THIS file 
тут находятся временные данные, не касающиеся проекта. 
Этот файл необходимо игнорировать!

# Временные данные
для анализа какие  модели обработки изображений можно еще внедрить 
https://habr.com/ru/articles/920440/
Ideogram меняет лицо, есть API
https://developer.ideogram.ai/api-reference/api-reference/edit-v3


**1. SDD MCP → формирование “источника истины”**
Вход: ваш повествовательный бриф + контекст по стеку (FastAPI + HTMX + Vanilla JS; без Redis/MinIO/WebSocket), ограничения, цели.
Задачи SDD MCP:
- Разложить бриф на артефакты SDD:
   - Vision
   - Glossary
   - Context/Scope
   - NFRs
   - Constraints
   - Risks
   - Use-cases/Jobs
   - Domain model (термины/агрегаты)
   - Interfaces (OpenAPI черновик)
   - JSON Schema контрактов
   - Sequence/State диаграммы
   - Acceptance Criteria
   - Test Plan (включая QA-матрицу).
- Выдать контракты первыми (OpenAPI/JSON Schema)
- Выдать тонкие фасады и точки расширения (плагины).
- Сгенерировать минимальные “скелеты” репо  с пустыми фасадами и интерфейсами:
   -`/spec/`  единственный источник правды
   - `/contracts/`  единственный источник правды
   - `/adr/`
   - `/docs/blueprints/`
   - `/src/app/`

Первый промпт: 
```markdown
Вот бриф. Сконструируй полный пакет SDD под стек FastAPI+HTMX+VanillaJS (без Redis/MinIO/WebSocket). Контракт-first: сгенерируй OpenAPI и JSON Schema первыми. Далее: NFR, Use-cases, Domain, Sequence, Acceptance Criteria, Test Plan. Разложи по папкам /spec, /contracts, /adr, дай короткий индекс артефактов.
Используй  spec-driven MCP
```
Последующие промпты:
```
«На основе /contracts и скелетов сгенерируй: API Reference, DevRunbook, CONTRIBUTING, тестовую матрицу, ADR черновики; собери diff между кодом и спецификацией; где расхождения — оформи отчёт /docs/diff.md.»
```

**2. Code-Doc MCP → производные документы из контрактов и кода**
Вход: /contracts + скелеты кода, которые SDD MCP уже нагенерил.
Задачи Code-Doc MCP:
- Генерация 
   - API Reference (из OpenAPI)
   - Backend Facade docs (из docstring/типов)
   - Sequence/Deployment диаграмм (по спекам)
   - ADR заготовок из принятых решений
   - README/CONTRIBUTING
   - DevRunbook (как поднять FastAPI, HTMX-фрагменты, миграции)
   - Test docs (матрицы кейсов, фикстуры)
- “Док-дрейф-детектор”: сопоставить текущий код со спецификацией и подсветить расхождения (diff-отчёт), чтобы вы вернулись в SDD MCP и поправили спецификацию/контракты **до** правки кода.
**3. Цикл синхронизации (крутите до готовности)**
- Если Code-Doc MCP нашёл расхождения → вернитесь в SDD MCP с диффом и задайте: `Внеси правки в /spec и /contracts согласно diff`
- После апдейта /spec повторите Code-Doc MCP → обновите авто-доки, ADR, чек-листы
- Только когда спеки стабильны, разрешайте генерацию/рефакторинг кода под них.

Первый промпт
```markdown
«На основе /contracts и скелетов сгенерируй: API Reference, DevRunbook, CONTRIBUTING, тестовую матрицу, ADR черновики; собери diff между кодом и спецификацией; где расхождения — оформи отчёт /docs/diff.md. Используй code-doc MCP.
```
Последующие промпты:
```
«Прими /docs/diff.md и обнови /spec+/contracts так, чтобы устранить дрейф. Сохрани список изменённых артефактов и причину.»
```

**Полезные проверки на каждом витке**

**Контракты неизменны?** → если менялись, код не правим, пока Code-Doc MCP не пересоберёт доки и не пройдёт diff.
NFR покрыты тест-планом? → Code-Doc MCP должен держать чек-лист производительности/безопасности/наблюдаемости.
HTMX-фрагменты документированы как интерфейсы (вход/выход, partials, hx-маршруты).
