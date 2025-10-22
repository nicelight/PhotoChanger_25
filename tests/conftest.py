"""Common pytest fixtures for PhotoChanger contract testing.

The module keeps ``sys.path`` configured for the scaffolding tests and provides
stubbed infrastructure objects (ingest queue, media storage) together with
helpers for patching FastAPI routers that are still represented by 501
responses.  Contract tests rely on these fixtures to build deterministic
payloads that align with ``spec/contracts`` schemas without touching the
production code.
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from importlib import import_module
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCHEMAS_ROOT = PROJECT_ROOT / "spec" / "contracts" / "schemas"

import pytest  # noqa: E402  (import after sys.path update)

try:  # noqa: E402  (import after sys.path update)
    import psycopg
    from psycopg import conninfo, sql
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    psycopg = None  # type: ignore[assignment]
    conninfo = None  # type: ignore[assignment]
    sql = None  # type: ignore[assignment]

PSYCOPG_MISSING_REASON = "psycopg is required for PostgreSQL queue tests"


def _require_psycopg() -> None:
    """Skip PostgreSQL-dependent tests when psycopg is unavailable."""

    if psycopg is None or conninfo is None or sql is None:
        pytest.skip(PSYCOPG_MISSING_REASON, allow_module_level=True)


@pytest.fixture
def anyio_backend() -> str:
    """Force AnyIO-based tests to run on asyncio without requiring trio."""

    return "asyncio"

try:  # noqa: E402  (import after sys.path update)
    from alembic import command as alembic_command
    from alembic.config import Config as AlembicConfig
except Exception:  # pragma: no cover - optional dependency
    alembic_command = None  # type: ignore[assignment]
    AlembicConfig = None  # type: ignore[assignment]

try:  # noqa: E402  (import after sys.path update)
    from tests.helpers.public_results import (
        register_finalized_job,
    )
except ModuleNotFoundError:  # pragma: no cover - optional FastAPI dependency
    def register_finalized_job(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        pytest.skip("fastapi is required for public results helpers")


from tests.mocks.providers import (  # noqa: E402  (import after sys.path update)
    MockGeminiProvider,
    MockProviderScenario,
    MockTurbotextProvider,
    MockProviderConfig,
)


class SchemaLoader:
    """Utility that loads JSON Schemas and resolves local references."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._cache: Dict[Path, Dict[str, Any]] = {}

    def load(self, schema_name: str) -> tuple[Dict[str, Any], Path]:
        """Return a schema dictionary together with its absolute path."""

        path = (self._root / schema_name).resolve()
        return self._load_from_path(path)

    def resolve_ref(self, ref: str, base_path: Path) -> tuple[Dict[str, Any], Path]:
        """Resolve a ``$ref`` relative to ``base_path``."""

        if ref.startswith("#"):
            raise AssertionError("In-document references are not supported in tests")
        path = (base_path.parent / ref).resolve()
        return self._load_from_path(path)

    def _load_from_path(self, path: Path) -> tuple[Dict[str, Any], Path]:
        if path not in self._cache:
            self._cache[path] = json.loads(path.read_text(encoding="utf-8"))
        return dict(self._cache[path]), path


class SimpleSchemaValidator:
    """Minimal JSON Schema validator tailored for the contract fixtures."""

    def __init__(self, loader: SchemaLoader) -> None:
        self._loader = loader

    def __call__(self, payload: Any, schema_name: str) -> None:
        """Validate ``payload`` against ``schema_name`` or raise ``AssertionError``."""

        schema, path = self._loader.load(schema_name)
        self._validate(payload, schema, path, pointer="$")

    def _validate(
        self, value: Any, schema: Dict[str, Any], path: Path, pointer: str
    ) -> None:
        schema, path = self._dereference(schema, path)

        if "allOf" in schema:
            for index, sub_schema in enumerate(schema["allOf"]):
                merged, sub_path = self._dereference(dict(sub_schema), path)
                self._validate(value, merged, sub_path, pointer)

        if "anyOf" in schema:
            errors = []
            for sub_schema in schema["anyOf"]:
                try:
                    merged, sub_path = self._dereference(dict(sub_schema), path)
                    self._validate(value, merged, sub_path, pointer)
                except AssertionError as exc:  # pragma: no cover - informative branch
                    errors.append(str(exc))
                else:
                    break
            else:
                joined = "; ".join(errors) if errors else "no matching schema"
                raise AssertionError(
                    f"{pointer}: value {value!r} does not match anyOf ({joined})"
                )
            schema = {k: v for k, v in schema.items() if k != "anyOf"}

        schema_type = schema.get("type")
        if schema_type is not None:
            self._assert_type(value, schema_type, pointer)

        if "enum" in schema and value not in schema["enum"]:
            raise AssertionError(f"{pointer}: {value!r} not in enum {schema['enum']!r}")

        if "const" in schema and value != schema["const"]:
            raise AssertionError(f"{pointer}: {value!r} != const {schema['const']!r}")

        if "pattern" in schema:
            if (
                not isinstance(value, str)
                or re.search(schema["pattern"], value) is None
            ):
                raise AssertionError(
                    f"{pointer}: {value!r} does not satisfy pattern {schema['pattern']!r}"
                )

        if "minimum" in schema:
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or value < schema["minimum"]
            ):
                raise AssertionError(
                    f"{pointer}: {value!r} is below minimum {schema['minimum']!r}"
                )

        if "format" in schema:
            self._validate_format(value, schema["format"], pointer)

        if (
            isinstance(schema.get("type"), (list, tuple))
            and "null" in schema["type"]
            and value is None
        ):
            return

        if schema.get("type") == "null" and value is None:
            return

        if (
            schema.get("type") == "object"
            or (isinstance(schema.get("type"), list) and "object" in schema["type"])
            or ("properties" in schema and isinstance(value, dict))
        ):
            self._validate_object(value, schema, path, pointer)
        elif schema.get("type") == "array" or (
            isinstance(schema.get("type"), list) and "array" in schema["type"]
        ):
            self._validate_array(value, schema, path, pointer)

    def _validate_object(
        self, value: Any, schema: Dict[str, Any], path: Path, pointer: str
    ) -> None:
        if not isinstance(value, dict):
            raise AssertionError(
                f"{pointer}: expected object, got {type(value).__name__}"
            )

        required = schema.get("required", [])
        for key in required:
            if key not in value:
                raise AssertionError(f"{pointer}: missing required property {key!r}")

        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)

        for key, item in value.items():
            if key in properties:
                merged, sub_path = self._dereference(dict(properties[key]), path)
                self._validate(item, merged, sub_path, f"{pointer}/{key}")
            else:
                if additional is False:
                    raise AssertionError(
                        f"{pointer}: additional property {key!r} is not allowed"
                    )
                if isinstance(additional, dict):
                    merged, sub_path = self._dereference(dict(additional), path)
                    self._validate(item, merged, sub_path, f"{pointer}/{key}")

    def _validate_array(
        self, value: Any, schema: Dict[str, Any], path: Path, pointer: str
    ) -> None:
        if not isinstance(value, list):
            raise AssertionError(
                f"{pointer}: expected array, got {type(value).__name__}"
            )

        if "minItems" in schema and len(value) < schema["minItems"]:
            raise AssertionError(
                f"{pointer}: expected at least {schema['minItems']} items, got {len(value)}"
            )

        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise AssertionError(
                f"{pointer}: expected at most {schema['maxItems']} items, got {len(value)}"
            )

        items_schema = schema.get("items")
        if isinstance(items_schema, dict):
            for index, item in enumerate(value):
                merged, sub_path = self._dereference(dict(items_schema), path)
                self._validate(item, merged, sub_path, f"{pointer}/{index}")

    def _assert_type(self, value: Any, declared: Any, pointer: str) -> None:
        allowed = declared if isinstance(declared, (list, tuple)) else [declared]
        for entry in allowed:
            if self._matches_type(value, entry):
                return
        raise AssertionError(f"{pointer}: {value!r} does not satisfy type {allowed!r}")

    def _matches_type(self, value: Any, entry: str) -> bool:
        if entry == "object":
            return isinstance(value, dict)
        if entry == "array":
            return isinstance(value, list)
        if entry == "string":
            return isinstance(value, str)
        if entry == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if entry == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if entry == "boolean":
            return isinstance(value, bool)
        if entry == "null":
            return value is None
        return False

    def _validate_format(self, value: Any, fmt: str, pointer: str) -> None:
        if fmt == "date-time":
            if not isinstance(value, str):
                raise AssertionError(f"{pointer}: expected string for date-time format")
            candidate = value.replace("Z", "+00:00")
            try:
                datetime.fromisoformat(candidate)
            except ValueError as exc:
                raise AssertionError(f"{pointer}: invalid date-time {value!r}") from exc
        elif fmt == "date":
            if not isinstance(value, str):
                raise AssertionError(f"{pointer}: expected string for date format")
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise AssertionError(f"{pointer}: invalid date {value!r}") from exc
        elif fmt == "uuid":
            if not isinstance(value, str):
                raise AssertionError(f"{pointer}: expected string for uuid format")
            try:
                uuid.UUID(value)
            except (ValueError, AttributeError) as exc:
                raise AssertionError(f"{pointer}: invalid uuid {value!r}") from exc
        elif fmt == "uri":
            if not isinstance(value, str):
                raise AssertionError(f"{pointer}: expected string for uri format")
            parsed = urlparse(value)
            if not (parsed.scheme and parsed.netloc):
                raise AssertionError(f"{pointer}: invalid uri {value!r}")

    def _dereference(
        self, schema: Dict[str, Any], path: Path
    ) -> tuple[Dict[str, Any], Path]:
        if "$ref" not in schema:
            return schema, path
        ref = schema["$ref"]
        ref_schema, ref_path = self._loader.resolve_ref(ref, path)
        merged = dict(ref_schema)
        merged.update({k: v for k, v in schema.items() if k != "$ref"})
        return self._dereference(merged, ref_path)


import pytest  # noqa: E402  (import after helper definitions)

from src.app.infrastructure.queue.postgres import (  # noqa: E402
    PostgresJobQueue,
    PostgresQueueConfig,
)


def _resolve_postgres_dsn() -> str:
    _require_psycopg()
    env_dsn = os.getenv("TEST_POSTGRES_DSN")
    if env_dsn:
        return env_dsn
    params: dict[str, object] = {
        "host": os.getenv("TEST_POSTGRES_HOST", "localhost"),
        "port": os.getenv("TEST_POSTGRES_PORT", "5432"),
        "dbname": os.getenv("TEST_POSTGRES_DB", "photochanger_test"),
        "user": os.getenv("TEST_POSTGRES_USER", "postgres"),
        "password": os.getenv("TEST_POSTGRES_PASSWORD", "postgres"),
    }
    return conninfo.make_conninfo(**params)


def _ensure_database_exists(dsn: str) -> None:
    _require_psycopg()
    params = conninfo.conninfo_to_dict(dsn)
    dbname = params.get("dbname")
    if not dbname:
        raise RuntimeError("PostgreSQL DSN must include a database name")
    admin_dsn = conninfo.make_conninfo(
        host=params.get("host") or "localhost",
        port=params.get("port") or "5432",
        user=params.get("user"),
        password=params.get("password"),
        dbname=os.getenv("TEST_POSTGRES_TEMPLATE_DB", "postgres"),
    )
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
            if cur.fetchone() is None:
                cur.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname))
                )


_applied_migrations: set[str] = set()


def _apply_queue_migrations(dsn: str) -> None:
    if alembic_command is None or AlembicConfig is None:
        import pytest

        pytest.skip("Alembic is required for PostgreSQL queue tests")
    if dsn in _applied_migrations:
        return
    config = AlembicConfig(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", dsn)
    alembic_command.upgrade(config, "head")
    _applied_migrations.add(dsn)


def _truncate_postgres_tables(dsn: str) -> None:
    _require_psycopg()
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                  AND tablename IN ('processing_logs', 'processing_log_aggregates', 'jobs')
                ORDER BY tablename
                """
            )
            tables = [sql.Identifier("public", row[0]) for row in cur.fetchall()]
            if not tables:
                return
            cur.execute(
                sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(
                    sql.SQL(", ").join(tables)
                )
            )


@pytest.fixture(scope="session")
def postgres_dsn() -> Iterator[str]:
    _require_psycopg()
    dsn = _resolve_postgres_dsn()
    try:
        _ensure_database_exists(dsn)
    except psycopg.OperationalError as exc:  # pragma: no cover - environment guard
        pytest.skip(f"PostgreSQL unavailable for tests: {exc}")
    yield dsn


@pytest.fixture
def postgres_queue_factory(postgres_dsn: str) -> Iterator[Callable[..., PostgresJobQueue]]:
    created: list[PostgresJobQueue] = []

    def _factory(**overrides: object) -> PostgresJobQueue:
        _truncate_postgres_tables(postgres_dsn)
        _apply_queue_migrations(postgres_dsn)
        config_kwargs: dict[str, object] = {"dsn": postgres_dsn}
        config_kwargs.update(overrides)
        config = PostgresQueueConfig(**config_kwargs)
        queue = PostgresJobQueue(config=config)
        created.append(queue)
        return queue

    yield _factory

    for queue in created:
        backend = getattr(queue, "_backend", None)
        connection = getattr(backend, "_conn", None)
        if connection is not None:
            connection.close()
    _truncate_postgres_tables(postgres_dsn)


@pytest.fixture
def postgres_queue(postgres_queue_factory: Callable[..., PostgresJobQueue]) -> Iterator[PostgresJobQueue]:
    queue = postgres_queue_factory()
    yield queue

try:  # pragma: no cover - guard for environments without FastAPI
    from fastapi import Response
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    Response = None  # type: ignore[assignment]
    TestClient = None  # type: ignore[assignment]
    FASTAPI_MISSING_REASON = "FastAPI is required for contract tests"
else:
    FASTAPI_MISSING_REASON = ""


def _require_fastapi() -> None:
    if Response is None or TestClient is None:
        pytest.skip(FASTAPI_MISSING_REASON, allow_module_level=True)


def _require_app_config() -> None:
    if AppConfig is None:
        pytest.skip("pydantic is required for AppConfig", allow_module_level=True)

try:  # noqa: E402  (import after optional FastAPI dependency)
    from src.app.core.app import create_app
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
    if exc.name != "fastapi":
        raise
    create_app = None  # type: ignore[assignment]

try:  # noqa: E402  (import after optional FastAPI dependency)
    from src.app.core.config import AppConfig
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
    if exc.name != "pydantic":
        raise
    AppConfig = None  # type: ignore[assignment]
from src.app.domain.models import Job, ProcessingLog  # noqa: E402
from src.app.services.job_service import QueueBusyError, QueueUnavailableError  # noqa: E402
from src.app.services.registry import ServiceRegistry  # noqa: E402


# ---------------------------------------------------------------------------
# In-memory infrastructure doubles
# ---------------------------------------------------------------------------


@dataclass
class FakeJobQueue:
    """In-memory collection that stores Job records for contract tests."""

    jobs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    domain_jobs: Dict[str, Job] = field(default_factory=dict)
    processing_logs: Dict[str, list[ProcessingLog]] = field(default_factory=dict)
    raise_busy: bool = False
    raise_unavailable: bool = False
    auto_finalize_inline: bytes | None = None
    auto_finalize_mime: str = "image/jpeg"

    def register(self, job: Dict[str, Any]) -> None:
        """Persist a Job payload so tests can reuse its deadline metadata."""

        self.jobs[job["id"]] = job

    def get(self, job_id: str) -> Dict[str, Any]:
        """Return a previously registered Job by identifier."""

        return self.jobs[job_id]

    @staticmethod
    def _iso(dt: datetime | None) -> str | None:
        if dt is None:
            return None
        return (
            dt.astimezone(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

    def _snapshot(self, job: Job) -> Dict[str, Any]:
        return {
            "id": str(job.id),
            "slot_id": job.slot_id,
            "status": job.status.value,
            "is_finalized": job.is_finalized,
            "failure_reason": job.failure_reason.value if job.failure_reason else None,
            "provider_job_reference": job.provider_job_reference,
            "payload_path": job.payload_path,
            "result_file_path": job.result_file_path,
            "result_inline_base64": job.result_inline_base64,
            "result_mime_type": job.result_mime_type,
            "result_size_bytes": job.result_size_bytes,
            "result_checksum": job.result_checksum,
            "result_expires_at": self._iso(job.result_expires_at),
            "expires_at": self._iso(job.expires_at),
            "created_at": self._iso(job.created_at),
            "updated_at": self._iso(job.updated_at),
            "finalized_at": self._iso(job.finalized_at),
        }

    def _store(self, job: Job) -> None:
        job_id = str(job.id)
        self.domain_jobs[job_id] = job
        self.jobs[job_id] = self._snapshot(job)

    def enqueue(self, job: Job) -> Job:
        """Store an enqueued job for later inspection."""

        if self.raise_busy:
            raise QueueBusyError("queue saturated")
        if self.raise_unavailable:
            raise QueueUnavailableError("queue unavailable")

        self._store(job)
        job_id = str(job.id)
        if self.auto_finalize_inline is not None:
            self.finalize_inline(
                job_id, self.auto_finalize_inline, mime=self.auto_finalize_mime
            )
        return job

    def list_recent_results(
        self,
        slot_id: str,
        *,
        limit: int,
        since: datetime,
    ) -> list[Job]:
        jobs = [
            job
            for job in self.domain_jobs.values()
            if job.slot_id == slot_id
            and job.is_finalized
            and job.failure_reason is None
            and job.finalized_at is not None
            and job.result_file_path is not None
            and job.result_mime_type is not None
            and job.result_expires_at is not None
            and job.finalized_at >= since
        ]
        jobs.sort(key=lambda item: item.finalized_at or item.updated_at, reverse=True)
        return jobs[:limit]

    def finalize_inline(
        self, job_id: str, payload: bytes, *, mime: str = "image/jpeg"
    ) -> None:
        """Mark a job as finalized with an inline base64 payload."""

        job = self.domain_jobs[job_id]
        job.is_finalized = True
        job.failure_reason = None
        job.result_inline_base64 = base64.b64encode(payload).decode("ascii")
        job.result_mime_type = mime
        job.result_size_bytes = len(payload)
        job.updated_at = datetime.now(timezone.utc)
        job.finalized_at = job.updated_at
        self._store(job)

    def append_processing_logs(
        self, entries: Iterable[ProcessingLog]
    ) -> None:  # pragma: no cover - simple storage
        for entry in entries:
            job_id = str(entry.job_id)
            self.processing_logs.setdefault(job_id, []).append(entry)


@dataclass
class FakeResultStore:
    """Simple map of Job identifiers to public result descriptors."""

    results: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def store(self, job_id: str, result: Dict[str, Any]) -> None:
        """Associate Job results with a job id for reuse across tests."""

        self.results[job_id] = result

    def get(self, job_id: str) -> Dict[str, Any]:
        """Return stored result metadata for the given job id."""

        return self.results[job_id]


@pytest.fixture(params=list(MockProviderScenario), ids=lambda scenario: scenario.value)
def mock_gemini_provider(request) -> MockGeminiProvider:
    """Return a configured Gemini mock for the requested scenario."""

    scenario: MockProviderScenario = request.param
    config = MockProviderConfig(
        scenario=scenario,
        timeout_polls=2,
        error_code="RESOURCE_EXHAUSTED",
        error_message="Quota exceeded for mock Gemini project",
    )
    return MockGeminiProvider(config)


@pytest.fixture(params=list(MockProviderScenario), ids=lambda scenario: scenario.value)
def mock_turbotext_provider(request) -> MockTurbotextProvider:
    """Return a configured Turbotext mock for the requested scenario."""

    scenario: MockProviderScenario = request.param
    config = MockProviderConfig(
        scenario=scenario,
        timeout_polls=2,
        error_code="INVALID_IMAGE_FORMAT",
        error_message="Unsupported image format supplied to mock Turbotext",
    )
    return MockTurbotextProvider(config)


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_job_queue() -> FakeJobQueue:
    """Provide a fake ingest queue used to capture job deadlines."""

    return FakeJobQueue()


@pytest.fixture
def fake_result_store() -> FakeResultStore:
    """Provide an in-memory result storage with TTL-aware metadata."""

    return FakeResultStore()


@pytest.fixture
def contract_app(
    fake_job_queue: FakeJobQueue,
    fake_result_store: FakeResultStore,
    tmp_path,
):
    """Instantiate the FastAPI application with fake infrastructure state."""

    _require_fastapi()
    _require_app_config()
    if create_app is None:
        pytest.skip(FASTAPI_MISSING_REASON or "FastAPI create_app unavailable")
    app_config = AppConfig(media_root=tmp_path / "media")
    extra_state = {
        "job_queue": fake_job_queue,
        "result_store": fake_result_store,
        "app_config": app_config,
        "disable_worker_pool": True,
    }
    app = create_app(extra_state=extra_state)

    # Reduce the synchronous response timeout to keep tests fast.
    registry: ServiceRegistry = app.state.service_registry  # type: ignore[attr-defined]
    settings_service = registry.resolve_settings_service()(config=app.state.config)
    settings = settings_service.get_settings()
    settings.ingest.sync_response_timeout_sec = 1
    settings.ingest.ingest_ttl_sec = 1
    settings.media_cache.public_link_ttl_sec = 1

    # Ensure static stats routes have priority over dynamic slot routes for tests.
    routes = app.router.routes
    global_route = next(
        (
            route
            for route in routes
            if getattr(route, "path", None) == "/api/stats/global"
        ),
        None,
    )
    slot_route = next(
        (
            route
            for route in routes
            if getattr(route, "path", None) == "/api/stats/{slot_id}"
        ),
        None,
    )
    if global_route and slot_route:
        global_index = routes.index(global_route)
        slot_index = routes.index(slot_route)
        if global_index > slot_index:
            routes.insert(slot_index, routes.pop(global_index))

    return app


@pytest.fixture
def contract_client(contract_app):
    """Return a ``TestClient`` bound to the contract-testing FastAPI app."""

    _require_fastapi()
    with TestClient(contract_app) as client:
        yield client


@dataclass(slots=True)
class PublicResultCase:
    job: Job
    public_url: str
    expires_at: datetime
    media_path: Path


@pytest.fixture
def fresh_public_result(contract_app) -> PublicResultCase:
    """Register a finalized job whose public link is still valid."""

    finalized_at = datetime.now(timezone.utc)
    job, public_url, expires_at = register_finalized_job(
        contract_app, finalized_at=finalized_at
    )
    assert job.result_file_path is not None
    media_root: Path = contract_app.state.config.media_root
    media_path = media_root / job.result_file_path
    assert media_path.exists()
    return PublicResultCase(
        job=job,
        public_url=public_url,
        expires_at=expires_at,
        media_path=media_path,
    )


@pytest.fixture
def expired_public_result(contract_app) -> PublicResultCase:
    """Register a finalized job whose TTL already elapsed."""

    registry: ServiceRegistry = contract_app.state.service_registry  # type: ignore[attr-defined]
    job_service = registry.resolve_job_service()(config=contract_app.state.config)
    retention_hours = job_service.result_retention_hours
    finalized_at = datetime.now(timezone.utc) - timedelta(
        hours=retention_hours + 1
    )
    job, public_url, expires_at = register_finalized_job(
        contract_app, finalized_at=finalized_at
    )
    assert job.result_file_path is not None
    media_root: Path = contract_app.state.config.media_root
    media_path = media_root / job.result_file_path
    assert media_path.exists()
    return PublicResultCase(
        job=job,
        public_url=public_url,
        expires_at=expires_at,
        media_path=media_path,
    )


# ---------------------------------------------------------------------------
# Sample data fixtures aligned with JSON Schemas
# ---------------------------------------------------------------------------


def _isoformat(dt: datetime) -> str:
    """Serialize a timezone-aware ``datetime`` to RFC 3339 format."""

    return (
        dt.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


@pytest.fixture
def sample_job(fake_job_queue: FakeJobQueue) -> Dict[str, Any]:
    """Return a Job record with consistent ingest and result deadlines."""

    created = datetime(2025, 10, 18, 10, 0, 0, tzinfo=timezone.utc)
    expires = created + timedelta(seconds=55)
    result_expires = created + timedelta(hours=72)
    job = {
        "id": "11111111-2222-3333-4444-555555555555",
        "slot_id": "slot-001",
        "status": "processing",
        "is_finalized": False,
        "failure_reason": None,
        "provider_job_reference": "provider-ref-001",
        "payload_path": "/tmp/payloads/job-1",
        "result_file_path": None,
        "result_inline_base64": None,
        "result_mime_type": None,
        "result_size_bytes": None,
        "result_checksum": None,
        "result_expires_at": _isoformat(result_expires),
        "expires_at": _isoformat(expires),
        "created_at": _isoformat(created),
        "updated_at": _isoformat(created + timedelta(seconds=1)),
        "finalized_at": None,
    }
    fake_job_queue.register(job)
    return job


@pytest.fixture
def expired_job(fake_job_queue: FakeJobQueue) -> Dict[str, Any]:
    """Return a Job payload representing an already expired ingest deadline."""

    created = datetime(2025, 10, 18, 9, 0, 0, tzinfo=timezone.utc)
    expires = created + timedelta(seconds=50)
    job = {
        "id": "99999999-8888-7777-6666-555555555555",
        "slot_id": "slot-001",
        "status": "processing",
        "is_finalized": False,
        "failure_reason": "timeout",
        "provider_job_reference": "provider-ref-expired",
        "payload_path": "/tmp/payloads/job-expired",
        "result_file_path": None,
        "result_inline_base64": None,
        "result_mime_type": None,
        "result_size_bytes": None,
        "result_checksum": None,
        "result_expires_at": None,
        "expires_at": _isoformat(expires),
        "created_at": _isoformat(created),
        "updated_at": _isoformat(created + timedelta(seconds=50)),
        "finalized_at": _isoformat(created + timedelta(seconds=50)),
    }
    fake_job_queue.register(job)
    return job


@pytest.fixture
def sample_result(
    sample_job: Dict[str, Any], fake_result_store: FakeResultStore
) -> Dict[str, Any]:
    """Return result metadata pointing to the sample job's public link."""

    result = {
        "job_id": sample_job["id"],
        "thumbnail_url": "https://cdn.photochanger.local/thumbs/sample.jpg",
        "download_url": f"https://cdn.photochanger.local/results/{sample_job['id']}",
        "completed_at": sample_job["created_at"],
        "result_expires_at": sample_job["result_expires_at"],
        "mime": "image/jpeg",
        "size_bytes": 1024,
    }
    fake_result_store.store(sample_job["id"], result)
    return result


@pytest.fixture
def expired_result(fake_result_store: FakeResultStore) -> Dict[str, Any]:
    """Provide metadata for a public result whose TTL already elapsed."""

    job_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    result = {
        "job_id": job_id,
        "thumbnail_url": "https://cdn.photochanger.local/thumbs/expired.jpg",
        "download_url": f"https://cdn.photochanger.local/results/{job_id}",
        "completed_at": "2025-10-10T10:00:00Z",
        "result_expires_at": "2025-10-13T10:00:00Z",
        "mime": "image/png",
        "size_bytes": 2048,
    }
    fake_result_store.store(job_id, result)
    return result


@pytest.fixture
def sample_slot(sample_result: Dict[str, Any]) -> Dict[str, Any]:
    """Return slot metadata enriched with the sample recent result list."""

    return {
        "id": "slot-001",
        "name": "Portrait Enhancer",
        "provider_id": "gemini-pro",
        "operation_id": "portrait-v2",
        "settings_json": {"prompt": "enhance portrait lighting"},
        "last_reset_at": "2025-10-17T12:00:00Z",
        "created_at": "2025-10-01T09:00:00Z",
        "updated_at": "2025-10-18T08:00:00Z",
        "recent_results": [sample_result],
    }


@pytest.fixture
def sample_slot_list(sample_slot: Dict[str, Any]) -> Dict[str, Any]:
    """Return a list response for ``GET /api/slots`` with metadata total=1."""

    return {"data": [sample_slot], "meta": {"total": 1}}


@pytest.fixture
def sample_settings(sample_job: Dict[str, Any]) -> Dict[str, Any]:
    """Return platform settings with TTL parameters derived from the job."""

    sync_timeout = 55
    return {
        "dslr_password": {
            "is_set": True,
            "updated_at": "2025-10-15T12:00:00Z",
            "updated_by": "admin",
        },
        "provider_keys": {
            "gemini-pro": {
                "is_configured": True,
                "updated_at": "2025-10-15T12:30:00Z",
                "updated_by": "admin",
                "project_id": "photochanger-lab",
            }
        },
        "ingest": {
            "sync_response_timeout_sec": sync_timeout,
            "ingest_ttl_sec": sync_timeout,
        },
        "media_cache": {
            "processed_media_ttl_hours": 72,
            "public_link_ttl_sec": sync_timeout,
        },
    }


@pytest.fixture
def sample_slot_stats() -> Dict[str, Any]:
    """Return slot-scoped statistics for the default slot."""

    return {
        "slot_id": "slot-001",
        "range": {"from": "2025-10-10", "to": "2025-10-17", "group_by": "day"},
        "summary": {
            "title": "Portrait Enhancer",
            "success": 42,
            "timeouts": 1,
            "provider_errors": 2,
            "cancelled": 0,
            "errors": 3,
            "ingest_count": 45,
            "last_reset_at": "2025-10-17T12:00:00Z",
        },
        "metrics": [
            {
                "period_start": "2025-10-16",
                "period_end": "2025-10-16",
                "success": 6,
                "timeouts": 0,
                "provider_errors": 1,
                "cancelled": 0,
                "errors": 1,
                "ingest_count": 7,
            }
        ],
    }


@pytest.fixture
def sample_global_stats() -> Dict[str, Any]:
    """Return aggregated statistics payload for ``/api/stats/global``."""

    return {
        "summary": {
            "total_runs": 120,
            "timeouts": 3,
            "provider_errors": 5,
            "cancelled": 1,
            "errors": 6,
            "ingest_count": 120,
        },
        "data": [
            {
                "period_start": "2025-10-10",
                "period_end": "2025-10-16",
                "success": 80,
                "timeouts": 2,
                "provider_errors": 3,
                "cancelled": 1,
                "errors": 4,
                "ingest_count": 90,
            }
        ],
        "meta": {"page": 1, "page_size": 10, "total": 1},
    }


# ---------------------------------------------------------------------------
# Schema helpers and router patching utilities
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def schema_loader() -> SchemaLoader:
    """Expose a shared schema loader for contract tests."""

    return SchemaLoader(SCHEMAS_ROOT)


@pytest.fixture
def load_contract_schema(
    schema_loader: SchemaLoader,
) -> Callable[[str], Dict[str, Any]]:
    """Return a loader that reads JSON Schemas from ``spec/contracts``."""

    def _load(schema_name: str) -> Dict[str, Any]:
        schema, _ = schema_loader.load(schema_name)
        return schema

    return _load


@pytest.fixture
def validate_with_schema(
    schema_loader: SchemaLoader,
) -> Callable[[Dict[str, Any], str], None]:
    """Return a helper that validates payloads against JSON Schemas."""

    validator = SimpleSchemaValidator(schema_loader)

    def _validate(payload: Dict[str, Any], schema_name: str) -> None:
        validator(payload, schema_name)

    return _validate


@pytest.fixture
def patch_endpoint_response(
    monkeypatch,
) -> Callable[[str, str, Callable[[], Response] | Response], None]:
    """Patch ``endpoint_not_implemented`` for a router module with a stub."""

    _require_fastapi()
    def _patch(
        module_path: str,
        operation: str,
        response_factory: Callable[[], Response] | Response,
    ) -> None:
        module = import_module(module_path)

        def _stub(received_operation: str) -> Response:
            assert received_operation == operation, (
                f"unexpected operation {received_operation!r} requested"
            )
            if callable(response_factory):
                return response_factory()
            return response_factory

        monkeypatch.setattr(module, "endpoint_not_implemented", _stub)

    return _patch


@pytest.fixture
def patch_authentication_response(
    monkeypatch,
) -> Callable[[str, Callable[[], Response] | Response], None]:
    """Override ``authentication_not_configured`` to emit contract errors."""

    _require_fastapi()
    def _patch(
        module_path: str,
        response_factory: Callable[[], Response] | Response,
    ) -> None:
        module = import_module(module_path)

        def _stub() -> Response:
            if callable(response_factory):
                return response_factory()
            return response_factory

        monkeypatch.setattr(module, "authentication_not_configured", _stub)

    return _patch


@pytest.fixture
def allow_bearer_auth(contract_app) -> Callable[[Iterable[str]], None]:
    """Override bearer auth dependencies to return ``True`` for tests."""

    async def _allow() -> bool:
        return True

    def _apply(modules: Iterable[str]) -> None:
        from src.app.api.routes import dependencies as base_dependencies

        contract_app.dependency_overrides[
            base_dependencies.require_bearer_authentication
        ] = _allow
        for module_path in modules:
            module = import_module(module_path)
            dependency = getattr(module, "require_bearer_authentication")
            contract_app.dependency_overrides[dependency] = _allow

    return _apply


@pytest.fixture
def ingest_payload() -> Dict[str, Any]:
    """Provide form-encoded ingest payload compatible with the stub schema."""

    image_bytes = b"\xff\xd8contract-image\xff\xd9"
    filename = "contract-test.jpg"
    unsafe_filename = "contract test/../payload?.jpg"
    sanitized_filename = (
        re.sub(r"[^A-Za-z0-9_.-]", "_", Path(unsafe_filename).name) or "upload.bin"
    )
    return {
        "data": {"password": "correct-horse-battery"},
        "files": {"fileToUpload": (filename, image_bytes, "image/jpeg")},
        "files_with_unsafe_name": {
            "fileToUpload": (unsafe_filename, image_bytes, "image/jpeg")
        },
        "image_bytes": image_bytes,
        "filename": filename,
        "mime": "image/jpeg",
        "unsafe_filename": unsafe_filename,
        "sanitized_filename": sanitized_filename,
    }
