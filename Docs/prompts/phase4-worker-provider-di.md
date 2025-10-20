# Prompt: Fix Queue Worker Provider Dispatch and DI Gaps

## Role & Goal
You are Codex Agent, responsible for completing Phase 4 task **4.3 "Queue worker end-to-end"**. Your immediate goal is to eliminate the dependency-injection gaps that prevent the queue worker from selecting and invoking provider adapters.

## Context Recap
- Domain overview: review `.memory/MISSION.md`, `.memory/CONTEXT.md`, `.memory/TASKS.md`, `.memory/USECASES.md` for mission, scope, and phase 4 decomposition.
- Architecture & decisions: `spec/adr/` (especially ADR-0002 on TTL), `spec/docs/blueprints/domain-model.md`, `spec/docs/blueprints/use-cases.md`.
- Contracts & data model: `spec/contracts/openapi.yaml`, JSON Schemas under `spec/contracts/schemas/`, and provider docs `Docs/providers/*.md`.
- Existing implementation: focus on `src/app/services`, `src/app/queue`, `src/app/providers`, `src/app/infrastructure/di`, `tests/integration/`, and `tests/contract/`.
- Mock providers: see `tests/mocks/providers.py` and how contract tests expect success/timeout/error flows.

## Problem Statement
`QueueWorker` cannot dispatch jobs to the correct provider because:
1. `ServiceRegistry` (and the DI container) lack registrations for provider factories/adapters.
2. `QueueWorker` is not wired with `SlotService` (or an equivalent resolver) to obtain slot configuration and provider metadata.
3. `dispatch_to_provider` is effectively unimplemented: it neither prepares payloads nor orchestrates provider lifecycle (`prepare_payload → submit_job → poll_status`), nor does it persist `ProcessingLog` entries or handle timeouts/cancellations per specs.

These gaps block Phase 4 tasks 4.3.x (worker execution, logging, TTL enforcement, metrics) and contradict the behavior described in the roadmap and blueprints.

## Success Criteria
Implement the full provider dispatch pipeline so that:
- `QueueWorker` resolves slot + provider configuration using `SlotService` and provider registry.
- Provider adapters (Gemini, Turbotext, etc.) are registered in the DI container via `ServiceRegistry`, with clear factory signatures and configuration sourcing (`configs/providers.json`, env overrides).
- `QueueWorker.dispatch_to_provider` executes the provider contract lifecycle: payload preparation, submission, status polling, cancellation on timeout, and logging results/errors.
- Processing outcomes update `JobService`/`JobRepository` consistently (statuses, `result_inline_base64`, storage paths, TTL timestamps) according to domain rules and ADRs.
- All relevant tests are added/updated: integration tests for worker success, timeout, provider error, and cancellation; unit tests for helper logic if added.
- Documentation and comments reflect the new DI wiring and worker behavior; TODOs are resolved or justified.

## Detailed Requirements
1. **Service Registry & DI**
   - Extend `ServiceRegistry` (or introduce a dedicated provider registry) to register provider adapter factories keyed by `provider_id`.
   - Ensure configuration objects (`ProviderConfig`, API keys, timeouts) come from a single source of truth (likely `AppConfig` or `configs/providers.json`).
   - Update DI container assembly so that `QueueWorker`, `JobService`, `SlotService`, storage, and provider adapters share consistent lifetimes.
   - Avoid circular dependencies and keep constructors explicit.

2. **Queue Worker Flow**
   - Inject required services into `QueueWorker`: `SlotService`, provider resolver, `JobService`, `MediaService`, etc.
   - Implement `dispatch_to_provider(job)` to:
     1. Resolve slot & provider metadata.
     2. Build `ProviderOperation`/payload via `ProviderAdapter.prepare_payload`.
     3. Call `submit_job`, then `poll_status` until completion/timeout per deadlines.
     4. Handle cancellation (call `cancel_job`) when TTL/deadline breaches occur.
     5. Persist `ProcessingLog` entries for each significant state change.
     6. Persist results in storage + inline base64 per domain rules, clear inline data after response when required.
   - Respect timeouts/deadlines from `domain.deadlines` (use existing helpers or implement missing logic).
   - Record metrics (duration, provider stats) if hooks exist; otherwise leave TODO with rationale.

3. **Error Handling**
   - Translate provider exceptions into domain-level statuses (e.g., `JobStatus.PROVIDER_ERROR`, `JobStatus.TIMEOUT`, `JobStatus.CANCELLED`).
   - Guarantee idempotent behavior if the worker restarts mid-processing (re-fetch job state, avoid duplicate submissions).
   - Ensure transactional updates or compensating actions to avoid inconsistent states.

4. **Testing**
   - Update/extend integration tests under `tests/integration/` to cover: happy path, provider timeout, provider error, manual cancellation.
   - Reuse mocks in `tests/mocks/providers.py`; add scenarios if missing.
   - Ensure contract tests that touch worker behavior remain green.
   - Run `pytest -m "unit or integration"`, `pytest -m contract`, and the project pre-commit checks from `.memory/CONTEXT.md`.

5. **Documentation & Artifacts**
   - Update `.memory/WORKLOG.md`, `.memory/TASKS.md`, `.memory/PROGRESS.md`, `.memory/ASKS.md`, and any ADRs/INDEX entries if scope dictates.
   - If new architectural decisions are made (e.g., provider registry patterns), document them via ADR.
   - Sync `README.md` or Docs if commands/configuration changed.

## Deliverables
- Updated source/tests implementing DI + worker dispatch fixes.
- Passing automated tests (`pytest` suites, linters per context instructions).
- Documentation/ADR/memory updates reflecting the changes.
- PR message summarizing the fixes and tests.

## Constraints & Quality Bar
- Follow existing code style and typing (mypy-compatible, use dataclasses/pydantic as established).
- No silent exception swallowing; log meaningfully.
- Keep functions small and cohesive; extract helpers if logic becomes complex.
- Ensure provider secrets/config remain outside the codebase (use env vars/config files referenced in CONTEXT).
- Maintain backward compatibility for contracts unless explicitly updated in specs.

## References
- `.memory/CONTEXT.md` — tooling, quality gates, pre-commit checklist.
- `.memory/TASKS.md` — Phase 4 task list, especially section 4.3.
- `spec/contracts/openapi.yaml` — authoritative API spec.
- `Docs/providers/gemini.md`, `Docs/providers/turbotext.md` — provider-specific constraints.
- `tests/mocks/providers.py` — expected provider behaviors in tests.
- `src/app/infrastructure/di/*` — current DI container setup.

Deliver a cohesive implementation plan and code changes that make the queue worker fully operational with real provider selection.
