# Диаграммы PhotoChanger

Каталог `spec/diagrams/` содержит актуальные визуальные артефакты системы. Все файлы лежат в UTF‑8 без BOM и используют синтаксис Mermaid (расширение `.mmd`) без Markdown-обрамления ```mermaid```, чтобы рендер на GitHub работал напрямую.

## C4-уровень
- `c4-context.mmd` — контекст PhotoChanger и внешние акторы (соотносится с `spec/docs/context.md`).
- `c4-container.mmd` — контейнерная диаграмма монолита FastAPI и зависимостей.

## Последовательности и состояния
- `uc2-ingest-success-sequence.mmd` — базовый сценарий успешного ingest (UC2).
- `uc3-ingest-state.mmd` — состояние джоба ingest (`pending/done/timeout/failed`).
- `uc3-ingest-timeout-sequence.mmd` — сценарий таймаута ingest (UC3).
- `uc4-mediaobject-state.mmd` — жизненный цикл `media_object`.
- `uc5-gallery-sequence.mmd` — публикация результатов в галерее (UC5).
- `uc6-ops-sequence.mmd` — обзор работы администратора/оператора со слотами и метриками (UC6).
- `cron-cleanup-state.mmd` — жизненный цикл запуска скрипта очистки медиакеша.

## Правила редактирования
- Перед изменениями сверяйся с соответствующим документом в `spec/docs/` или контрактом; при расхождении инициируй `CONSULT`.
- Не добавляй окружение ```mermaid``` — GitHub интерпретирует `.mmd` как чистый Mermaid.
- Для проверки используй [Mermaid Live Editor](https://mermaid.live/) или `npx @mermaid-js/mermaid-cli -i file.mmd -o file.svg`.
- При необходимости PlantUML сохраняем с расширением `.puml`, но фиксируем это в README и добавляем инструкции по рендеру.

## Поддержка актуальности
- После обновления диаграмм обновляй ссылки на них в `spec/docs/` и логируй изменения в `.memory/WORKLOG.md`.
- Проверяй, что `git diff` не содержит «Р…» артефактов и файлы читаются через `py -X utf8 -c "Path(...).read_text()"`.
