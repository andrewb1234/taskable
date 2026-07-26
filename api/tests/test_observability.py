"""Privacy, correlation, metrics, readiness, and telemetry controls."""

from __future__ import annotations

import json
import logging
import re
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from api.config import Settings, get_settings
from api.main import create_app
from api.observability import (
    JsonFormatter,
    RequestContextFilter,
    _otlp_signal_endpoint,
    _sentry_before_send,
    instrument_database_metrics,
    log_event,
    observe_job,
)


def _production_settings(**overrides) -> Settings:
    values = {
        "frontend_url": "https://app.example.com",
        "jwt_secret": "j" * 32,
        "google_client_id": "client-id",
        "google_client_secret": "client-secret",
        "migration_mode": "check",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_otlp_common_endpoint_expands_to_signal_paths():
    base_url = "https://collector.example/tenant/"

    assert _otlp_signal_endpoint(base_url, "traces") == (
        "https://collector.example/tenant/v1/traces"
    )
    assert _otlp_signal_endpoint(base_url, "metrics") == (
        "https://collector.example/tenant/v1/metrics"
    )


def test_request_id_is_server_generated_and_health_is_correlated(client):
    response = client.get(
        "/healthz",
        headers={"X-Request-ID": "attacker-controlled-request-id"},
    )

    assert response.status_code == 200
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["X-Request-ID"])
    assert response.headers["X-Request-ID"] != (
        "attacker-controlled-request-id"
    )


def test_readiness_checks_database_and_realtime(client):
    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["database"] == "healthy"
    assert response.json()["realtime"] == "local"


def test_readiness_rejects_traffic_when_database_is_unavailable(
    client,
    monkeypatch,
):
    class UnavailableDatabase:
        def connect(self):
            raise RuntimeError("database-host-secret")

    monkeypatch.setattr(
        "api.main.database.engine",
        UnavailableDatabase(),
    )

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["database"] == "unavailable"
    assert "database-host-secret" not in response.text


def test_readiness_rejects_degraded_realtime(client, monkeypatch):
    monkeypatch.setattr(
        "api.main.get_broadcaster",
        lambda: SimpleNamespace(status=lambda: "degraded"),
    )

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["database"] == "healthy"
    assert response.json()["realtime"] == "degraded"


def test_metrics_endpoint_is_hidden_until_token_is_configured(client):
    response = client.get("/internal/metrics")

    assert response.status_code == 404


def test_metrics_endpoint_requires_dedicated_token(
    engine,
    monkeypatch,
):
    token = "m" * 32
    monkeypatch.setenv("METRICS_BEARER_TOKEN", token)
    get_settings.cache_clear()
    observed_app = create_app()

    with TestClient(observed_app) as observed_client:
        denied = observed_client.get(
            "/internal/metrics",
            headers={"Authorization": "Bearer wrong"},
        )
        accepted = observed_client.get(
            "/internal/metrics",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert denied.status_code == 401
    assert accepted.status_code == 200
    assert "mouvadah_http_requests_total" in accepted.text
    assert "mouvadah_http_response_body_bytes" in accepted.text
    assert "mouvadah_database_queries_total" in accepted.text
    assert token not in accepted.text


def test_w3c_trace_id_is_attached_to_request_log(client):
    trace_id = "0af7651916cd43dd8448eb211c80319c"
    logger = logging.getLogger("mouvadah.http")
    records: list[logging.LogRecord] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = Capture()
    handler.addFilter(RequestContextFilter())
    logger.addHandler(handler)
    try:
        response = client.get(
            "/api/v1/projects",
            headers={
                "traceparent": (
                    f"00-{trace_id}-b7ad6b7169203331-01"
                )
            },
        )
    finally:
        logger.removeHandler(handler)

    assert response.status_code == 200
    assert records
    assert records[-1].mouvadah_trace_id == trace_id
    assert records[-1].mouvadah_request_id == response.headers["X-Request-ID"]


def test_http_trace_never_records_query_or_headers(client, monkeypatch):
    observed_spans = []

    class Span:
        def __init__(self, name, attributes):
            self.name = name
            self.attributes = dict(attributes)

        def get_span_context(self):
            return SimpleNamespace(is_valid=False)

        def update_name(self, name):
            self.name = name

        def set_attribute(self, key, value):
            self.attributes[key] = value

        def set_status(self, status):
            self.status = status

    class Tracer:
        @contextmanager
        def start_as_current_span(
            self,
            name,
            *,
            context,
            kind,
            attributes,
            record_exception,
            set_status_on_exception,
        ):
            del (
                context,
                kind,
                record_exception,
                set_status_on_exception,
            )
            span = Span(name, attributes)
            observed_spans.append(span)
            yield span

    monkeypatch.setattr(
        "api.observability.trace.get_tracer",
        lambda name: Tracer(),
    )
    response = client.get(
        "/api/v1/projects?token=private-query-value",
        headers={"X-Private-Header": "private-header-value"},
    )

    assert response.status_code == 200
    assert len(observed_spans) == 1
    span = observed_spans[0]
    assert span.name == "GET /api/v1/projects"
    assert span.attributes["http.route"] == "/api/v1/projects"
    encoded = repr(span.attributes)
    assert "private-query-value" not in encoded
    assert "private-header-value" not in encoded
    assert "token" not in encoded


def test_json_formatter_redacts_credentials_and_omits_exception_value():
    formatter = JsonFormatter()
    try:
        raise RuntimeError("password=exception-secret")
    except RuntimeError:
        record = logging.getLogger("test").makeRecord(
            "test",
            logging.ERROR,
            __file__,
            1,
            (
                "Authorization: Bearer bearer-secret "
                "postgresql://user:database-secret@db.example/app "
                "api_key=key-secret "
                "person@example.com "
                "https://app.example/path?search=query-private"
            ),
            (),
            __import__("sys").exc_info(),
        )
    record.event_name = "test.failure"
    record.event_fields = {
        "workspace_id": 7,
        "cookie": "session-secret",
    }
    record.mouvadah_request_id = "request-id"
    record.mouvadah_trace_id = "trace-id"

    payload = formatter.format(record)
    decoded = json.loads(payload)

    assert decoded["event"] == "test.failure"
    assert decoded["workspace_id"] == 7
    assert decoded["cookie"] == "[REDACTED]"
    assert decoded["error_type"] == "RuntimeError"
    assert decoded["error_frames"]
    for secret in (
        "bearer-secret",
        "database-secret",
        "key-secret",
        "query-private",
        "session-secret",
        "exception-secret",
        "person@example.com",
    ):
        assert secret not in payload


def test_structured_fields_are_redacted_before_logging():
    logger = logging.getLogger("mouvadah.test.redaction")
    records: list[logging.LogRecord] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = Capture()
    handler.addFilter(RequestContextFilter())
    logger.addHandler(handler)
    try:
        log_event(
            logger,
            logging.INFO,
            "test.redaction",
            password="clear-text-password",
            workspace_id=9,
        )
    finally:
        logger.removeHandler(handler)

    assert records[0].event_fields == {
        "password": "[REDACTED]",
        "workspace_id": 9,
    }
    assert "clear-text-password" not in repr(records[0].__dict__)


def test_sentry_scrubber_removes_request_content_and_user_data():
    event = {
        "request": {
            "url": "https://app.example.com/path?token=url-secret",
            "headers": {"Authorization": "Bearer header-secret"},
            "cookies": {"session": "cookie-secret"},
            "data": {"password": "body-secret"},
            "query_string": "token=query-secret",
        },
        "user": {"email": "person@example.com"},
        "extra": {
            "database_url": "postgresql://user:db-secret@db.example/app"
        },
        "breadcrumbs": {
            "values": [{"message": "arbitrary-breadcrumb-secret"}]
        },
        "exception": {
            "values": [
                {
                    "type": "RuntimeError",
                    "value": "arbitrary-exception-secret",
                    "stacktrace": {
                        "frames": [
                            {
                                "filename": "worker.py",
                                "vars": {
                                    "private": "arbitrary-local-secret"
                                },
                            }
                        ]
                    },
                }
            ]
        },
    }

    scrubbed = _sentry_before_send(event, {})
    encoded = json.dumps(scrubbed)

    assert "headers" not in scrubbed["request"]
    assert "cookies" not in scrubbed["request"]
    assert "data" not in scrubbed["request"]
    assert "query_string" not in scrubbed["request"]
    assert "url" not in scrubbed["request"]
    assert "user" not in scrubbed
    assert "breadcrumbs" not in scrubbed
    assert "extra" not in scrubbed
    exception = scrubbed["exception"]["values"][0]
    assert "value" not in exception
    assert "vars" not in exception["stacktrace"]["frames"][0]
    for secret in (
        "url-secret",
        "header-secret",
        "cookie-secret",
        "body-secret",
        "query-secret",
        "db-secret",
        "person@example.com",
        "arbitrary-breadcrumb-secret",
        "arbitrary-exception-secret",
        "arbitrary-local-secret",
    ):
        assert secret not in encoded


def test_database_tracing_records_operation_without_statement(monkeypatch):
    observed_spans = []

    class Span:
        def __init__(self, name, kind, attributes):
            self.name = name
            self.kind = kind
            self.attributes = attributes
            self.ended = False

        def end(self):
            self.ended = True

        def set_status(self, status):
            self.status = status

        def set_attribute(self, key, value):
            self.attributes[key] = value

    class Tracer:
        def start_span(self, name, *, kind, attributes):
            span = Span(name, kind, attributes)
            observed_spans.append(span)
            return span

    monkeypatch.setattr(
        "api.observability.trace.get_tracer",
        lambda name: Tracer(),
    )
    observed_engine = create_engine("sqlite://")
    instrument_database_metrics(observed_engine)

    with observed_engine.connect() as connection:
        connection.execute(text("SELECT 'private-statement-value'"))

    assert len(observed_spans) == 1
    assert observed_spans[0].name == "database.select"
    assert observed_spans[0].attributes == {
        "db.operation.name": "SELECT",
        "db.system.name": "sqlite",
    }
    assert observed_spans[0].ended is True
    assert "private-statement-value" not in repr(observed_spans[0].attributes)

    with pytest.raises(Exception):
        with observed_engine.connect() as connection:
            connection.execute(
                text("SELECT arbitrary_sql_secret FROM missing_table")
            )

    failed_span = observed_spans[-1]
    assert failed_span.name == "database.select"
    assert failed_span.ended is True
    assert "error.type" in failed_span.attributes
    assert "arbitrary_sql_secret" not in repr(failed_span.attributes)
    assert "missing_table" not in repr(failed_span.attributes)


def test_failed_job_trace_records_type_without_exception_value(monkeypatch):
    observed = {}

    class Span:
        def __init__(self):
            self.attributes = {}

        def set_attribute(self, key, value):
            self.attributes[key] = value

        def set_status(self, status):
            self.status = status

    class Tracer:
        @contextmanager
        def start_as_current_span(self, name, **kwargs):
            observed["name"] = name
            observed["kwargs"] = kwargs
            observed["span"] = Span()
            yield observed["span"]

    monkeypatch.setattr(
        "api.observability.trace.get_tracer",
        lambda name: Tracer(),
    )

    with pytest.raises(RuntimeError, match="arbitrary-job-secret"):
        with observe_job("database_verify"):
            raise RuntimeError("arbitrary-job-secret")

    assert observed["name"] == "job.database_verify"
    assert observed["kwargs"] == {
        "record_exception": False,
        "set_status_on_exception": False,
    }
    assert observed["span"].attributes == {
        "mouvadah.job.name": "database_verify",
        "error.type": "RuntimeError",
    }
    assert "arbitrary-job-secret" not in repr(observed)


@pytest.mark.parametrize(
    "overrides,match",
    [
        ({"metrics_bearer_token": "short"}, "METRICS_BEARER_TOKEN"),
        ({"otel_trace_sample_ratio": 1.1}, "OTEL_TRACE_SAMPLE_RATIO"),
        (
            {
                "otel_exporter_otlp_endpoint": (
                    "https://user:secret@collector.example/v1/traces"
                )
            },
            "must not contain credentials",
        ),
        (
            {"deployment_environment": "bad environment"},
            "DEPLOYMENT_ENVIRONMENT",
        ),
    ],
)
def test_observability_configuration_rejects_unsafe_values(
    overrides,
    match,
):
    with pytest.raises(RuntimeError, match=match):
        _production_settings(**overrides).validate_production()


@pytest.mark.parametrize(
    "field",
    ["otel_exporter_otlp_endpoint", "sentry_dsn"],
)
def test_production_observability_exports_require_https(field):
    with pytest.raises(RuntimeError, match="must use HTTPS"):
        _production_settings(
            **{field: "http://collector.example/ingest"}
        ).validate_production()
