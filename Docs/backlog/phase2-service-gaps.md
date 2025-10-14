# Phase 2 — Service Layer Gaps

The scaffolding in phase 2 introduces domain models and interfaces without
implementations. Follow-up phases must address the following integration gaps:

- **PostgreSQL queue schema** — tables for `job`, `processing_log`, slot/template
  bindings and the `media_object` store. Queue operations rely on
  `SELECT ... FOR UPDATE SKIP LOCKED` and must enforce `expires_at` updates
  derived from `T_sync_response`.
- **Settings persistence** — migrations for `app_settings` with fields covering
  `ingest.sync_response_timeout_sec`, public link TTL mirroring that value and
  `media.result_retention_sec = 72h`. Implement password hashing/rotation policy
  surfaced through `SettingsService`.
- **Media storage configuration** — filesystem or object storage wiring for
  payloads and 72h retention of result files. Includes background cleanup tasks
  for payload TTL (`T_sync_response`) and result retention windows.
- **Provider adapters** — Gemini and Turbotext client adapters with throttling
  and polling bounded by `T_sync_response`. Provide a plug-in registration layer
  for mapping slot `provider` identifiers to adapter factories.
- **Background jobs and maintenance** — workers to purge expired queue records,
  revoke public media links and refresh slot `recent_results`. Requires
  scheduling primitives (cron/job runner) aligned with TTL expectations.
- **Monitoring/metrics pipeline** — persistence and aggregation for
  `ProcessingLog` records, Prometheus exporters and alerting rules covering
  timeout rates and queue backlog.
