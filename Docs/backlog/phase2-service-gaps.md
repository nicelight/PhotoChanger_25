# Phase 2 — Service Layer Gaps

The scaffolding in phase 2 introduces domain models and interfaces without
implementations. Follow-up phases must address the following integration gaps:

- **PostgreSQL schema & migrations** — create tables for `job`, `media_object`,
  `processing_log`, `template_media`, slot/template bindings and `app_settings`.
  Queue operations have to honour `job.expires_at = created_at + T_sync_response`
  and use `SELECT ... FOR UPDATE SKIP LOCKED` with appropriate indexes to avoid
  head-of-line blocking.
- **Transaction management** — wire a concrete `UnitOfWork` (SQLAlchemy or
  psycopg-based) to coordinate `JobRepository`, `SlotRepository`,
  `SettingsRepository`, `StatsRepository` and media storage updates within
  atomic boundaries.
- **Settings persistence** — materialize nested structures for
  `dslr_password`, `provider_keys`, `ingest` and `media_cache`. Implement
  password hashing/rotation and ensure TTL fields (`sync_response_timeout_sec`,
  `public_link_ttl_sec`, `processed_media_ttl_hours`) stay consistent with the
  SDD formulas.
- **Media storage configuration** — provision filesystem or object storage for
  ingest payloads (`T_sync_response` TTL), template media and result files with
  `T_result_retention = 72h`. Implement public URL generation plus purging logic
  exposed through `MediaService.purge_expired_media`.
- **Provider adapters & routing** — deliver Gemini and Turbotext client
  adapters, map `Slot.provider_id` to factories in the plugin layer and enforce
  polling/throttling windows bounded by `T_sync_response`.
- **Background jobs & maintenance** — schedule workers for queue timeout
  handling, public link revocation, template cleanup and refreshing
  `Slot.recent_results` galleries. Requires cron/job-runner configuration and
  TTL-aware cleanup routines.
- **Monitoring & analytics** — persist `ProcessingLog` records, build
  aggregations for the statistics API and expose Prometheus metrics/alerts for
  timeout rate, queue backlog and provider latency.
- **Service wiring** — implement `services.container.build_service_registry()`
  to register repositories, storage backends, providers and the unit-of-work so
  that FastAPI endpoints and workers can resolve concrete implementations.
