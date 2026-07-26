"""Privacy-preserving logs, metrics, tracing, and incident correlation.

The module deliberately keeps telemetry labels low-cardinality and never
records request bodies, query strings, cookies, authorization headers, email
addresses, or raw database statements. Vendor integrations are optional:
Prometheus metrics remain disabled until a dedicated bearer token is set,
OpenTelemetry exports only when an OTLP endpoint is configured, and Sentry
receives errors only when a DSN is configured.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import re
import sys
import time
import traceback
import uuid
import weakref
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import sentry_sdk
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
    OTLPMetricExporter,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.trace import SpanKind, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import (
    TraceContextTextMapPropagator,
)
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from sqlalchemy import event
from sqlalchemy.engine import Engine
from starlette.datastructures import MutableHeaders
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.version import __version__, git_sha

if TYPE_CHECKING:
    from api.config import Settings


_request_id: ContextVar[str | None] = ContextVar(
    "mouvadah_request_id",
    default=None,
)
_event_fields: ContextVar[dict[str, Any] | None] = ContextVar(
    "mouvadah_event_fields",
    default=None,
)
_deployment_environment = "local"
_tracer_provider: TracerProvider | None = None
_meter_provider: MeterProvider | None = None
_otel_job_runs = None
_otel_job_duration = None
_sentry_initialized = False
_instrumented_engines: weakref.WeakSet[Engine] = weakref.WeakSet()

_SAFE_EVENT_FIELD = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SECRET_KEY = re.compile(
    r"(authorization|cookie|password|passwd|secret|token|api.?key|"
    r"credential|session|jwt|dsn)",
    re.IGNORECASE,
)
_BEARER_VALUE = re.compile(
    r"(?i)\b(bearer)\s+[a-z0-9._~+/=-]+",
)
_URI_PASSWORD = re.compile(r"(://[^:/@\s]+:)[^@\s]+(@)")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|authorization|"
    r"cookie|session|jwt|dsn)(\s*[:=]\s*)"
    r"(\"[^\"]*\"|'[^']*'|[^\s,;&]+)"
)
_QUERY_SECRET = re.compile(
    r"(?i)([?&](?:access_token|token|api[_-]?key|password|secret)=)"
    r"[^&\s]+"
)
_HTTP_URL_QUERY = re.compile(r"(https?://[^\s?#]+)\?[^\s#]+", re.IGNORECASE)
_EMAIL_ADDRESS = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@"
    r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![A-Za-z0-9.-])"
)
_SQL_OPERATION = re.compile(r"^\s*([A-Za-z]+)")
_UNSAFE_LOGGER_PREFIXES = (
    "httpcore",
    "httpx",
    "sqlalchemy.engine",
    "sqlalchemy.pool",
)


HTTP_REQUESTS = Counter(
    "mouvadah_http_requests_total",
    "Completed HTTP requests.",
    ("method", "route", "status"),
)
HTTP_DURATION = Histogram(
    "mouvadah_http_request_duration_seconds",
    "HTTP request duration.",
    ("method", "route"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
)
HTTP_RESPONSE_SIZE = Histogram(
    "mouvadah_http_response_body_bytes",
    "Uncompressed HTTP response body size by route.",
    ("method", "route"),
    buckets=(
        256,
        1_024,
        4_096,
        16_384,
        65_536,
        262_144,
        1_048_576,
        4_194_304,
    ),
)
HTTP_EXCEPTIONS = Counter(
    "mouvadah_http_unhandled_exceptions_total",
    "Unhandled HTTP exceptions.",
    ("route", "error_type"),
)
AUTH_FAILURES = Counter(
    "mouvadah_auth_failures_total",
    "Authentication or authorization failures returned by the API.",
    ("status",),
)
DB_QUERIES = Counter(
    "mouvadah_database_queries_total",
    "Database operations by low-cardinality operation and outcome.",
    ("operation", "outcome"),
)
DB_DURATION = Histogram(
    "mouvadah_database_query_duration_seconds",
    "Database operation duration.",
    ("operation",),
    buckets=(0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)
DB_CONNECTIONS = Gauge(
    "mouvadah_database_connections_in_use",
    "Connections currently checked out from instrumented database pools.",
)
REALTIME_SUBSCRIBERS = Gauge(
    "mouvadah_realtime_subscribers",
    "Currently connected SSE subscribers.",
)
REALTIME_EVENTS = Counter(
    "mouvadah_realtime_events_total",
    "Realtime invalidation delivery attempts.",
    ("transport", "outcome"),
)
REALTIME_RESYNCS = Counter(
    "mouvadah_realtime_resyncs_total",
    "Explicit client resync instructions.",
    ("reason",),
)
REALTIME_RECONNECTS = Counter(
    "mouvadah_realtime_reconnect_attempts_total",
    "PostgreSQL realtime reconnect attempts.",
    ("outcome",),
)
REALTIME_HEALTH = Gauge(
    "mouvadah_realtime_transport_healthy",
    "Whether the configured realtime transport is healthy (1) or degraded (0).",
)
JOB_RUNS = Counter(
    "mouvadah_job_runs_total",
    "Operator job runs by bounded job name and outcome.",
    ("job", "outcome"),
)
JOB_DURATION = Histogram(
    "mouvadah_job_duration_seconds",
    "Operator job duration.",
    ("job",),
    buckets=(0.1, 0.5, 1, 2.5, 5, 10, 30, 60, 300, 900, 3600),
)


def current_request_id() -> str | None:
    return _request_id.get()


def current_trace_id() -> str | None:
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return None
    return format(span_context.trace_id, "032x")


def _redact_string(value: str) -> str:
    redacted = _HTTP_URL_QUERY.sub(r"\1?[REDACTED_QUERY]", value)
    redacted = _EMAIL_ADDRESS.sub("[REDACTED_EMAIL]", redacted)
    redacted = _BEARER_VALUE.sub(r"\1 [REDACTED]", redacted)
    redacted = _URI_PASSWORD.sub(r"\1[REDACTED]\2", redacted)
    redacted = _SECRET_ASSIGNMENT.sub(
        lambda match: (
            f"{match.group(1)}{match.group(2)}[REDACTED]"
        ),
        redacted,
    )
    redacted = _QUERY_SECRET.sub(r"\1[REDACTED]", redacted)
    if len(redacted) > 4096:
        return f"{redacted[:4096]}…[TRUNCATED]"
    return redacted


def redact(value: Any, *, key: str | None = None) -> Any:
    """Return a JSON-safe value with credentials and risky fields removed."""
    if (
        key is not None
        and _SECRET_KEY.search(key)
        and not key.lower().endswith("_id")
    ):
        return "[REDACTED]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _redact_string(value)
    if isinstance(value, Mapping):
        return {
            str(item_key): redact(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [redact(item) for item in value]
    return _redact_string(str(value))


class RequestContextFilter(logging.Filter):
    """Attach request and trace correlation without requiring logger plumbing."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name.startswith(_UNSAFE_LOGGER_PREFIXES):
            return False
        record.mouvadah_request_id = current_request_id()
        record.mouvadah_trace_id = current_trace_id()
        record.event_fields = _event_fields.get() or {}
        return True


class JsonFormatter(logging.Formatter):
    """Emit a stable JSON envelope without exception values or local state."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "severity": record.levelname,
            "event": getattr(record, "event_name", record.getMessage()),
            "logger": record.name,
            "service": "mouvadah-api",
            "service_version": __version__,
            "git_sha": git_sha(),
            "environment": _deployment_environment,
        }
        request_id = getattr(record, "mouvadah_request_id", None)
        trace_id = getattr(record, "mouvadah_trace_id", None)
        if request_id:
            payload["request_id"] = request_id
        if trace_id:
            payload["trace_id"] = trace_id
        fields = getattr(record, "event_fields", {})
        if isinstance(fields, Mapping):
            for key, value in fields.items():
                if _SAFE_EVENT_FIELD.fullmatch(str(key)):
                    payload[str(key)] = redact(value, key=str(key))
        if record.exc_info and record.exc_info[2] is not None:
            payload["error_type"] = record.exc_info[0].__name__
            payload["error_frames"] = [
                {
                    "file": frame.filename,
                    "line": frame.lineno,
                    "function": frame.name,
                }
                for frame in traceback.extract_tb(record.exc_info[2])[-20:]
            ]
        return json.dumps(redact(payload), separators=(",", ":"), sort_keys=True)


def log_event(
    logger: logging.Logger,
    level: int,
    event_name: str,
    *,
    exc_info: bool = False,
    **fields: Any,
) -> None:
    # Redact before values enter the logging framework. The ContextVar keeps
    # structured fields available to the synchronous handler without passing
    # potentially sensitive inputs to a logging sink.
    safe_fields = redact(fields)
    fields_token = _event_fields.set(
        safe_fields if isinstance(safe_fields, dict) else {}
    )
    try:
        logger.log(
            level,
            event_name,
            extra={"event_name": event_name},
            exc_info=exc_info,
        )
    finally:
        _event_fields.reset(fields_token)


def configure_logging(
    *,
    level: str,
    deployment_environment: str,
) -> None:
    """Install one redacting JSON handler for application and server logs."""
    global _deployment_environment
    _deployment_environment = deployment_environment
    handler = logging.StreamHandler(sys.stderr)
    handler.addFilter(RequestContextFilter())
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    root.mouvadah_structured_logging = True  # type: ignore[attr-defined]

    # Middleware emits normalized access events, so disable Uvicorn's
    # duplicated free-form access line. Error logs propagate into JSON.
    logging.getLogger("uvicorn.access").disabled = True
    uvicorn_error = logging.getLogger("uvicorn.error")
    uvicorn_error.handlers.clear()
    uvicorn_error.propagate = True
    for noisy_logger in ("httpcore", "httpx", "sqlalchemy.engine"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def _sentry_before_send(
    event: dict[str, Any],
    hint: dict[str, Any],
) -> dict[str, Any] | None:
    del hint
    request = event.get("request")
    if isinstance(request, dict):
        for risky_key in (
            "cookies",
            "data",
            "env",
            "headers",
            "query_string",
            "url",
        ):
            request.pop(risky_key, None)
    event.pop("user", None)
    for risky_key in ("breadcrumbs", "extra", "logentry", "message"):
        event.pop(risky_key, None)
    exception = event.get("exception")
    if isinstance(exception, dict):
        values = exception.get("values")
        if isinstance(values, list):
            for exception_value in values:
                if not isinstance(exception_value, dict):
                    continue
                exception_value.pop("value", None)
                stacktrace = exception_value.get("stacktrace")
                if not isinstance(stacktrace, dict):
                    continue
                frames = stacktrace.get("frames")
                if isinstance(frames, list):
                    for frame in frames:
                        if isinstance(frame, dict):
                            frame.pop("vars", None)
    tags = event.setdefault("tags", {})
    request_id = current_request_id()
    trace_id = current_trace_id()
    if request_id:
        tags["request_id"] = request_id
    if trace_id:
        tags["trace_id"] = trace_id
    return redact(event)


def configure_error_aggregation(settings: Settings) -> None:
    """Enable privacy-restricted Sentry error aggregation when configured."""
    global _sentry_initialized
    dsn = settings.sentry_dsn_value()
    if not dsn or _sentry_initialized:
        return
    sentry_sdk.init(
        dsn=dsn,
        environment=settings.observability_environment(),
        release=f"mouvadah-api@{git_sha()}",
        send_default_pii=False,
        max_request_body_size="never",
        include_local_variables=False,
        traces_sample_rate=0.0,
        before_send=_sentry_before_send,
    )
    _sentry_initialized = True


def configure_runtime(settings: Settings) -> None:
    configure_logging(
        level=settings.log_level,
        deployment_environment=settings.observability_environment(),
    )
    configure_error_aggregation(settings)
    configure_open_telemetry(settings)


def _otlp_signal_endpoint(base_url: str, signal: str) -> str:
    return f"{base_url.rstrip('/')}/v1/{signal}"


def configure_open_telemetry(settings: Settings) -> None:
    """Initialize process-wide trace/metric providers for API and CLI jobs."""
    global _tracer_provider, _meter_provider
    global _otel_job_runs, _otel_job_duration

    resource = Resource.create(
        {
            "service.name": "mouvadah-api",
            "service.version": __version__,
            "deployment.environment.name": (
                settings.observability_environment()
            ),
        }
    )
    if _tracer_provider is None:
        tracer_provider = TracerProvider(
            resource=resource,
            sampler=ParentBased(
                TraceIdRatioBased(settings.otel_trace_sample_ratio)
            ),
        )
        if settings.otel_exporter_otlp_endpoint:
            # Keep the configured value a common OTLP base URL. Authentication
            # headers still come from the standard OTLP environment variable.
            tracer_provider.add_span_processor(
                BatchSpanProcessor(
                    OTLPSpanExporter(
                        endpoint=_otlp_signal_endpoint(
                            settings.otel_exporter_otlp_endpoint,
                            "traces",
                        )
                    )
                )
            )
        trace.set_tracer_provider(tracer_provider)
        _tracer_provider = tracer_provider

    if (
        _meter_provider is None
        and settings.otel_exporter_otlp_endpoint
    ):
        metric_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(
                endpoint=_otlp_signal_endpoint(
                    settings.otel_exporter_otlp_endpoint,
                    "metrics",
                )
            ),
            export_interval_millis=60_000,
        )
        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[metric_reader],
        )
        metrics.set_meter_provider(meter_provider)
        _meter_provider = meter_provider
        meter = metrics.get_meter("mouvadah.jobs")
        _otel_job_runs = meter.create_counter(
            "mouvadah.job.runs",
            unit="1",
            description="Operator job runs.",
        )
        _otel_job_duration = meter.create_histogram(
            "mouvadah.job.duration",
            unit="s",
            description="Operator job duration.",
        )


def flush_telemetry() -> None:
    if _tracer_provider is not None:
        _tracer_provider.force_flush(timeout_millis=5000)
    if _meter_provider is not None:
        _meter_provider.force_flush(timeout_millis=5000)
    sentry_sdk.flush(timeout=5)


def metrics_response() -> Response:
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


def metrics_token_matches(
    configured_token: str | None,
    supplied_token: str | None,
) -> bool:
    if not configured_token or not supplied_token:
        return False
    return hmac.compare_digest(configured_token, supplied_token)


def _route_label(scope: Scope) -> str:
    request_path = scope.get("path", "")
    if request_path.startswith("/assets/"):
        return "/assets/{path}"
    route = scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        root_path = str(scope.get("root_path", "")).rstrip("/")
        route_path = f"{root_path}{path}"
        if route_path.startswith("/assets"):
            return "/assets/{path}"
        return route_path or "/"
    if request_path in {"/healthz", "/readyz", "/internal/metrics"}:
        return request_path
    return "unmatched"


def _request_state(scope: Scope) -> dict[str, Any]:
    state = scope.get("state")
    return state if isinstance(state, dict) else {}


def _incoming_trace_context(scope: Scope):
    carrier: dict[str, str] = {}
    for raw_name, raw_value in scope.get("headers", []):
        name = raw_name.decode("latin-1").lower()
        if name in {"traceparent", "tracestate"}:
            carrier[name] = raw_value.decode("latin-1")
    return TraceContextTextMapPropagator().extract(carrier)


class ObservabilityMiddleware:
    """Correlate and measure every HTTP response without recording content."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = logging.getLogger("mouvadah.http")

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex
        request_token = _request_id.set(request_id)
        state = scope.setdefault("state", {})
        state["request_id"] = request_id
        started_at = time.perf_counter()
        method = str(scope.get("method", "UNKNOWN")).upper()
        try:
            tracer = trace.get_tracer("mouvadah.http")
            with tracer.start_as_current_span(
                f"{method} request",
                context=_incoming_trace_context(scope),
                kind=SpanKind.SERVER,
                attributes={
                    "http.request.method": method,
                    "mouvadah.request.id": request_id,
                },
                record_exception=False,
                set_status_on_exception=False,
            ) as span:
                span_context = span.get_span_context()
                if span_context.is_valid:
                    state["trace_id"] = format(
                        span_context.trace_id,
                        "032x",
                    )
                status_code = 500
                response_started = False
                response_bytes = 0
                unhandled: Exception | None = None

                async def send_with_correlation(message: Message) -> None:
                    nonlocal status_code, response_bytes, response_started
                    if message["type"] == "http.response.start":
                        response_started = True
                        status_code = int(message["status"])
                        headers = MutableHeaders(scope=message)
                        headers["X-Request-ID"] = request_id
                    elif message["type"] == "http.response.body":
                        body = message.get("body", b"")
                        if isinstance(body, bytes):
                            response_bytes += len(body)
                    await send(message)

                try:
                    await self.app(scope, receive, send_with_correlation)
                except asyncio.CancelledError:
                    status_code = 499
                    raise
                except Exception as exc:
                    unhandled = exc
                    status_code = 500
                    raise
                finally:
                    duration = time.perf_counter() - started_at
                    route = _route_label(scope)
                    span.update_name(f"{method} {route}")
                    span.set_attribute("http.route", route)
                    span.set_attribute(
                        "http.response.status_code",
                        status_code,
                    )
                    span.set_attribute("http.response.body.size", response_bytes)
                    if status_code >= 500:
                        span.set_status(Status(StatusCode.ERROR))
                    if unhandled is not None:
                        span.set_attribute(
                            "error.type",
                            type(unhandled).__name__,
                        )
                    # Skip successful scraper noise, but retain disabled or
                    # unauthorized attempts as request/auth-failure signals.
                    if (
                        scope.get("path") != "/internal/metrics"
                        or status_code != 200
                    ):
                        HTTP_REQUESTS.labels(
                            method,
                            route,
                            str(status_code),
                        ).inc()
                        HTTP_DURATION.labels(method, route).observe(duration)
                        HTTP_RESPONSE_SIZE.labels(method, route).observe(
                            response_bytes
                        )
                        if status_code in {401, 403}:
                            AUTH_FAILURES.labels(str(status_code)).inc()
                        state = _request_state(scope)
                        fields = {
                            "method": method,
                            "route": route,
                            "status": status_code,
                            "duration_ms": round(duration * 1000, 3),
                            "response_bytes": response_bytes,
                            "response_started": response_started,
                            "auth_method": state.get("auth_method"),
                            "actor_user_id": state.get("user_id"),
                            "api_key_id": state.get("api_key_id"),
                            "workspace_id": state.get("workspace_id"),
                        }
                        if unhandled is not None:
                            HTTP_EXCEPTIONS.labels(
                                route,
                                type(unhandled).__name__,
                            ).inc()
                            log_event(
                                self.logger,
                                logging.ERROR,
                                "http.request.failed",
                                exc_info=True,
                                **fields,
                            )
                        else:
                            log_event(
                                self.logger,
                                (
                                    logging.WARNING
                                    if status_code >= 500
                                    else logging.INFO
                                ),
                                "http.request.completed",
                                **fields,
                            )
        finally:
            _request_id.reset(request_token)


def _database_operation(statement: str | None) -> str:
    match = _SQL_OPERATION.match(statement or "")
    operation = match.group(1).upper() if match else "OTHER"
    if operation not in {
        "SELECT",
        "INSERT",
        "UPDATE",
        "DELETE",
        "WITH",
        "PRAGMA",
        "CREATE",
        "ALTER",
        "DROP",
    }:
        return "OTHER"
    return operation


def _pop_database_timer(
    connection: Any,
) -> tuple[float, str, Any] | None:
    stack = connection.info.get("_mouvadah_observation_stack", [])
    return stack.pop() if stack else None


def instrument_database_metrics(engine: Engine) -> None:
    """Attach operation-only SQL spans and low-cardinality pool metrics."""
    if engine in _instrumented_engines:
        return
    _instrumented_engines.add(engine)
    tracer = trace.get_tracer("mouvadah.database")
    database_system = engine.dialect.name

    def before_cursor_execute(
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        del cursor, parameters, context, executemany
        operation = _database_operation(statement)
        span = tracer.start_span(
            f"database.{operation.lower()}",
            kind=SpanKind.CLIENT,
            attributes={
                "db.operation.name": operation,
                "db.system.name": database_system,
            },
        )
        connection.info.setdefault(
            "_mouvadah_observation_stack",
            [],
        ).append((time.perf_counter(), operation, span))

    def after_cursor_execute(
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        del cursor, statement, parameters, context, executemany
        timer = _pop_database_timer(connection)
        if timer is None:
            return
        started_at, operation, span = timer
        DB_QUERIES.labels(operation, "success").inc()
        DB_DURATION.labels(operation).observe(
            time.perf_counter() - started_at
        )
        span.end()

    def handle_error(exception_context) -> None:
        connection = exception_context.connection
        if connection is None:
            return
        timer = _pop_database_timer(connection)
        if timer is None:
            return
        started_at, operation, span = timer
        DB_QUERIES.labels(operation, "error").inc()
        DB_DURATION.labels(operation).observe(
            time.perf_counter() - started_at
        )
        span.set_status(Status(StatusCode.ERROR))
        span.set_attribute(
            "error.type",
            type(exception_context.original_exception).__name__,
        )
        span.end()

    def checkout(dbapi_connection, connection_record, connection_proxy) -> None:
        del dbapi_connection, connection_record, connection_proxy
        DB_CONNECTIONS.inc()

    def checkin(dbapi_connection, connection_record) -> None:
        del dbapi_connection, connection_record
        DB_CONNECTIONS.dec()

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    event.listen(engine, "after_cursor_execute", after_cursor_execute)
    event.listen(engine, "handle_error", handle_error)
    event.listen(engine.pool, "checkout", checkout)
    event.listen(engine.pool, "checkin", checkin)


def record_realtime_event(transport: str, outcome: str) -> None:
    REALTIME_EVENTS.labels(transport, outcome).inc()


def record_realtime_resync(reason: str) -> None:
    # The caller controls this bounded protocol enum, never user input.
    REALTIME_RESYNCS.labels(reason).inc()


def record_realtime_reconnect(outcome: str) -> None:
    REALTIME_RECONNECTS.labels(outcome).inc()


def set_realtime_health(healthy: bool) -> None:
    REALTIME_HEALTH.set(1 if healthy else 0)


def add_realtime_subscriber(delta: int) -> None:
    REALTIME_SUBSCRIBERS.inc(delta)


@contextmanager
def observe_job(job: str) -> Iterator[None]:
    """Measure and trace a bounded operator job without capturing arguments."""
    logger = logging.getLogger("mouvadah.job")
    tracer = trace.get_tracer("mouvadah.jobs")
    started_at = time.perf_counter()
    log_event(logger, logging.INFO, "job.started", job=job)
    with tracer.start_as_current_span(
        f"job.{job}",
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        span.set_attribute("mouvadah.job.name", job)
        try:
            yield
        except Exception:
            duration = time.perf_counter() - started_at
            error_type = sys.exc_info()[0]
            span.set_status(Status(StatusCode.ERROR))
            if error_type is not None:
                span.set_attribute("error.type", error_type.__name__)
            JOB_RUNS.labels(job, "failed").inc()
            JOB_DURATION.labels(job).observe(duration)
            if _otel_job_runs is not None:
                _otel_job_runs.add(
                    1,
                    {"mouvadah.job.name": job, "outcome": "failed"},
                )
                _otel_job_duration.record(
                    duration,
                    {"mouvadah.job.name": job, "outcome": "failed"},
                )
            log_event(
                logger,
                logging.ERROR,
                "job.failed",
                job=job,
                duration_ms=round(duration * 1000, 3),
                exc_info=True,
            )
            sentry_sdk.capture_exception()
            raise
        else:
            duration = time.perf_counter() - started_at
            JOB_RUNS.labels(job, "succeeded").inc()
            JOB_DURATION.labels(job).observe(duration)
            if _otel_job_runs is not None:
                _otel_job_runs.add(
                    1,
                    {"mouvadah.job.name": job, "outcome": "succeeded"},
                )
                _otel_job_duration.record(
                    duration,
                    {"mouvadah.job.name": job, "outcome": "succeeded"},
                )
            log_event(
                logger,
                logging.INFO,
                "job.completed",
                job=job,
                duration_ms=round(duration * 1000, 3),
            )
