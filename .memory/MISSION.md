---
id: mission
version: 1
updated: 2025-01-14
owner: product
---

# Миссия и ценность
- **Кому помогаем:** администраторам контента и студийным операторам, которые запускают обработку из DSLR Remote Pro, а также команде эксплуатации, контролирующей SLA и затраты провайдеров. Платформа обеспечивает единое окно управления слотами и автоматизирует доставку готовых изображений по публичным ссылкам в пределах гарантийных TTL.【F:spec/docs/blueprints/vision.md】【F:Docs/brief.md】
- **Почему сейчас:** бизнесу требуется консистентный серверный слой между DSLR Remote Pro и несколькими AI-провайдерами (Gemini, Turbotext) с соблюдением их лимитов, дедлайнов и требований к хранению медиа. Без этой прослойки команды тратят время на ручную маршрутизацию и рискуют нарушить SLA или потерять файлы из-за рассинхрона TTL.【F:spec/docs/blueprints/vision.md】【F:spec/docs/blueprints/constraints-risks.md】
- **Бизнес-метрики успеха:** ≥ 95 % ingest-запросов завершаются 200 в пределах `T_sync_response`; доля таймаутов ≤ 5 %; SLA доступности ingest API ≥ 99 %; отсутствие утечек временных/итоговых файлов после наступления TTL; соблюдение квот провайдеров (Gemini/Turbotext).【F:spec/docs/blueprints/vision.md】【F:spec/docs/blueprints/nfr.md】

## Scope
- **In-scope:**
  - Ingest API с polling записи `Job` и возвратом 200/504 строго по `T_sync_response` (45–60 с).【F:Docs/brief.md】【F:spec/docs/blueprints/use-cases.md】
  - Очередь задач на PostgreSQL, воркеры с интеграцией Gemini и Turbotext, расчёт TTL и очистка временных/итоговых медиа (`media_object`, `Job.result_*`).【F:spec/docs/blueprints/context.md】【F:spec/docs/blueprints/domain-model.md】
  - Административный UI/API: управление слотами (`slot-001`…`slot-015`), шаблонными медиа, глобальными настройками (ingest-пароль, `T_sync_response`), просмотр `recent_results` и статистики.【F:Docs/brief.md】【F:spec/docs/blueprints/use-cases.md】
  - Безопасность и наблюдаемость: JWT для администраторов (`serg`, `igor`), логирование статусов Job, метрики таймаутов, алерты по превышению 504 и заполнению хранилищ.【F:spec/docs/blueprints/nfr.md】【F:spec/docs/blueprints/acceptance-criteria.md】
- **Out-of-scope:**
  - Регистрация новых пользователей, self-service смена паролей и внешние IdP (MVP ограничивается статическими аккаунтами).【F:spec/docs/blueprints/context.md】
  - Автоматическое продление TTL публичных ссылок или исходных файлов; повторный доступ требует нового ingest или повторной регистрации медиа.【F:spec/docs/blueprints/constraints-risks.md】【F:spec/docs/blueprints/use-cases.md】
  - Подключение дополнительных AI-провайдеров, новых очередей (Kafka) и расширенной UI-аналитики — отдельные инициативы roadmap.【F:spec/docs/blueprints/context.md】【F:Docs/implementation_roadmap.md】

## Критерии успеха (верхнеуровневые NFR/SLO/SLA)
- Ingest API удерживает соединение и завершает ответ (200/504) строго в пределах актуального `T_sync_response`; после таймаута все временные ресурсы очищаются, а задача фиксируется как `failure_reason = 'timeout'`.【F:spec/docs/blueprints/nfr.md】【F:spec/docs/blueprints/use-cases.md】
- Очередь и воркеры устойчивы к рестартам и не теряют задачи (PostgreSQL `SELECT … FOR UPDATE SKIP LOCKED`, идемпотентная отмена).【F:spec/docs/blueprints/nfr.md】【F:spec/docs/blueprints/domain-model.md】
- Публичные ссылки и результирующие файлы соблюдают TTL (`T_public_link_ttl = T_sync_response`, `T_result_retention = 72h`); после истечения API возвращает `410 Gone`, а утечек не происходит.【F:spec/docs/blueprints/vision.md】【F:spec/docs/blueprints/use-cases.md】
- Мониторинг покрывает p95 ingest, долю 504, заполнение `MEDIA_ROOT`, квоты провайдеров; алерты срабатывают при отклонениях и поддерживают SLA 99 %.【F:spec/docs/blueprints/nfr.md】【F:spec/docs/blueprints/acceptance-criteria.md】
